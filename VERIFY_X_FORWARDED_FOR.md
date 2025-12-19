# How to Verify X-Forwarded-For Header

This guide shows several methods to verify that the `X-Forwarded-For` header is being set correctly by nginx and received by the API.

## Method 1: Check API Logs for IP Whitelist Warnings

The API logs warnings when an IP restriction fails. If nginx is setting `X-Forwarded-For` correctly, you should see the correct IP in the logs.

**Steps:**

1. Make sure you have an API key with IP restrictions (e.g., `allowed_ips: ["127.0.0.1"]`)
2. Make a request through nginx (port 8080) with that API key
3. Check the API logs:

```bash
docker compose logs api --tail=50 | grep -i "IP\|whitelist\|forwarded"
```

**Expected output when working correctly:**
- If IP matches: No warnings, request succeeds
- If IP doesn't match: You'll see: `API key X rejected: IP Y not in whitelist. Allowed IPs: [...]`

**Example:**
```bash
# Request through nginx with IP-restricted API key
curl "http://localhost:8080/api/v1/search?q=test&api_key=your-key-here"

# Check logs
docker compose logs api --tail=100 | grep "IP\|whitelist"
```

## Method 2: Compare Direct API vs Nginx Proxy

Make the same request directly to the API (port 8000) and through nginx (port 8080), then compare what IP the API sees.

**Steps:**

1. Make request directly to API (bypasses nginx):
```bash
curl "http://localhost:8000/api/v1/search?q=test&api_key=your-key-here"
```

2. Make the same request through nginx:
```bash
curl "http://localhost:8080/api/v1/search?q=test&api_key=your-key-here"
```

3. Check logs for both:
```bash
docker compose logs api --tail=100
```

**Expected behavior:**
- Direct (port 8000): API sees Docker bridge IP (e.g., `172.18.0.1`) or connection refused
- Through nginx (port 8080): API sees `127.0.0.1` (from X-Forwarded-For header)

## Method 3: Check Database Logs for IP Address

The API logs all requests with IP addresses to the `api_usage_logs` table. Query this table to see what IPs are being recorded.

**Steps:**

1. Make a request through nginx:
```bash
curl "http://localhost:8080/api/v1/search?q=test"
```

2. Query the database to see the logged IP:
```bash
docker compose exec paradedb psql -U postgres -d btaa_geospatial_api -c "SELECT ip_address, endpoint, requested_at FROM api_usage_logs ORDER BY requested_at DESC LIMIT 5;"
```

**Expected result:**
- When accessing through nginx (port 8080): `ip_address` should be `127.0.0.1`
- When accessing directly (port 8000): `ip_address` would be the Docker bridge IP

## Method 4: Use curl to Inspect Headers

Use curl's verbose mode to see what headers are being sent and received.

**Steps:**

1. Check what headers nginx receives from curl:
```bash
curl -v "http://localhost:8080/api/v1/search?q=test" 2>&1 | grep -i "forwarded\|x-real"
```

2. Alternatively, use curl to send a custom X-Forwarded-For header to test:
```bash
curl -H "X-Forwarded-For: 192.168.1.100" "http://localhost:8080/api/v1/search?q=test"
```

Then check logs to see if the API received that IP:
```bash
docker compose logs api --tail=50 | grep "192.168.1.100"
```

## Method 5: Enable Debug Logging

Enable debug logging in the API to see detailed IP extraction information.

**Steps:**

1. The API already has debug logging for rate limiting. Check if LOG_LEVEL is set to DEBUG in docker-compose.yml (it should be).

2. Make a request through nginx:
```bash
curl "http://localhost:8080/api/v1/search?q=test"
```

3. Check for debug messages:
```bash
docker compose logs api --tail=100 | grep -i "debug\|extract\|forwarded\|IP"
```

## Method 6: Test with IP-Whitelisted API Key

The most practical test: use an API key with IP restrictions and verify it works.

**Steps:**

1. Create/update an API key with `allowed_ips: ["127.0.0.1"]`

2. Test request through nginx (should work):
```bash
curl "http://localhost:8080/api/v1/search?q=test&api_key=your-key-with-ip-restriction"
```

3. Check logs - should see no IP restriction warnings:
```bash
docker compose logs api --tail=50 | grep -i "rejected\|whitelist"
```

**If it works correctly:**
- No warnings in logs
- Request succeeds with 200 status

**If X-Forwarded-For is NOT working:**
- You'll see: `API key X rejected: IP 172.18.0.1 not in whitelist. Allowed IPs: ['127.0.0.1']`
- Request might fail or fall back to anonymous tier

## Quick Verification Script

Here's a quick one-liner to verify X-Forwarded-For is working:

```bash
# Test through nginx and check what IP was logged
curl -s "http://localhost:8080/api/v1/search?q=test" > /dev/null && \
docker compose exec paradedb psql -U postgres -d btaa_geospatial_api -t -c \
  "SELECT ip_address FROM api_usage_logs ORDER BY requested_at DESC LIMIT 1;"
```

**Expected output:** `172.18.0.1` (Docker bridge IP - this confirms X-Forwarded-For is working)

**Note:** In Docker, requests from `localhost` appear as `172.18.0.1` to nginx (the Docker bridge IP), not `127.0.0.1`. This is expected behavior. For IP whitelisting in local development, use `172.18.0.1` in your `allowed_ips`.

## Troubleshooting

**If X-Forwarded-For is not being set:**

1. Check nginx is running:
```bash
docker compose ps nginx
```

2. Check nginx logs:
```bash
docker compose logs nginx --tail=50
```

3. Verify nginx config is mounted correctly:
```bash
docker compose exec nginx cat /etc/nginx/conf.d/default.conf
```

4. Test nginx connectivity:
```bash
curl -v http://localhost:8080/health
```

