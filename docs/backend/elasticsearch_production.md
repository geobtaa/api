# Elasticsearch Production Configuration Guide

This document covers Elasticsearch production configuration, high availability, backup strategies, and scaling considerations for the BTAA Geospatial API.

## Current Production Setup

The Elasticsearch deployment uses:
- **Version**: 9.0.0
- **Deployment**: Single-node cluster (via Kamal)
- **Memory**: 2GB heap (configurable)
- **Replicas**: 1 (for fault tolerance)
- **Shards**: 1

## Server Requirements

### Minimum Requirements
- **RAM**: 8GB total (4GB for ES container, 4GB for OS and other services)
- **CPU**: 2+ cores
- **Disk**: 50GB+ SSD recommended
- **Network**: Stable connection for backups

### Recommended for Production
- **RAM**: 16GB+ total (4-8GB for ES)
- **CPU**: 4+ cores
- **Disk**: 100GB+ SSD with fast I/O
- **Network**: Low-latency connection

### Ulimits Configuration

Elasticsearch requires high file descriptor limits (65536+). **Note**: Kamal doesn't support `ulimits` in accessories configuration, so we need to configure them at the host system level.

**Option 1: Configure Docker daemon (Recommended)**

On your Kamal server, edit `/etc/docker/daemon.json`:

```json
{
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  }
}
```

Then restart Docker:
```bash
sudo systemctl restart docker
```

**Option 2: Use the setup script**

```bash
# Copy the script to the server
kamal ssh
# Then run:
bash <(curl -s https://raw.githubusercontent.com/your-repo/scripts/setup_elasticsearch_ulimits.sh)
# Or manually copy and run scripts/setup_elasticsearch_ulimits.sh
```

**Option 3: Configure system limits**

Add to `/etc/security/limits.conf`:
```
* soft nofile 65536
* hard nofile 65536
```

**Verify ulimits are applied:**
```bash
kamal accessory exec elasticsearch "ulimit -n"  # Should show 65536
```

**If you still see "Too many open files" errors:**
1. Verify ulimits: `kamal accessory exec elasticsearch "ulimit -n"`
2. Check system-level limits on the host
3. Ensure the ES client has connection pooling configured (maxsize=25)
4. Restart the Elasticsearch container after setting ulimits

## Configuration Details

### Memory Settings

Current configuration in `config/deploy.yml`:
```yaml
ES_JAVA_OPTS: "-Xms2g -Xmx2g"
```

This allocates 2GB heap. For production workloads:
- **2GB**: Minimum for small to medium datasets
- **4GB**: Recommended for better performance
- **8GB**: For large datasets or high query volumes

**Note**: Don't allocate more than 50% of available RAM to ES heap. Leave memory for the OS and other processes.

### Disk Watermarks

Disk watermarks prevent the cluster from running out of disk space:
```yaml
cluster.routing.allocation.disk.watermark.low: "85%"
cluster.routing.allocation.disk.watermark.high: "90%"
cluster.routing.allocation.disk.watermark.flood_stage: "95%"
```

- **Low (85%)**: ES starts moving shards away from nodes with low disk
- **High (90%)**: ES stops allocating new shards to nodes
- **Flood (95%)**: ES sets all indices to read-only

### Index Configuration

Index settings in `app/elasticsearch/mappings.py`:
```python
"settings": {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 1,  # Changed from 0 for fault tolerance
    }
}
```

**Replicas**: Set to 1 for fault tolerance. Even in a single-node cluster, replicas help with:
- Shard recovery
- Preparing for multi-node expansion
- Data redundancy

**Shards**: Currently 1 shard. Consider increasing if:
- Index size exceeds 50GB
- Query performance degrades
- You need better parallelization

### Connection Pooling

The ES client in `app/elasticsearch/client.py` uses connection pooling:
```python
es = AsyncElasticsearch(
    ...,
    maxsize=25,  # Maximum connections in pool
)
```

This prevents file descriptor exhaustion by limiting concurrent connections.

## High Availability

### Current Setup: Single-Node

The current deployment uses a single-node cluster. This is suitable for:
- Development and staging
- Small to medium production workloads
- Budget-constrained deployments

**Limitations**:
- No automatic failover
- Single point of failure
- Limited scalability

### Multi-Node Setup (Future)

For true high availability, consider a 3-node cluster:

```yaml
# Node 1 (master-eligible, data)
discovery.type: zen
node.roles: [master, data]
cluster.initial_master_nodes: ["node1", "node2", "node3"]

# Node 2 (master-eligible, data)
discovery.type: zen
node.roles: [master, data]
cluster.initial_master_nodes: ["node1", "node2", "node3"]

# Node 3 (master-eligible, data)
discovery.type: zen
node.roles: [master, data]
cluster.initial_master_nodes: ["node1", "node2", "node3"]
```

**Benefits**:
- Automatic failover
- Better query performance (parallelization)
- True fault tolerance

**Requirements**:
- 3+ servers or containers
- Network connectivity between nodes
- Shared configuration

## Backup and Disaster Recovery

### Backup Strategy

We use Elasticsearch snapshots for backups. The backup script is located at
`scripts/backup_elasticsearch.py`.

Production snapshots use the S3 repository configured by
`ELASTICSEARCH_SNAPSHOT_REPOSITORY_TYPE=s3`, `BACKUP_S3_BUCKET`, and the
`BACKUP_S3_PREFIX/prd/elasticsearch` base path. Local/dev environments keep the
filesystem repository default for manual testing, but scheduled backups are
gated by `BACKUP_ENABLED` and `KAMAL_DEST`. See
[disaster_recovery.md](disaster_recovery.md) for the current production
runbook.

#### Creating Backups

```bash
# Create a snapshot (auto-named with timestamp)
python scripts/backup_elasticsearch.py --create

# Create a scheduled production-gated snapshot and keep only the newest 3
python scripts/backup_elasticsearch.py --scheduled --create --wait --retain-count 3

# Create a named snapshot
python scripts/backup_elasticsearch.py --create --name my_backup

# Wait for completion
python scripts/backup_elasticsearch.py --create --wait
```

#### Listing Snapshots

```bash
# List all snapshots
python scripts/backup_elasticsearch.py --list

# Check status of specific snapshot
python scripts/backup_elasticsearch.py --status snapshot_name
```

#### Restoring from Backup

```bash
# Restore a snapshot (overwrites existing index)
python scripts/backup_elasticsearch.py --restore snapshot_name

# Restore to a different index name
python scripts/backup_elasticsearch.py --restore snapshot_name --restore-to new_index_name

# Wait for restore to complete
python scripts/backup_elasticsearch.py --restore snapshot_name --wait
```

#### Cleanup Old Backups

```bash
# Delete snapshots older than 7 days (default)
python scripts/backup_elasticsearch.py --cleanup

# Keep snapshots for 30 days
python scripts/backup_elasticsearch.py --cleanup --keep-days 30
```

### Backup Repository

The backup repository is automatically created on first use.

For local/dev filesystem snapshots, it is configured as:
- **Path**: `/usr/share/elasticsearch/backups` (inside container)
- **Type**: Filesystem (fs)
- **Compression**: Enabled

For S3 snapshots in production:
- **Bucket**: `BACKUP_S3_BUCKET`
- **Base path**: `BACKUP_S3_PREFIX/prd/elasticsearch`
- **Repository type**: `s3`
- **Retention**: count-based via `--retain-count 3`

**For filesystem Kamal testing**, ensure the backup directory is persisted:
```yaml
directories:
  - esdata:/usr/share/elasticsearch/data
  - esbackups:/usr/share/elasticsearch/backups  # Add this
```

### Backup Schedule

Current production backup schedule:
- **Daily**: Full snapshot at 5:45 AM America/Chicago.
- **Retention**: keep the latest 3 managed snapshots.

Cron entry:
```bash
45 5 * * * /opt/venv/bin/python3 /app/scripts/backup_elasticsearch.py --scheduled --create --wait --retain-count ${BACKUP_RETENTION_COUNT:-3}
```

### Disaster Recovery Procedure

1. **Stop the application** (prevent writes during restore)
2. **Delete or close the corrupted index**:
   ```bash
   kamal app exec "python -c 'from app.elasticsearch.client import es; import asyncio; asyncio.run(es.indices.delete(index=\"btaa_geospatial_api\"))'"
   ```
3. **Restore from snapshot**:
   ```bash
   kamal app exec "python scripts/backup_elasticsearch.py --restore snapshot_name --wait"
   ```
4. **Verify the restore**:
   ```bash
   kamal app exec "python scripts/check_elasticsearch_health.py"
   ```
5. **Restart the application**

## Monitoring and Maintenance

### Health Checks

The deployment includes a healthcheck in `config/deploy.yml`:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
  interval: 30s
  timeout: 10s
  retries: 5
```

### Monitoring Scripts

#### Health Check
```bash
# Comprehensive health check
python scripts/check_elasticsearch_health.py

# Via Kamal
kamal app exec "python scripts/check_elasticsearch_health.py"
```

#### Production Validation
```bash
# Validate production settings
python scripts/validate_elasticsearch_production.py

# Via Kamal
kamal app exec "python scripts/validate_elasticsearch_production.py"
```

### Key Metrics to Monitor

1. **Cluster Health**: Should be GREEN (or YELLOW in single-node with replicas)
2. **Disk Usage**: Keep below 85% (low watermark)
3. **Memory Usage**: Monitor JVM heap usage
4. **Query Performance**: Track slow queries
5. **Index Size**: Monitor growth rate

### Common Issues and Solutions

#### "Too Many Open Files" Error

**Symptoms**: Elasticsearch errors about file descriptors

**Solutions**:
1. Verify ulimits in `config/deploy.yml` (should be 65536)
2. Check ES client connection pooling (maxsize=25)
3. Verify system-level limits on host
4. Restart Elasticsearch container

#### Cluster Status YELLOW

**Symptoms**: Cluster health shows YELLOW status

**Causes**:
- Unassigned shards (common in single-node with replicas)
- Disk space issues
- Node failures

**Solutions**:
- In single-node: YELLOW is expected with replicas (replicas can't be assigned)
- Check disk space
- Verify all nodes are running

#### Slow Query Performance

**Symptoms**: Queries take too long

**Solutions**:
1. Check index size (consider splitting into more shards)
2. Review query patterns (use filters, not queries where possible)
3. Increase memory allocation
4. Check for resource contention

#### Out of Memory

**Symptoms**: ES crashes or becomes unresponsive

**Solutions**:
1. Increase heap size (if resources allow)
2. Reduce index refresh interval
3. Optimize queries
4. Consider adding more nodes

## Scaling Considerations

### When to Scale

Consider scaling when:
- Index size exceeds 50GB per shard
- Query response times degrade
- Memory usage consistently high (>80%)
- Disk I/O becomes a bottleneck

### Scaling Options

1. **Vertical Scaling** (increase resources):
   - Increase heap size
   - Add more CPU
   - Use faster storage (SSD)

2. **Horizontal Scaling** (add nodes):
   - Deploy multi-node cluster
   - Increase number of shards
   - Distribute load across nodes

3. **Index Optimization**:
   - Adjust refresh interval
   - Optimize mappings
   - Use index aliases for zero-downtime updates

### Index Sharding Strategy

Current: 1 shard, 1 replica

**Guidelines**:
- **Small index (<10GB)**: 1 shard is fine
- **Medium index (10-50GB)**: 2-3 shards
- **Large index (>50GB)**: 5+ shards

**Note**: Once an index is created, you cannot change the number of shards. Plan ahead or use index aliases with reindexing.

## Performance Tuning

### Index Settings

Consider these settings for better performance:

```python
"settings": {
    "index": {
        "number_of_shards": 1,
        "number_of_replicas": 1,
        "refresh_interval": "30s",  # Reduce refresh frequency
        "number_of_routing_shards": 1,  # For future scaling
    }
}
```

### Query Optimization

- Use **filters** instead of **queries** where possible (filters are cached)
- Avoid wildcard queries at the start of terms
- Use `_source` filtering to reduce data transfer
- Consider using `search_after` for deep pagination instead of `from/size`

### Memory Optimization

- Set `indices.breaker.total.limit` to 70% of heap
- Monitor field data cache usage
- Use `doc_values: true` for aggregations (default in ES 2.0+)

## Security Considerations

### Current Setup

The production setup has security disabled for simplicity:
```yaml
xpack.security.enabled: "false"
```

### Production Security (Recommended)

For production, enable security:
```yaml
xpack.security.enabled: "true"
xpack.security.transport.ssl.enabled: "true"
```

This requires:
- SSL/TLS certificates
- User authentication
- Role-based access control
- Updated client configuration

## Troubleshooting

### Accessing Elasticsearch

```bash
# Via Kamal
kamal accessory exec elasticsearch "curl http://localhost:9200/_cluster/health"

# View logs
kamal accessory logs elasticsearch

# Restart
kamal accessory restart elasticsearch
```

### Common Commands

```bash
# Cluster health
curl http://localhost:9200/_cluster/health?pretty

# Index stats
curl http://localhost:9200/btaa_geospatial_api/_stats?pretty

# Node info
curl http://localhost:9200/_nodes?pretty

# Index settings
curl http://localhost:9200/btaa_geospatial_api/_settings?pretty
```

## References

- [Elasticsearch Production Deployment](https://www.elastic.co/guide/en/elasticsearch/reference/current/deploy.html)
- [Elasticsearch Snapshot and Restore](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html)
- [Elasticsearch Index Settings](https://www.elastic.co/guide/en/elasticsearch/reference/current/index-modules.html)
- [Elasticsearch Performance Tuning](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-search-speed.html)
