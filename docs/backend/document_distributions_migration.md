## Document Distributions Migration

This guide documents how to migrate legacy `document_distributions` rows from the old BTAA Geoportal database into the new `resource_distributions` table. It expands on the existing `old_database_migration` documentation and should be referenced when running production cutover dry-runs.

### Legacy Schema Summary (`geoportal_production_20251030`)
- `document_distributions`
  - `id` bigint primary key
  - `friendlier_id` varchar (required) — matches the resource identifier exposed in the legacy API
  - `reference_type_id` bigint (required) — FK to `reference_types.id`
  - `url` varchar nullable — legacy system allowed empty distributions
  - `label` varchar nullable
  - `position` integer nullable — ordering set by editors, often NULL
  - `created_at`, `updated_at` timestamp without time zone (required)
  - `import_distribution_id` bigint nullable
  - Unique index `(friendlier_id, reference_type_id, url)` ensured no duplicate URLs per resource/type

- `reference_types`
  - Columns align 1:1 with the new `distribution_types` lookup (`name`, `reference_type`, `reference_uri`, `label`, `note`, `position`)
  - IDs are stable across legacy and new databases (verified spot-check).

### New Schema Summary (`btaa_ogm_api`)
- `resource_distributions`
  - `id` serial primary key
  - `resource_id` varchar(255) required — matches `resources.id`
  - `distribution_type_id` integer required — FK to `distribution_types.id`
  - `url` text required (we must skip or remediate NULL legacy URLs)
  - `label` varchar(255) nullable
  - `position` integer default 0
  - `created_at`, `updated_at` timestamptz default `now()`
  - `import_distribution_id` varchar(255) nullable
  - Several supporting indexes (resource, type, url, position, import ID)

- `distribution_types`
  - Lookup table seeded from OpenGeoMetadata. Schema matches legacy `reference_types` and IDs/names align exactly.

### Field Mapping & Required Transformations
| Legacy (`document_distributions`) | New (`resource_distributions`) | Notes |
| --- | --- | --- |
| `friendlier_id` | `resource_id` | Legacy `friendlier_id` equals the new `resources.id` populated via the bridge (`COALESCE(friendlier_id, id)`), so a direct copy preserves relationships. |
| `reference_type_id` | `distribution_type_id` | IDs match between `reference_types` and `distribution_types`; fallback join on `reference_uri` if future divergence is detected. |
| `url` | `url` | Legacy allows NULL; new schema requires non-null. Skip NULL/empty values and log counts. Cast to text for consistency. |
| `label` | `label` | Copy as-is; legacy values already <= 255 chars. |
| `position` | `position` | Use legacy value when present; default to 0 when NULL. |
| `created_at` | `created_at` | Convert legacy `timestamp` (assume UTC) to `timestamptz`. |
| `updated_at` | `updated_at` | Same conversion as `created_at`. |
| `import_distribution_id` (bigint) | `import_distribution_id` (varchar) | Cast to string when present; preserve exact numeric text for downstream traceability. |

Additional rules:
- Enforce uniqueness per `(resource_id, distribution_type_id, url)` when inserting to avoid duplicates if the script is re-run.
- Trim whitespace from URLs and labels to match new validation expectations.
- Optionally normalize URLs (e.g., strip surrounding quotes) if encountered — log any sanitization performed.

### ID Resolution Strategy
1. Load a mapping from `reference_types` (old) to `distribution_types` (new). Prefer joining on `reference_uri` and verifying ID equality; raise when mismatched to avoid silent data drift.
2. Validate that every `friendlier_id` from the old table exists in the new `resources` table. Produce a report of missing resources; optionally gate insertion on full alignment.
3. For future incremental loads, allow filtering by a resource ID list or timestamp window.

### Deduplication & Conflict Handling
- Legacy unique constraint prevents duplicates, so the new workflow creates a matching unique index on `(resource_id, distribution_type_id, url)` and upserts on that natural key.
- When re-running the job, existing rows with a non-null `import_distribution_id` are removed (or the table is truncated if requested) to keep the operation idempotent without touching manually curated data.
- Consider clearing the target table (after backup) only when performing full refresh; otherwise rely on the upsert to preserve downstream edits while keeping URLs unique per resource/type.

### Timestamps & Time Zones
- Legacy timestamps are stored without time zone; treat them as UTC and attach `+00` during copy (`created_at AT TIME ZONE 'UTC'`). The script should accept an override in case the legacy DB stored local times.
- When timestamps are NULL (should not happen), fall back to `NOW()` but log.

### Null URL Handling
- Rows with NULL or empty URLs cannot be inserted. Record their count in the migration log and optionally export to CSV for manual remediation.

### Verification Checklist
- Compare row counts by distribution type: `SELECT reference_type_id, COUNT(*) FROM document_distributions GROUP BY 1` vs equivalent on `resource_distributions`.
- Sample a few resources to ensure ordering (`position`) is preserved.
- Confirm `import_distribution_id` text matches original bigint values.
- For resources lacking distributions post-migration, confirm they are absent in legacy data as well.

### Migration Script (`db/migrations/migrate_document_distributions.py`)
- CLI options:
  - `--dry-run` for read-only validation
  - `--batch-size` to tune throughput (default 1000)
  - `--no-delete-existing` to preserve prior rows, `--truncate` for full refresh
  - `--skip-resource-check` to bypass verification that `resources.id` already exists
  - `--verbose` to enable debug logging (including sample missing resource IDs)
- Automatically ensures a unique index on `(resource_id, distribution_type_id, url)` so upserts succeed on repeat runs.
- Deletes previously migrated rows that have `import_distribution_id` set (or truncates the table when requested) before inserting new data, keeping the operation idempotent.
- Stores the legacy `document_distributions.id` in `import_distribution_id` to make subsequent clean-up or spot checks easy.
- Writes consolidated stats (processed, skipped-null-url, skipped-missing-resource, inserted) to the log after each batch and at completion.

This document should be kept in sync with the migration script described above.

### Recommended Runbook
1. **Pre-checks**
   - Ensure `import_from_old_production.py` (resources) has been run recently so the new database already contains corresponding `resources.id` values.
   - Run `python db/migrations/migrate_document_distributions.py --dry-run --verbose` to validate type mappings and resource coverage without writing data.
2. **Full migration**
   - For a clean refresh, execute `python db/migrations/migrate_document_distributions.py --truncate --batch-size 2000`.
   - For incremental refreshes where manual edits may exist, use `--no-delete-existing` and rely on the upsert to touch only matching `(resource_id, distribution_type_id, url)` rows.
3. **Post-run validation**
   - Execute the verification queries above; store outputs (counts, sample comparisons) alongside other migration logs.
   - Rerun `python db/migrations/import_from_old_production.py --verify` if the resource import occurred earlier, ensuring resource/distribution counts align.
4. **Before go-live**
   - Repeat the dry-run and full migration steps against fresh database snapshots to confirm repeatability.
   - Refresh Elasticsearch indices (`python run_index.py`) once resources and distributions are in place.

