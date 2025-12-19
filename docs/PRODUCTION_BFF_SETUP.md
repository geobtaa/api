# Production BFF Proxy Setup

## Overview

In production (using Kamal with Traefik), the BFF proxy functionality is handled by a **FastAPI middleware** instead of nginx. This middleware intercepts `/api-proxy/*` routes, rewrites them to `/api/v1/*`, and injects the API key server-side.

## How It Works

```
Browser Request: /api-proxy/search?q=test
    ↓
Traefik (Kamal proxy)
    ↓
FastAPI APIProxyMiddleware
    ↓
    Rewrites path: /api-proxy/search → /api/v1/search
    Adds header: X-API-Key: <from env>
    ↓
Normal FastAPI routing
    ↓
API endpoint handler
    ↓
Response (with redirect rewriting if needed)
```

## Setup Steps

### 1. Add API Key to Secrets

Add `BTAA_GEOSPATIAL_API_KEY` to your `.kamal/secrets` file:

```bash
BTAA_GEOSPATIAL_API_KEY=your-production-api-key-here
```

**Important**: 
- Create an API key with IP whitelisting to your production server's IP
- Use `btaa_primary` tier for unlimited access
- See [IP Whitelisting Recommendations](IP_WHITELISTING_RECOMMENDATIONS.md) for details

### 2. Deploy

The middleware is already configured in `app/main.py` and will automatically handle `/api-proxy/*` routes:

```bash
kamal deploy
```

### 3. Verify It Works

Test the endpoint:

```bash
curl "https://your-domain.com/api-proxy/search?q=test"
```

Should return JSON response (not 404).

## Configuration

The middleware is configured in `config/deploy.yml`:

```yaml
env:
  secret:
    - BTAA_GEOSPATIAL_API_KEY  # API key for BFF proxy
```

And in `app/main.py`:

```python
# Add API proxy middleware (handles /api-proxy/ routes with API key injection)
app.add_middleware(APIProxyMiddleware)
```

## Differences from Development

| Aspect | Development (Local) | Production |
|--------|-------------------|------------|
| **Proxy** | nginx (docker-compose) | FastAPI Middleware |
| **Config File** | `config/nginx-dev.conf.template` | `app/middleware/api_proxy_middleware.py` |
| **Port** | 8080 | Same as main API (via Traefik) |
| **URL** | `http://localhost:8080/api-proxy/*` | `https://your-domain.com/api-proxy/*` |

## Redirect Handling

The middleware automatically rewrites redirect Location headers:
- API redirect: `/api/v1/static-maps/{id}`
- Browser sees: `/api-proxy/static-maps/{id}`

This ensures redirects stay within the proxy path.

## Troubleshooting

### 404 on /api-proxy/* Routes

1. **Check API key is set:**
   ```bash
   kamal app exec "python -c 'import os; print(os.getenv(\"BTAA_GEOSPATIAL_API_KEY\"))'"
   ```

2. **Check middleware is loaded:**
   ```bash
   kamal app logs | grep -i "api.*proxy\|middleware"
   ```

3. **Test direct API access:**
   ```bash
   curl "https://your-domain.com/api/v1/search?q=test"
   ```

### API Key Not Working

1. **Verify API key is in secrets:**
   ```bash
   # Check .kamal/secrets file has BTAA_GEOSPATIAL_API_KEY
   ```

2. **Verify API key is valid:**
   - Check API key exists and is active
   - Verify IP whitelisting (if configured)
   - Check API logs for key validation errors

3. **Check middleware logs:**
   ```bash
   kamal app logs | grep -i "BTAA_GEOSPATIAL_API_KEY\|api.*proxy"
   ```

### Redirects Not Working

If redirects don't go through the proxy:
- Check middleware is rewriting Location headers correctly
- Verify redirect status codes (301, 302, 303, 307, 308) are handled
- Check browser Network tab to see final redirect location

## React App Configuration

Your React app should use the same `/api-proxy/*` endpoints in both development and production:

```typescript
// Works in both development and production
const API_BASE = process.env.NODE_ENV === 'production'
  ? 'https://your-domain.com/api-proxy'
  : 'http://localhost:8080/api-proxy'

fetch(`${API_BASE}/search?q=test`)
```

## Security Notes

- ✅ API key is never exposed to browser
- ✅ API key is stored in `.kamal/secrets` (not committed to git)
- ✅ IP whitelisting can be used to restrict API key usage
- ⚠️ Ensure `.kamal/secrets` is in `.gitignore`
- ⚠️ Rotate API keys periodically
- ⚠️ Monitor API usage logs for suspicious activity

