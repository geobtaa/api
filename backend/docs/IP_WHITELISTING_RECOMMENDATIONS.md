# IP Whitelisting Recommendations for geo.btaa.org

## Architecture Overview

- **Frontend**: `geo.btaa.org` (public website, accessible from anywhere)
- **API**: `api.geo.btaa.org` (should be protected from unlimited direct access)

## Recommended Approach: Server-Side API Calls with IP Whitelisting

### Setup Steps

1. **Create API Key for Frontend Server**
   ```bash
   POST /api/v1/admin/api-keys
   {
     "tier_name": "btaa_primary",
     "name": "geo.btaa.org Frontend Server",
     "allowed_ips": ["YOUR_FRONTEND_SERVER_IP"]
   }
   ```

2. **Frontend Server Configuration**
   - Frontend server makes API calls from server-side code (not browser)
   - Include API key in server-side requests (never expose it to browser)
   - Frontend server IP is whitelisted, so API accepts requests

3. **Result**
   - ✅ Users can browse `geo.btaa.org` normally
   - ✅ Frontend server gets unlimited API access (btaa_primary tier)
   - ✅ Direct API calls from user browsers are rejected (401) unless user has their own API key
   - ✅ Prevents abuse: users can't extract frontend's API key and use it from anywhere

### How It Works

```
User Browser (anywhere in world)
    ↓
geo.btaa.org (frontend server)
    ↓ (server-side API call with API key)
    ↓ (X-Forwarded-For: frontend-server-IP)
api.geo.btaa.org
    ↓ (checks: API key valid + IP in whitelist)
    ↓ (ALLOWED - unlimited requests)
API Response
```

If someone tries to directly call the API:
```
User Browser (tries direct API call)
    ↓ (X-Forwarded-For: user-real-IP)
api.geo.btaa.org
    ↓ (checks: API key valid BUT IP not in whitelist)
    ↓ (REJECTED - 401 Unauthorized)
```

## Alternative: Client-Side API Calls (Not Recommended for Production)

If your frontend makes API calls directly from the browser:

### Option A: No API Key (Recommended for Client-Side)
- Don't include an API key in client-side code
- Users automatically get `anonymous` tier (10 requests/minute)
- **Pros**: Secure, simple, prevents API key exposure
- **Cons**: Lower rate limit (10 req/min) - may be limiting for power users
- **Best for**: Public browsing, casual use

### Option B: Client-Side API Key (Not Recommended)
- Include API key in browser JavaScript
- **Pros**: Higher rate limits for users
- **Cons**: 
  - ❌ API key is exposed (anyone can view source and extract it)
  - ❌ Can't use IP whitelisting (would block all users)
  - ❌ Users can use extracted key from anywhere with high limits
  - ❌ Security risk: key can be abused

## Recommendation Summary

**For production frontend (`geo.btaa.org`):**

1. **Use server-side API calls** (Next.js API routes, Express backend, etc.)
2. **Create `btaa_primary` tier API key** with IP whitelist to frontend server IP only
3. **Never expose API key to browser** - keep it server-side only
4. **Users browse normally**, but can't directly abuse the API

**Why This Works:**
- Frontend server gets unlimited access (appropriate for main BTAA application)
- IP whitelisting prevents API key theft/abuse
- Users still get full frontend functionality
- Direct API access is properly restricted

## Finding Your Frontend Server IP

To get the IP address(es) to whitelist:

```bash
# If frontend is on same server as API
hostname -I

# If frontend is on different server, check its outbound IP
# You can also check API logs after making a test request:
docker compose logs api | grep "X-Forwarded-For" | tail -5
```

## Testing

After setting up IP whitelisting:

1. **Test from frontend server** - should work (unlimited requests)
2. **Test direct API call from your laptop** - should get 401 Unauthorized
3. **Test browsing geo.btaa.org** - should work normally

## Current Configuration

Based on your setup, you're using `btaa_primary` tier which has:
- **Tier**: `btaa_primary`
- **Rate Limit**: Unlimited
- **Intended for**: "The main BTAA Geoportal frontend application"

This is exactly right for your use case - just add IP whitelisting to restrict it to your frontend server.

