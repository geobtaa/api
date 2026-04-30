# VM memory recovery runbook

Use this when a Kamal host is memory overloaded, swapping heavily, or stuck after a
large cache-priming job. The goal is to stop the memory producer first, then free
recoverable cache memory, then restart services only as needed.

Examples below use `dev1`. Substitute the destination you are recovering.

## 1. Confirm the host and lock state

```bash
kamal lock status -d dev1
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'hostname; uptime'
```

If Kamal reports a deploy lock, do not release it blindly. First check whether a
real deploy or long-running Kamal command is still active on your workstation:

```bash
ps aux | grep -E 'kamal|prime_static_map_cache|prime_thumbnail_cache|prime_resource' | grep -v grep
```

If the lock is stale and no deploy should still be running, release it:

```bash
kamal lock release -d dev1
```

## 2. Stop the runaway producer

For static-map or visual-cache incidents, stop the primer before restarting
services. Otherwise the host may immediately refill Redis or swap again.

```bash
kamal app exec -d dev1 --roles web --reuse "bash -lc 'pgrep -af prime_static_map_cache.py || true'"
kamal app exec -d dev1 --roles web --reuse "bash -lc 'pkill -f prime_static_map_cache.py || true'"
```

Use the same pattern for other known primers:

```bash
kamal app exec -d dev1 --roles web --reuse "bash -lc 'pkill -f prime_thumbnail_cache.py || true'"
kamal app exec -d dev1 --roles web --reuse "bash -lc 'pkill -f prime_resource_representation_cache.py || true'"
```

## 3. Measure memory, swap, and container pressure

```bash
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; swapon --show; docker stats --no-stream'
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'vmstat 1 10'
```

Healthy enough to proceed:

- `free -h` shows several GiB available.
- `vmstat` columns `si` and `so` are mostly `0`.
- `swpd` is flat or shrinking.
- `docker stats` does not show Redis or Elasticsearch growing rapidly.

Still unstable:

- `si` or `so` keep showing non-zero values.
- `swpd` is increasing.
- `wa` is elevated, especially above roughly `5%`.
- Redis logs or app logs show `Redis is loading the dataset in memory`.

## 4. Free Redis binary-cache pressure first

Redis DB 1 stores binary image/static-map bodies. Those bytes are recoverable from
durable generated visual asset rows in Postgres or from regeneration. Prefer
clearing DB 1 over flushing DB 0, because DB 0 contains endpoint cache data,
aliases, queues, and other application keys.

```bash
kamal accessory exec -d dev1 redis "sh -lc 'REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli -h btaa-geospatial-api-redis -n 1 FLUSHDB ASYNC'"
kamal accessory exec -d dev1 redis "sh -lc 'REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli -h btaa-geospatial-api-redis MEMORY PURGE || true'"
```

Check Redis memory after the purge:

```bash
kamal accessory exec -d dev1 redis "sh -lc 'REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli -h btaa-geospatial-api-redis INFO memory | egrep \"used_memory_human|used_memory_peak_human|mem_fragmentation_ratio\"'"
```

If Redis is still loading, unresponsive, or holding too much memory, reboot the
accessory:

```bash
kamal accessory reboot -d dev1 redis
```

If Redis restarts and reloads the same giant persisted dataset, stop Redis and
quarantine the persisted cache files so the accessory starts empty. This clears
Redis cache and queue state, but it does not delete Postgres durable generated
asset rows or resource representations.

```bash
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'docker stop btaa-geospatial-api-redis || true'
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'docker run --rm -v /var/lib/btaa-geospatial-api:/host redis:7.4.6-alpine sh -lc '"'"'set -eu; dest="/host/redis-quarantine-$(date +%Y%m%d%H%M%S)"; mkdir -p "$dest"; for p in /host/redis/* /host/redis/.[!.]* /host/redis/..?*; do [ -e "$p" ] && mv "$p" "$dest"/; done; echo "Redis data moved to $dest"; ls -lah /host/redis "$dest"'"'"''
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'docker start btaa-geospatial-api-redis'
```

## 5. Reboot Elasticsearch only if pressure remains

Elasticsearch can temporarily consume CPU and disk I/O while recovering. If
Redis is calm but the host is still swapping or Elasticsearch is unhealthy,
reboot it:

```bash
kamal accessory reboot -d dev1 elasticsearch
```

Then check cluster health:

```bash
kamal accessory exec -d dev1 elasticsearch "curl -s http://localhost:9200/_cluster/health?pretty"
```

## 6. Restart app containers if swapped pages remain hot

Kamal has `accessory reboot`, but it does not have `kamal app reboot`. Restart
the app containers with stop and boot:

```bash
kamal app stop -d dev1
kamal app boot -d dev1
```

Use this after stopping the runaway producer and calming Redis/Elasticsearch,
not as the first recovery step.

## 7. Clear swap only when RAM is safe

Only do this when `free -h` shows enough available RAM to hold the current swap
usage. Clearing swap too early can make an overloaded host worse.

Use an SSH user with sudo rights. This may be different from the Kamal deploy
user.

```bash
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; swapon --show'
SUDO_SSH_USER=lars7423
ssh -t "$SUDO_SSH_USER@$KAMAL_HOST" 'sudo swapoff -a && sudo swapon -a'
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; vmstat 1 10'
```

## 8. Post-recovery cache priming rules

Do not rerun the old full static-map primer after a Redis OOM or swap incident.
Full-corpus Redis asset-body hydration can exceed a 32 GiB VM once static maps,
thumbnails, Elasticsearch, Postgres, workers, and OS cache are all accounted for.

Safe full static-map priming should warm durable links and aliases only:

```bash
make kamal-prime-static-map-cache KAMAL_DEST=dev1
```

Only hydrate image bodies into Redis for a small hotset:

```bash
make kamal-prime-static-map-cache KAMAL_DEST=dev1 PRIME_LIMIT=500 PRIME_STATIC_MAP_HYDRATE_ASSETS=1
make kamal-prime-static-map-cache KAMAL_DEST=dev1 RESOURCE_IDS="b1g_PJxxfKgpqpUT b1g_abc123" PRIME_STATIC_MAP_HYDRATE_ASSETS=1
```

The static-map primer refuses full-corpus Redis body hydration unless
`PRIME_ALLOW_FULL_HYDRATION=1` is also set. Do not use that override on a 32 GiB
host unless Redis DB 1 has been explicitly sized for the full image-body cache.
Kamal environments also set `VISUAL_ASSET_CACHE_TTL_SECONDS=604800`, so Redis
keeps recently used visual bodies hot while cold bodies expire back to the
durable Postgres store. Redis is also capped by `REDIS_MAXMEMORY` (default
`12gb`) with `volatile-lru` eviction, which should turn cache overgrowth into
evictions instead of host-wide memory exhaustion.

Before restarting any large priming job, confirm the host is stable:

```bash
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; vmstat 1 10; docker stats --no-stream'
```

## Fast emergency sequence

Use this when the host is already in trouble and you need the shortest safe path:

```bash
kamal lock status -d dev1
kamal app exec -d dev1 --roles web --reuse "bash -lc 'pkill -f prime_static_map_cache.py || true'"
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; swapon --show; docker stats --no-stream'
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'vmstat 1 10'
kamal accessory exec -d dev1 redis "sh -lc 'REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli -h btaa-geospatial-api-redis -n 1 FLUSHDB ASYNC'"
kamal accessory exec -d dev1 redis "sh -lc 'REDISCLI_AUTH=\"$REDIS_PASSWORD\" redis-cli -h btaa-geospatial-api-redis MEMORY PURGE || true'"
kamal accessory reboot -d dev1 redis
kamal accessory reboot -d dev1 elasticsearch
ssh "$KAMAL_SSH_USER@$KAMAL_HOST" 'free -h; vmstat 1 10; docker stats --no-stream'
```

If Kamal commands are blocked by a stale lock and you have confirmed no deploy
is active:

```bash
kamal lock release -d dev1
```
