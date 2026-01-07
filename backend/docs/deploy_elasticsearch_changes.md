# Deploying Elasticsearch Configuration Changes

This guide covers deploying the Elasticsearch production hardening changes to your Kamal server.

## Overview of Changes

The changes include:
1. **Application code**: ES client connection pooling (`app/elasticsearch/client.py`)
2. **Index settings**: Replica configuration (`app/elasticsearch/mappings.py`)
3. **Accessory config**: Ulimits, disk watermarks, healthcheck (`config/deploy.yml`)

## Deployment Steps

### Step 1: Commit and Push Changes

```bash
# Review your changes
git status
git diff config/deploy.yml
git diff app/elasticsearch/

# Commit the changes
git add config/deploy.yml app/elasticsearch/client.py app/elasticsearch/mappings.py scripts/ docs/
git commit -m "Add Elasticsearch production hardening: ulimits, replicas, backups"

# Push to your repository
git push
```

### Step 2: Rebuild and Deploy Application

The application code changes (ES client and mappings) require rebuilding the Docker image:

```bash
# Deploy the application (this rebuilds the image with new code)
kamal deploy

# Or if you want to rebuild without deploying
kamal build
kamal deploy --skip-build
```

**Note**: The new mappings (with replicas=1) will only apply to **new indices**. If you have an existing index, you'll need to update it (see Step 4).

### Step 3: Update Elasticsearch Accessory Configuration

The accessory configuration changes (ulimits, disk watermarks, healthcheck) require restarting the Elasticsearch container:

```bash
# Option A: Remove and recreate the accessory (applies new config)
kamal accessory remove elasticsearch
kamal accessory boot elasticsearch

# Option B: Reboot the accessory (may not apply all config changes)
kamal accessory reboot elasticsearch
```

**Recommended**: Use Option A to ensure all configuration changes are applied.

### Step 4: Update Existing Index Settings

If you have an existing index, update the replica settings:

```bash
# Update the replica count on the existing index
kamal app exec "python -c \"
import asyncio
from app.elasticsearch.client import es

async def update_replicas():
    await es.indices.put_settings(
        index='btaa_geospatial_api',
        body={'index': {'number_of_replicas': 1}}
    )
    print('Replicas updated to 1')

asyncio.run(update_replicas())
\""
```

**Alternative**: Use the Elasticsearch API directly:

```bash
# Via curl from the app container
kamal app exec "curl -X PUT 'http://btaa-geospatial-api-elasticsearch:9200/btaa_geospatial_api/_settings' -H 'Content-Type: application/json' -d '{\"index\": {\"number_of_replicas\": 1}}'"
```

### Step 5: Verify Configuration

Run the validation script to ensure everything is configured correctly:

```bash
# Validate production settings
kamal app exec "python scripts/validate_elasticsearch_production.py"

# Check Elasticsearch health
kamal app exec "python scripts/check_elasticsearch_health.py"
```

### Step 6: Verify Ulimits

Check that ulimits are properly set in the Elasticsearch container:

```bash
# Check ulimits inside the ES container
kamal accessory exec elasticsearch "ulimit -n"

# Should show: 65536
```

### Step 7: Test the Changes

```bash
# Check cluster health
kamal accessory exec elasticsearch "curl -s http://localhost:9200/_cluster/health?pretty"

# Check index settings
kamal accessory exec elasticsearch "curl -s http://localhost:9200/btaa_geospatial_api/_settings?pretty | grep -A 2 number_of_replicas"

# Check disk watermarks
kamal accessory exec elasticsearch "curl -s http://localhost:9200/_cluster/settings?include_defaults=true | grep -i watermark"
```

## Complete Deployment Command Sequence

Here's the complete sequence in one go:

```bash
# 1. Deploy application with new code
kamal deploy

# 2. Update Elasticsearch accessory (applies new config)
kamal accessory remove elasticsearch
kamal accessory boot elasticsearch

# 3. Wait for Elasticsearch to be ready (30-60 seconds)
sleep 60

# 4. Update existing index replicas
kamal app exec "python -c \"
import asyncio
from app.elasticsearch.client import es

async def update():
    await es.indices.put_settings(
        index='btaa_geospatial_api',
        body={'index': {'number_of_replicas': 1}}
    )
    print('✓ Replicas updated')

asyncio.run(update())
\""

# 5. Validate configuration
kamal app exec "python scripts/validate_elasticsearch_production.py"

# 6. Verify ulimits
kamal accessory exec elasticsearch "ulimit -n"
```

## Troubleshooting

### Elasticsearch Won't Start

If Elasticsearch fails to start after the changes:

```bash
# Check logs
kamal accessory logs elasticsearch

# Common issues:
# - Ulimits not applied: Check host system limits
# - Memory issues: Verify ES_JAVA_OPTS settings
# - Disk space: Check available disk space
```

### Index Replica Update Fails

If updating replicas fails (common in single-node clusters):

```bash
# Check cluster status
kamal accessory exec elasticsearch "curl -s http://localhost:9200/_cluster/health?pretty"

# In single-node clusters, replicas may show as unassigned (YELLOW status)
# This is expected and not a problem - replicas will be assigned if you add nodes
```

### "Too Many Open Files" Still Occurs

If you still see file descriptor errors:

```bash
# 1. Verify ulimits in container
kamal accessory exec elasticsearch "ulimit -n"

# 2. Check system limits on host
kamal ssh "ulimit -n"

# 3. Verify ES client connection pooling
kamal app exec "python -c 'from app.elasticsearch.client import es; print(es.transport.maxsize)'"
```

## Post-Deployment Checklist

- [ ] Application deployed with new code
- [ ] Elasticsearch accessory restarted with new config
- [ ] Ulimits verified (should be 65536)
- [ ] Index replicas updated to 1
- [ ] Validation script passes
- [ ] Health check shows GREEN or YELLOW (YELLOW is OK in single-node with replicas)
- [ ] No "too many open files" errors in logs
- [ ] Backup repository can be created (test with backup script)

## Next Steps

After deployment:

1. **Set up automated backups**:
   ```bash
   # Test backup creation
   kamal app exec "python scripts/backup_elasticsearch.py --create"
   
   # Set up cron job for daily backups (on server)
   ```

2. **Monitor Elasticsearch**:
   ```bash
   # Regular health checks
   kamal app exec "python scripts/check_elasticsearch_health.py"
   ```

3. **Review logs periodically**:
   ```bash
   kamal accessory logs elasticsearch --tail 100
   ```

