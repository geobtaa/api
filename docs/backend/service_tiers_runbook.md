## Service Tiers & Rate Limiting Runbook

This document outlines the operational steps to enable and monitor **service tiers**, **API keys**, and **rate limiting** for the BTAA Geospatial API.

For the broader analytics architecture, event taxonomy, retention model, and extension guidelines, see [Analytics Program](analytics_program.md).

### 1. One-time setup per environment

- **Ensure database migrations have been run:**

  ```bash
  .venv/bin/python scripts/run_migrations.py
  ```

  This will:

  - Create the `api_service_tiers`, `api_keys`, `analytics_api_usage_logs`, `analytics_searches`, `analytics_search_impressions`, and `analytics_events` tables.
  - Create the daily analytics rollup tables `analytics_daily_api_usage_metrics`, `analytics_daily_search_metrics`, `analytics_daily_resource_metrics`, and the `analytics_maintenance_state` checkpoint table.
  - Convert raw analytics tables to monthly partitions when needed.
  - Seed the default service tiers (including `anonymous`, `general_registered`, and BTAA internal tiers).

- **Ensure Redis is available:**

  - In Docker-based environments, `docker-compose.yml` and `config/deploy.yml` already define a `redis`/`btaa-geospatial-api-redis` service.
  - Verify that the application containers can reach Redis at `REDIS_HOST:REDIS_PORT`.

### 2. Configure environment variables

Set (or verify) the following in your `.env`, deployment environment, or hosting platform:

```text
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=optional_password

RATE_LIMIT_ENABLED=true      # Enable/disable middleware enforcement
RATE_LIMIT_REDIS_DB=2        # Dedicated Redis DB for rate limiting

ANALYTICS_RETENTION_API_USAGE_DAYS=30
ANALYTICS_RETENTION_SEARCH_DAYS=90
ANALYTICS_RETENTION_IMPRESSION_DAYS=30
ANALYTICS_RETENTION_EVENT_DAYS=90
ANALYTICS_PARTITION_HISTORY_MONTHS=2
ANALYTICS_PARTITION_FUTURE_MONTHS=2
ANALYTICS_ROLLUP_MAX_DAYS_PER_RUN=31
```

For production:

- Use a strong `REDIS_PASSWORD` and restrict network access to the Redis instance.
- Keep `RATE_LIMIT_ENABLED=true` unless you have a compelling operational reason to disable it temporarily.

### 3. Create and manage API keys

1. **Set admin credentials** (already required for other admin endpoints):

   ```text
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=changeme
   ```

2. **Create an API key for a specific tier** using the admin endpoint:

   ```bash
   curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
     -X POST "https://your-host/api/v1/admin/api-keys" \
     -H "Content-Type: application/json" \
     -d '{"tier_name": "general_registered", "name": "Example client"}'
   ```

   - The response will include:
     - `api_key` – plaintext key (shown once; save it securely).
     - `key_id` – numeric identifier used for future updates/revocation.

3. **Update or revoke keys**:

   - Update tier or metadata:

     ```bash
     curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
       -X PATCH "https://your-host/api/v1/admin/api-keys/<key_id>" \
       -H "Content-Type: application/json" \
       -d '{"tier_name": "btaa_member_affiliated", "name": "Updated name", "is_active": true}'
     ```

   - Revoke (deactivate) a key:

     ```bash
     curl -u "$ADMIN_USERNAME:$ADMIN_PASSWORD" \
       -X DELETE "https://your-host/api/v1/admin/api-keys/<key_id>"
     ```

4. **List keys and tiers**:

   - `GET /api/v1/admin/api-keys` – inspect existing keys.
   - `GET /api/v1/admin/api-tiers` – verify tier names and rate limits.

### 4. Client integration checklist

When onboarding a new API client:

1. Decide which **tier** they belong to (`general_registered`, `btaa_member_primary`, etc.).
2. Create an API key for that tier using the admin endpoint.
3. Provide the client with:
   - Their API key.
   - Instructions to send it via:
     - `X-API-Key` header, or
     - `Authorization: Bearer <api_key>` header, or
     - `api_key=<api_key>` query parameter.
4. Communicate the tier’s **rate limit** and expected behavior on exceeding it (HTTP 429, `Retry-After`, `X-RateLimit-*` headers).

### 5. Monitoring and troubleshooting

- **Quick health checks:**
  - Confirm Redis is reachable and healthy (see existing Redis health checks in `docker-compose.yml` or `config/deploy.yml`).
  - Hit a public endpoint and inspect response headers for `X-RateLimit-*`.

- **Inspect API usage logs:**
  - API request analytics are queued to Celery and written asynchronously to `analytics_api_usage_logs`, with `tier_id` and optional `api_key_id`.
  - Product analytics beacons from the Geoportal are queued to Celery and written asynchronously to `analytics_searches`, `analytics_search_impressions`, and `analytics_events`.
  - Raw analytics now live in monthly partitions, and daily rollups are written to:
    - `analytics_daily_api_usage_metrics`
    - `analytics_daily_search_metrics`
    - `analytics_daily_resource_metrics`
  - Use SQL or your preferred BI tool to:
    - Track high-volume clients.
    - Identify frequent 429 responses.
    - Analyze traffic by tier.

- **Run storage maintenance manually if needed:**

  ```bash
  make analytics-maintenance
  make analytics-size-report
  ```

  - `analytics-maintenance` is safe to re-run. It pre-creates future partitions, rolls up completed days, and drops raw partitions only after the rollups have caught up.

- **Common failure modes:**
  - **Redis unavailable**:
    - Middleware logs a warning and allows traffic; rate limiting becomes “best effort” until Redis is restored.
  - **Celery broker/worker unavailable**:
    - API responses still succeed, but analytics request logs may be delayed or dropped until the queue path is healthy again.
  - **Missing tiers or keys**:
    - Re-run `scripts/run_migrations.py` to ensure tables & seed tiers exist.
    - Use `GET /api/v1/admin/api-tiers` to verify tier configuration.
  - **Postgres connection pressure under keyed load**:
    - Keep `API_KEY_TIER_CACHE_TTL_SECONDS` enabled so repeated requests with
      the same key do not need a database lookup before the unlimited-tier
      rate-limit skip can happen.
    - Keep `API_KEY_LAST_USED_UPDATE_INTERVAL_SECONDS` above zero so
      `api_keys.last_used_at` is not updated on every request.
    - Use `DB_POOL_MAX`, `SQLALCHEMY_ASYNC_POOL_SIZE`, and
      `SQLALCHEMY_ASYNC_MAX_OVERFLOW` to budget database clients across all
      API worker processes before increasing `WEB_UVICORN_WORKERS` or
      `WEB_INTERNAL_UVICORN_WORKERS`.

### 6. Changing tier policies

To adjust per-minute limits or descriptions:

1. Update `db/migrations/initialize_api_tiers.py` with the desired limits.
2. Apply the changes:
   - For new environments, run `scripts/run_migrations.py` as usual.
   - For existing environments, either:
     - Run the initializer script directly against the target DB, or
     - Apply equivalent `UPDATE` statements manually.
3. Communicate new limits to affected API clients.
