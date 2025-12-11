# Fixing "Too Many Open Files" Issue in Docker Desktop

## Problem
Docker containers are hitting file descriptor limits, causing:
- Elasticsearch: "Too many open files" errors
- PostgreSQL/ParadeDB: "out of file descriptors" errors
- Uvicorn reloader: File watching failures

## Root Cause
Docker Desktop on macOS runs in a Linux VM that has default file descriptor limits. When uvicorn's reloader watches too many files, it exhausts these limits.

## Solutions Applied

### 1. Disabled Auto-Reload (Temporary Fix)
Removed `--reload` from uvicorn command in `docker-compose.yml` to stop file watching.

**To manually restart after code changes:**
```bash
docker-compose restart api
```

### 2. Added Ulimits to Containers
Added file descriptor limits to containers in `docker-compose.yml`:
- API container: 65536
- Elasticsearch: 65536  
- ParadeDB: 65536

### 3. Created .watchfilesignore
Created `.watchfilesignore` file to exclude large directories if reload is re-enabled.

## Permanent Fix: Increase Docker Desktop VM Limits

### Option A: Restart Docker Desktop (Quick Fix)
1. Quit Docker Desktop completely
2. Restart Docker Desktop
3. Run `docker-compose up -d`

### Option B: Configure Docker Desktop VM Limits (Recommended)
1. Open Docker Desktop
2. Go to Settings → Resources → Advanced
3. Increase file descriptor limits if available
4. Or edit Docker Desktop's VM configuration directly

### Option C: Use Docker Desktop's WSL2 Backend (if on Windows)
WSL2 typically has higher default limits.

## Re-enabling Auto-Reload (After Fix)

If you want to re-enable auto-reload after fixing the VM limits:

```yaml
command: ["uvicorn","main:app","--host","0.0.0.0","--port","8000","--reload","--log-level","debug","--reload-dir","/app/app","--reload-dir","/app/db","--reload-dir","/app/main.py"]
```

This limits watching to only the application code directories.

## Current Status
- ✅ Auto-reload disabled (manual restart required)
- ✅ Ulimits configured in docker-compose.yml
- ⚠️ Docker Desktop VM may need restart
- ⚠️ System may need time to release file descriptors

