# Backend-for-Frontend (BFF) Implementation Guide

## Architecture Overview

```
User Browser (anywhere)
    ↓
    ↓ HTTP requests (no API key exposed)
    ↓
Your Backend API (geo.btaa.org/api-proxy or similar)
    ↓
    ↓ Server-side API key (hidden from browser)
    ↓
    ↓ X-Forwarded-For: YOUR_BACKEND_SERVER_IP
    ↓
BTAA API (api.geo.btaa.org)
    ↓
    ↓ Checks: API key valid + IP whitelisted
    ↓
    ↓ ALLOWED (unlimited requests)
    ↓
Response flows back to React app
```

## Benefits

- ✅ API key never exposed to browser
- ✅ Can use IP whitelisting (backend server IP is known)
- ✅ Unlimited access for your backend
- ✅ Can add additional security (rate limiting, caching, etc.)
- ✅ Can modify/enhance responses before sending to frontend
- ✅ Can add analytics/logging

## Implementation Options

### Option A: Next.js API Routes (Recommended if using Next.js)

If your React app is Next.js, use API routes:

**File structure:**
```
your-react-app/
├── pages/
│   ├── api/
│   │   └── proxy/
│   │       └── [...path].ts  # Catch-all route
│   └── ...
├── .env.local                 # API key stored here
└── ...
```

**Example: `pages/api/proxy/[...path].ts`**

```typescript
import type { NextApiRequest, NextApiResponse } from 'next'

const BTAA_API_BASE = process.env.BTAA_API_URL || 'https://api.geo.btaa.org'
const BTAA_GEOSPATIAL_API_KEY = process.env.BTAA_GEOSPATIAL_API_KEY // Server-side only!

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  // Only allow GET requests (adjust as needed)
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  // Get the path from the catch-all route
  const path = req.query.path as string[]
  const apiPath = Array.isArray(path) ? path.join('/') : path

  // Forward query parameters
  const queryParams = new URLSearchParams(req.query as Record<string, string>)
  queryParams.delete('path') // Remove the path parameter
  
  const queryString = queryParams.toString()
  const url = `${BTAA_API_BASE}/api/v1/${apiPath}${queryString ? `?${queryString}` : ''}`

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-API-Key': BTAA_GEOSPATIAL_API_KEY!,
        'Accept': 'application/json',
        // Forward any other headers you need
      },
    })

    const data = await response.json()
    
    // Forward status and data
    res.status(response.status).json(data)
  } catch (error) {
    console.error('Proxy error:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
}
```

**Environment variables (`.env.local`):**
```bash
BTAA_API_URL=https://api.geo.btaa.org
BTAA_GEOSPATIAL_API_KEY=your-api-key-here
```

**React app usage:**
```typescript
// Instead of: fetch('https://api.geo.btaa.org/api/v1/search?q=test')
// Use:
fetch('/api/proxy/search?q=test')
```

### Option B: Express.js Backend (Standalone Node.js)

If you have a separate backend or want more control:

**File: `backend/proxy.js`**

```javascript
const express = require('express')
const router = express.Router()
const fetch = require('node-fetch')

const BTAA_API_BASE = process.env.BTAA_API_URL || 'https://api.geo.btaa.org'
const BTAA_GEOSPATIAL_API_KEY = process.env.BTAA_GEOSPATIAL_API_KEY

// Proxy all API requests
router.get('/api/*', async (req, res) => {
  // Get path after /api/
  const apiPath = req.path.replace('/api/', '')
  const url = `${BTAA_API_BASE}/api/v1/${apiPath}${req.url.includes('?') ? req.url.substring(req.url.indexOf('?')) : ''}`

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-API-Key': BTAA_GEOSPATIAL_API_KEY,
        'Accept': 'application/json',
      },
    })

    const data = await response.json()
    res.status(response.status).json(data)
  } catch (error) {
    console.error('Proxy error:', error)
    res.status(500).json({ error: 'Internal server error' })
  }
})

module.exports = router
```

**File: `backend/server.js`**

```javascript
const express = require('express')
const cors = require('cors')
const proxy = require('./proxy')

const app = express()
app.use(cors()) // Allow your React app's origin
app.use(proxy)

const PORT = process.env.PORT || 3001
app.listen(PORT, () => {
  console.log(`Backend proxy running on port ${PORT}`)
})
```

**Environment variables:**
```bash
BTAA_API_URL=https://api.geo.btaa.org
BTAA_GEOSPATIAL_API_KEY=your-api-key-here
```

### Option C: Nginx Reverse Proxy (If you prefer)

If you want to handle this at the infrastructure level:

**nginx config:**
```nginx
location /api-proxy/ {
    rewrite ^/api-proxy/(.*) /api/v1/$1 break;
    proxy_pass https://api.geo.btaa.org;
    proxy_set_header X-API-Key "your-api-key-here";
    proxy_set_header Host api.geo.btaa.org;
    proxy_set_header X-Forwarded-For $remote_addr;
}
```

Then React calls: `fetch('/api-proxy/search?q=test')`

## Setup Steps

### 1. Create API Key with IP Whitelisting

Once your backend is deployed, get its outbound IP address and create the API key:

```bash
# Create API key for backend server
curl -X POST https://api.geo.btaa.org/api/v1/admin/api-keys \
  -u admin:your-admin-password \
  -H "Content-Type: application/json" \
  -d '{
    "tier_name": "btaa_primary",
    "name": "geo.btaa.org Backend Proxy",
    "allowed_ips": ["YOUR_BACKEND_SERVER_IP"]
  }'
```

**Finding your backend server's IP:**

If your backend is on the same server as the React app:
```bash
# On your server
curl ifconfig.me
# or
hostname -I
```

If you need to check what IP the API sees:
1. Temporarily create API key without IP whitelisting
2. Make a test request from your backend
3. Check API logs or database:
```sql
SELECT ip_address FROM api_usage_logs ORDER BY requested_at DESC LIMIT 1;
```

### 2. Update React App to Use Proxy

Change all API calls from:
```typescript
// OLD (direct API calls)
fetch('https://api.geo.btaa.org/api/v1/search?q=test')
```

To:
```typescript
// NEW (through your backend proxy)
fetch('/api/proxy/search?q=test')  // Next.js
// or
fetch('https://geo.btaa.org/api-proxy/search?q=test')  // Express/nginx
```

### 3. Secure Your API Key

- ✅ Store API key in environment variables (never commit to git)
- ✅ Add `.env*` to `.gitignore`
- ✅ Use different keys for development/staging/production
- ✅ Rotate keys periodically
- ✅ Monitor API usage logs

### 4. Add Additional Security (Optional)

You can enhance the proxy with:

**Rate limiting per user:**
```typescript
// Track requests per IP in Redis or memory
const userRequests = new Map()
const MAX_REQUESTS_PER_MINUTE = 100

// Check rate limit before proxying
const userIP = req.headers['x-forwarded-for'] || req.socket.remoteAddress
// ... rate limit logic ...
```

**Request validation:**
```typescript
// Only allow certain endpoints
const allowedPaths = ['search', 'resources', 'suggest']
if (!allowedPaths.some(path => apiPath.startsWith(path))) {
  return res.status(403).json({ error: 'Endpoint not allowed' })
}
```

**Response caching:**
```typescript
// Cache responses for 5 minutes
const cache = new Map()
const cacheKey = `${apiPath}?${queryString}`
// ... caching logic ...
```

## Testing

1. **Test from your backend server:**
```bash
curl -H "X-API-Key: your-key" https://api.geo.btaa.org/api/v1/search?q=test
# Should work (unlimited)
```

2. **Test from your laptop:**
```bash
curl -H "X-API-Key: your-key" https://api.geo.btaa.org/api/v1/search?q=test
# Should fail (401) if IP whitelisting is working
```

3. **Test through your proxy:**
```bash
curl https://geo.btaa.org/api/proxy/search?q=test
# Should work (backend IP is whitelisted)
```

4. **Test from React app:**
- Open browser dev tools
- Check Network tab
- Verify API key is NOT in requests
- Verify requests go to your proxy, not directly to api.geo.btaa.org

## Deployment Considerations

### Development vs Production

**Development:**
- Use separate API key (can be without IP whitelisting for ease)
- Or use `127.0.0.1` / `localhost` if testing locally

**Production:**
- Use IP whitelisting (production backend server IP)
- Use `btaa_primary` tier for unlimited access
- Monitor usage logs

### Environment Variables

```bash
# .env.local (development)
BTAA_GEOSPATIAL_API_KEY=dev-key-here

# .env.production (production)
BTAA_GEOSPATIAL_API_KEY=prod-key-with-ip-whitelist-here
```

## Summary

1. ✅ Build backend proxy (Next.js API routes, Express, or nginx)
2. ✅ Store API key server-side in environment variables
3. ✅ Update React app to call proxy instead of API directly
4. ✅ Create API key with IP whitelisting to backend server IP
5. ✅ Test and verify API key is not exposed in browser
6. ✅ Deploy and monitor

This gives you tight control while maintaining unlimited access for legitimate users.

