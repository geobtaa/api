# Disaster Recovery Backups

This runbook covers the production backup path for the BTAA Geospatial API
single-host Kamal deployment.

## Scope

- `prd` gets nightly disaster-recovery backups.
- `dev1` and `dev2` are not backed up by default. The cron entries exist in the
  shared image, but both backup scripts exit cleanly unless `BACKUP_ENABLED=true`
  and `KAMAL_DEST` matches `BACKUP_REQUIRED_DEST`.
- Retention is count-based: keep the latest three successful Postgres dumps and
  the latest three managed Elasticsearch snapshots.

## Schedule

The Kamal cron container runs:

- 5:30 AM America/Chicago: `backup_postgres_to_s3.py`
- 5:45 AM America/Chicago: `backup_elasticsearch.py --scheduled --create --wait --retain-count ${BACKUP_RETENTION_COUNT:-3}`

These run after the bridge sync, blog sync, sitemap generation, and analytics
maintenance jobs in `config/crontab`.

## S3 Layout

Default keys use:

```text
s3://<BACKUP_S3_BUCKET>/<BACKUP_S3_PREFIX>/prd/postgres/*.dump
s3://<BACKUP_S3_BUCKET>/<BACKUP_S3_PREFIX>/prd/postgres/*.dump.manifest.json
s3://<BACKUP_S3_BUCKET>/<BACKUP_S3_PREFIX>/prd/elasticsearch/<snapshot-repository-objects>
```

The default `BACKUP_S3_PREFIX` is `btaa-geospatial-api`.

Do not use S3 lifecycle expiration directly under the Elasticsearch snapshot
prefix. Elasticsearch snapshot repositories maintain metadata across objects;
delete old snapshots through the Elasticsearch snapshot API, which the script
does with `--retain-count`.

## Required Production Settings

Set these for `prd` before enabling backups:

```bash
BACKUP_ENABLED=true
BACKUP_S3_BUCKET=<bucket-name>
BACKUP_S3_PREFIX=btaa-geospatial-api
BACKUP_S3_REGION=us-east-2
AWS_ACCESS_KEY_ID=<secret>
AWS_SECRET_ACCESS_KEY=<secret>
```

`config/deploy.prd.yml` defaults `BACKUP_ENABLED` to true, but the jobs will
fail until `BACKUP_S3_BUCKET` and usable AWS credentials exist.

The IAM principal needs at least list/read/write/delete permission for:

```text
arn:aws:s3:::<bucket-name>/<BACKUP_S3_PREFIX>/prd/*
```

## One-Time Elasticsearch S3 Setup

The Postgres backup uses the AWS CLI in the cron container. Elasticsearch S3
snapshots are written by the Elasticsearch node itself, so its S3 client must
also have credentials.

If the production host has an AWS instance profile or another supported ambient
credential source, use that. Otherwise, after the AWS secrets are available to
the Elasticsearch accessory, add them to the Elasticsearch keystore:

```bash
kamal accessory exec -d prd elasticsearch \
  "bash -lc 'printf %s \"\$AWS_ACCESS_KEY_ID\" | bin/elasticsearch-keystore add -x -f s3.client.default.access_key'"

kamal accessory exec -d prd elasticsearch \
  "bash -lc 'printf %s \"\$AWS_SECRET_ACCESS_KEY\" | bin/elasticsearch-keystore add -x -f s3.client.default.secret_key'"

kamal accessory reboot -d prd elasticsearch
```

After restart, create/test the repository with:

```bash
make kamal-backup-elasticsearch KAMAL_DEST=prd
make kamal-backup-list-elasticsearch KAMAL_DEST=prd
```

## Manual Backup Commands

Run these from the repository root:

```bash
make kamal-backup-postgres KAMAL_DEST=prd
make kamal-backup-elasticsearch KAMAL_DEST=prd
make kamal-backup-list-elasticsearch KAMAL_DEST=prd
```

## Restore Outline

Prefer restoring into a throwaway environment first so the archive and
procedure are tested without extending an outage.

### Postgres

1. Stop app writers (`web`, `worker`, and `cron`) or otherwise hold writes.
2. Download the selected `.dump` artifact from S3 to the host.
3. Restore it into the ParadeDB container:

   ```bash
   docker exec -i btaa-geospatial-api-paradedb pg_restore \
     -U postgres \
     -d btaa_geospatial_api \
     --clean \
     --if-exists \
     --no-owner \
     --no-acl \
     < /var/tmp/<backup>.dump
   ```

4. Run a health check, then rebuild/search-verify Elasticsearch if needed:

   ```bash
   make kamal-reindex KAMAL_DEST=prd
   make kamal-verify-h3-index KAMAL_DEST=prd
   ```

### Elasticsearch

When the database is intact, the safest Elasticsearch recovery is usually:

```bash
make kamal-reindex KAMAL_DEST=prd
```

Use an Elasticsearch snapshot when reindexing is unavailable or too slow:

```bash
make kamal-backup-list-elasticsearch KAMAL_DEST=prd

kamal app exec -d prd --roles cron --reuse \
  "bash -lc '/opt/venv/bin/python3 /app/scripts/backup_elasticsearch.py --restore <snapshot-name> --wait'"
```

If the existing index blocks restore, stop app traffic and delete or close the
corrupt index/alias target first.

## Restore Drill

At least monthly:

1. Restore the latest Postgres dump to a temporary database.
2. Confirm `pg_restore --list` succeeds and spot-check key tables.
3. Confirm the newest Elasticsearch snapshot lists as `SUCCESS`.
4. Document the selected backup keys, restore duration, and any manual fixes.
