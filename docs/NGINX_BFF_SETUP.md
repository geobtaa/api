# Nginx BFF Proxy Setup

This document explains how to use the nginx reverse proxy as a Backend-for-Frontend (BFF) to securely proxy API requests with server-side API key injection.

## Architecture

```
React App (Browser)
    ↓
    ↓ fetch('/api-proxy/search?q=test')
    ↓ (NO API KEY in request)
    ↓
Nginx (localhost:8080)
    ↓
    ↓ Adds X-API-Key header server-side
    ↓ Proxies to http://api:8000/api/v1/search?q=test
    ↓
BTAA API
    ↓
    ↓ Validates API key + IP whitelist
    ↓
Response flows back
```

## Setup Steps

### 1. Add API Key to Environment

Add your API key to your `.env` file (create it if it doesn't exist):

```bash
BTAA_GEOSPATIAL_API_KEY=your-api-key-here
```

**Important**: 
- Never commit `.env` to git (it should be in `.gitignore`)
- Use different keys for development and production
- For production, create an API key with IP whitelisting to your nginx server's IP

### 2. Restart Nginx

After adding the API key, restart the nginx container:

```bash
docker compose restart nginx
```

Or rebuild everything:

```bash
docker compose up -d
```

### 3. Update Your React App

Change all API calls from:

```typescript
// OLD - Direct API call (exposes API key)
fetch('http://localhost:8000/api/v1/search?q=test', {
  headers: {
    'X-API-Key': 'your-key-here'  // ❌ Exposed in browser!
  }
})
```

To:

```typescript
// NEW - Through BFF proxy (API key hidden)
fetch('http://localhost:8080/api-proxy/search?q=test')
// ✅ No API key in request - added server-side by nginx
```

### 4. Verify It Works

**Test the proxy:**
```bash
# Should work (nginx adds API key server-side)
curl http://localhost:8080/api-proxy/search?q=test
```

**Check browser DevTools:**
1. Open your React app
2. Open DevTools → Network tab
3. Make an API request
4. Verify:
   - ✅ Request goes to `localhost:8080/api-proxy/*`
   - ✅ No `X-API-Key` header visible in request
   - ✅ Response is successful

**Check nginx logs:**
```bash
docker compose logs nginx --tail=20
```

**Check API logs:**
```bash
docker compose logs api --tail=20 | grep -i "api key\|tier"
```

## API Endpoints

### BFF Proxy Endpoint

- **URL Pattern**: `http://localhost:8080/api-proxy/{endpoint}`
- **Example**: `http://localhost:8080/api-proxy/search?q=test`
- **Behavior**: 
  - Automatically adds `X-API-Key` header server-side
  - Proxies to `http://api:8000/api/v1/{endpoint}`
  - Sets `X-Forwarded-For` header correctly

### Direct Proxy Endpoint (Backward Compatibility)

- **URL Pattern**: `http://localhost:8080/api/v1/{endpoint}`
- **Example**: `http://localhost:8080/api/v1/search?q=test`
- **Behavior**:
  - Does NOT add API key automatically
  - You can pass your own API key if needed
  - Useful for admin endpoints

## Production Setup

### 1. Create API Key with IP Whitelisting

Once your nginx server is deployed, get its outbound IP and create the API key:

```bash
curl -X POST https://api.geo.btaa.org/api/v1/admin/api-keys \
  -u admin:your-admin-password \
  -H "Content-Type: application/json" \
  -d '{
    "tier_name": "btaa_primary",
    "name": "geo.btaa.org Nginx BFF Proxy",
    "allowed_ips": ["YOUR_NGINX_SERVER_IP"]
  }'
```

**Finding your nginx server's IP:**

If nginx is on the same server as the API:
```bash
# On your server
curl ifconfig.me
```

Or check what IP the API sees:
1. Temporarily create API key without IP whitelisting
2. Make a test request through nginx
3. Check API logs or database:
```sql
SELECT ip_address FROM api_usage_logs ORDER BY requested_at DESC LIMIT 1;
```

### 2. Set Production Environment Variable

In your production environment (Kamal, Docker, etc.), set:

```bash
BTAA_GEOSPATIAL_API_KEY=your-production-api-key-with-ip-whitelist
```

### 3. Update React App for Production

Update your React app's API base URL:

```typescript
// Development
const API_BASE = 'http://localhost:8080/api-proxy'

// Production
const API_BASE = 'https://geo.btaa.org/api-proxy'  // or wherever nginx is hosted
```

## Troubleshooting

### API Key Not Working

1. **Check environment variable is set:**
   ```bash
   docker compose exec nginx env | grep BTAA_GEOSPATIAL_API_KEY
   ```

2. **Check nginx config was generated correctly:**
   ```bash
   docker compose exec nginx cat /etc/nginx/conf.d/default.conf | grep X-API-Key
   ```

3. **Check nginx logs for errors:**
   ```bash
   docker compose logs nginx
   ```

### 401 Unauthorized Errors

- **Development**: Make sure `BTAA_GEOSPATIAL_API_KEY` is set in `.env` file
- **Production**: 
  - Verify API key has IP whitelisting set correctly
  - Check that nginx server IP matches whitelisted IP
  - Verify API key is active and not revoked

### Requests Not Proxying

1. **Check nginx is running:**
   ```bash
   docker compose ps nginx
   ```

2. **Check nginx can reach API:**
   ```bash
   docker compose exec nginx wget -O- http://api:8000/health
   ```

3. **Check nginx config syntax:**
   ```bash
   docker compose exec nginx nginx -t
   ```

## Security Notes

- ✅ API key is never exposed to browser
- ✅ API key is stored in environment variables (not in code)
- ✅ IP whitelisting prevents key theft/abuse
- ✅ All requests are logged for monitoring
- ⚠️ Keep `.env` file secure and never commit it
- ⚠️ Rotate API keys periodically
- ⚠️ Monitor API usage logs for suspicious activity

## Summary

1. ✅ Add `BTAA_GEOSPATIAL_API_KEY` to `.env` file
2. ✅ Restart nginx: `docker compose restart nginx`
3. ✅ Update React app to use `/api-proxy/*` endpoints
4. ✅ Verify API key is not visible in browser DevTools
5. ✅ For production, create API key with IP whitelisting
6. ✅ Monitor and maintain

This setup gives you tight control over API access while keeping the API key secure and hidden from client-side code.

