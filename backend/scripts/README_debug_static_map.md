# Static Map Debugging Guide

## Problem
The static map endpoint (`/resources/{id}/static-map`) may fail on servers with firewalls that block outbound HTTP traffic because it needs to fetch map tiles from external tile servers.

## Quick Diagnosis

Run the diagnostic script on your Kamal server:

```bash
# SSH into your server
kamal app exec -i "python scripts/debug_static_map.py"
```

Or if you have direct SSH access:

```bash
ssh your-server
cd /path/to/app
python scripts/debug_static_map.py
```

## What the Script Tests

1. **Import Check**: Verifies `py-staticmaps` is installed
2. **Network Connectivity**: Tests if the server can reach `basemaps.cartocdn.com` (the tile server)
3. **Map Generation**: Attempts to generate a test static map

## Expected Output

### If Network is Working:
```
✓ Successfully connected to tile server: HTTP 200, received X bytes
✓ Successfully generated static map: /path/to/map.png
```

### If Firewall is Blocking:
```
✗ Failed to connect to tile server: [Errno 61] Connection refused
✗ Network error rendering map: Connection timeout
```

## Solutions

### Option 1: Allow Outbound HTTP/HTTPS (Recommended)
Configure your firewall to allow outbound HTTP (port 80) and HTTPS (port 443) traffic to:
- `*.basemaps.cartocdn.com`
- `*.cartocdn.com`

### Option 2: Use a Proxy Server
If you must restrict outbound traffic, configure an HTTP proxy:

```python
# In your environment or config
import os
os.environ['HTTP_PROXY'] = 'http://your-proxy:8080'
os.environ['HTTPS_PROXY'] = 'http://your-proxy:8080'
```

### Option 3: Pre-generate Maps
Generate static maps on a machine with internet access and copy them to the server.

### Option 4: Use Offline Tile Cache
Set up a local tile server or cache tiles locally (more complex).

## Checking Celery Task Logs

If maps are generated via Celery tasks, check the worker logs:

```bash
# On your server
tail -f logs/celery.log | grep -i "static.*map\|network\|connection"
```

Look for errors like:
- `Connection refused`
- `Connection timeout`
- `Network unreachable`
- `Failed to render`

## Manual Network Test

Test connectivity directly from the server:

```bash
# Test DNS resolution
nslookup basemaps.cartocdn.com

# Test HTTP connection
curl -v http://a.basemaps.cartocdn.com/rastertiles/light_all/1/0/0.png

# Test with timeout
curl --max-time 10 http://a.basemaps.cartocdn.com/rastertiles/light_all/1/0/0.png
```

If these fail, it confirms the firewall is blocking outbound traffic.

