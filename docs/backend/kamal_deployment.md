# Kamal Deployment Guide

## Current Production Stack

This deployment runs on `lib-btaageoapi-dev-app-01.oit.umn.edu` with:

**Application Containers:**
- **Web**: Single-host router + SSR + API (public port 8000 via Traefik)
- **Worker**: Celery worker for background tasks
- **Flower**: Celery monitoring UI (port 5555, internal)

**Accessories (Managed Services):**
- **ParadeDB 0.18.11**: PostgreSQL with extensions (pg_search, postgis, vector, pg_ivm)
- **Elasticsearch 9.0.0**: Search indexing
- **Redis 7.4.6-alpine**: Caching & Celery broker (password-protected)

**URL**: https://lib-btaageoapi-dev-app-01.oit.umn.edu

### Single-host routing behavior

This deployment serves both the SSR frontend and the API from the same hostname:

- **SSR UI**: `https://<host>/`
- **API**: `https://<host>/api/...` (e.g. `/api/v1/search`, `/api/docs`)

## Prerequisites

1. **Remote Server Requirements**:
   - Ubuntu 20.04+ or similar Linux distribution
   - Docker installed and running
   - SSH access with key-based authentication
   - Minimum 4GB RAM, 2 CPU cores
   - 50GB+ storage for databases

2. **Local Requirements**:
   - Kamal installed: `gem install kamal`
   - Docker registry account (Docker Hub, GHCR, etc.)
   - Domain name pointing to your server (for SSL)

## Step-by-Step Deployment

### 1. Configure Secrets

Create `.kamal/secrets` file with your sensitive data:

```bash
# Create the secrets directory
mkdir -p .kamal

# Create secrets file (don't commit this!)
cat > .kamal/secrets << 'EOF'
# Deployment configuration (environment-specific)
export KAMAL_HOST=your-server-hostname.example.com
export KAMAL_SSH_USER=your_ssh_username
export KAMAL_REGISTRY_USERNAME=your_github_username

# Registry password (GitHub Personal Access Token with packages:write)
KAMAL_REGISTRY_PASSWORD=your_github_token_here

# Redis password (required; used for caching + rate limiting + celery broker)
REDIS_PASSWORD=your_redis_password_here

# PostgreSQL password
POSTGRES_PASSWORD=your_postgres_password_here

# Database URL (will be interpolated by Kamal)
DATABASE_URL=postgresql+asyncpg://postgres:your_postgres_password_here@btaa-geospatial-api-paradedb:5432/btaa_geospatial_api

# Admin credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_admin_password_here

# OpenAI API credentials (for LLM features)
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-3.5-turbo

# API key used by the SSR server for server-side loaders (server-only; not exposed to browser)
BTAA_GEOSPATIAL_API_KEY=your_frontend_api_key_here
EOF

# Secure the file
chmod 600 .kamal/secrets
```

**Note**: Our `.kamal/secrets` uses `export` lines, so you must source it in your shell before running Kamal commands in a new session:

```bash
set -a; source .kamal/secrets; set +a
```

### 2. Verify `config/deploy.yml`

The `config/deploy.yml` is now environment-agnostic and uses variables from `.kamal/secrets`:

- `KAMAL_HOST`: Your server hostname (set in `.kamal/secrets`)
- `KAMAL_SSH_USER`: SSH username (set in `.kamal/secrets`)
- `KAMAL_REGISTRY_USERNAME`: Docker registry username (set in `.kamal/secrets`)
- All sensitive data is referenced from secrets, not hardcoded

**No manual edits needed** - just ensure your `.kamal/secrets` file has the correct values.

### 3. Prepare Your Server

SSH into your server and prepare it:

```bash
# SSH to your server
ssh your-user@YOUR_SERVER_IP

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Create deploy user (optional but recommended)
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy
sudo mkdir -p /home/deploy/.ssh
sudo cp ~/.ssh/authorized_keys /home/deploy/.ssh/
sudo chown -R deploy:deploy /home/deploy/.ssh
sudo chmod 700 /home/deploy/.ssh
sudo chmod 600 /home/deploy/.ssh/authorized_keys

# Exit and reconnect to apply group changes
exit
```

### 4. Set Up DNS

Point your domain to your server:

```
A record: yourdomain.com → YOUR_SERVER_IP
```

Wait for DNS propagation (can take up to 48 hours, usually much faster).

### 5. Build and Push Docker Image

```bash
# Build the image locally
docker build -t your-dockerhub-username/btaa-geospatial-api:latest .

# Login to Docker Hub
docker login

# Push the image
docker push your-dockerhub-username/btaa-geospatial-api:latest
```

### 6. Setup Kamal on Server

```bash
# Initialize Kamal (sets up Docker and accessories on server)
kamal setup

# This will:
# - Install Kamal proxy (Traefik) on your server
# - Start all accessories (ParadeDB, Elasticsearch, Redis)
# - Deploy your application containers (web, worker, flower)
```

**Note**: The initial setup deploys:
- **ParadeDB 0.18.11** with PostgreSQL + extensions (pg_search, postgis, vector, pg_ivm)
- **Elasticsearch 9.0.0** for search indexing
- **Redis 7.4.6-alpine** for caching and Celery broker

### 7. Run Database Migrations

```bash
# After setup, run migrations
kamal app exec "python db/migrations/create_resource_spatial_facets_table.py"

# Or use the alias
kamal console
>>> from db.migrations import create_resource_spatial_facets_table
>>> # Run migrations...
```

### 8. Verify Deployment

```bash
# Check if containers are running
kamal app details

# Check accessories status
kamal accessory details paradedb
kamal accessory details elasticsearch
kamal accessory details redis

# View application logs
kamal app logs

# Test the API
curl https://your-domain.com/api/v1/health
```

## Common Kamal Commands

### Quick Reference

```bash
# Full deployment workflow
kamal deploy                          # Deploy all services (web, worker, flower)
kamal deploy --roles worker           # Deploy only worker role
kamal redeploy                        # Redeploy without rebuilding
kamal rollback                        # Rollback to previous version

# Database management
make db-export                        # Export local database
make db-import                        # Import to remote
make db-sync                          # Export + Import

# Monitoring
kamal app logs --roles web            # View web logs
kamal app logs --roles worker         # View worker logs  
kamal app logs --roles flower         # View Flower logs
kamal accessory logs paradedb         # View database logs

# Accessories management
kamal accessory boot paradedb         # Start ParadeDB
kamal accessory reboot redis          # Restart Redis
kamal accessory remove elasticsearch  # Remove Elasticsearch
```

### Deployment
```bash
# Deploy new version
kamal deploy

# Redeploy without building
kamal redeploy

# Rollback to previous version
kamal rollback
```

### Management
```bash
# View logs
kamal app logs -f

# Execute commands in app container
kamal app exec "python script.py"

# SSH into server
kamal ssh

# Access PostgreSQL
kamal accessory exec paradedb "psql -U postgres btaa_ogm_api"

# Restart services
kamal app restart
kamal accessory restart redis
```

### Monitoring
```bash
# Check app status
kamal app details

# Check accessory status
kamal accessory details paradedb

# View Celery worker logs
kamal app logs --roles worker

# View Flower logs
kamal app logs --roles flower

# Access Flower (Celery monitoring) via SSH tunnel
# (Use your KAMAL_SSH_USER and KAMAL_HOST from .kamal/secrets)
ssh -L 5555:localhost:5555 $KAMAL_SSH_USER@$KAMAL_HOST
# Then open http://localhost:5555 in browser
```

## Multi-Container Setup

Your application has multiple containers:

1. **Web** (single-host): Public router on port 8000 that serves:
   - SSR on `/` (Node server on internal port 3000)
   - API on `/api/*` (FastAPI on internal port 8001)
2. **Worker** (Celery): Background task processing for async jobs
3. **Flower**: Celery monitoring UI on port 5555
4. **Accessories**:
   - **ParadeDB** (PostgreSQL + extensions): Port 5432 (v0.18.11)
   - **Elasticsearch**: Port 9200 (v9.0.0)
   - **Redis**: Port 6379 (v7.4.6-alpine)

## Environment-Specific Configuration

### Production Tweaks

Update `config/deploy.yml` for production:

```yaml
servers:
  web:
    hosts:
      - <%= ENV['KAMAL_HOST'] %>
    # Single-host: nginx (public :8000) routes /api/* -> uvicorn (:8001) and / -> SSR (:3000)
    cmd: bash -lc "/app/scripts/start_web_singlehost.sh"

  worker:
    hosts:
      - <%= ENV['KAMAL_HOST'] %>
    cmd: celery -A app.tasks.worker worker --loglevel=INFO --concurrency=4

  flower:
    hosts:
      - <%= ENV['KAMAL_HOST'] %>
    cmd: celery -A app.tasks.worker flower --port=5555

# Health checks are configured in proxy section
proxy:
  ssl: true
  host: <%= ENV['KAMAL_HOST'] %>
  app_port: 8000
  healthcheck:
    path: /api/docs
```

### Frontend SSR configuration notes

- The SSR server uses runtime env var `API_BASE_URL` for server-side requests. In the single-host image it defaults to:
  - `http://127.0.0.1:8000/api/v1` (goes through the internal router)
- The browser bundle uses build arg `VITE_API_BASE_URL` and should be set to:
  - `https://<host>/api/v1`

### Caching + rate limiting env vars (production)

Recommended baseline (set via Kamal `env.clear` / `env.secret` in `config/deploy.yml`):

```text
# Redis connectivity
REDIS_HOST=btaa-geospatial-api-redis
REDIS_PORT=6379
REDIS_PASSWORD=... (secret)

# Separate Redis DBs
REDIS_DB=0
RATE_LIMIT_REDIS_DB=2

# Enable middleware enforcement
RATE_LIMIT_ENABLED=true

# Endpoint caching controls
ENDPOINT_CACHE=true
GAZETTEER_CACHE_TTL=3600
CACHE_DEBUG_HEADERS=false
CACHE_LOG_EVENTS=false
CACHE_VERSION=v2
CACHE_APP_VERSION= (optional)
```

### ParadeDB Configuration

ParadeDB is a PostgreSQL-compatible database with additional extensions:
- **pg_search**: Full-text search (BM25)
- **postgis**: Spatial/geographic data
- **vector**: pgvector for embeddings
- **pg_ivm**: Incremental materialized views

Current configuration in `deploy.yml`:

```yaml
paradedb:
  image: paradedb/paradedb:0.18.11
  roles: [web, worker, flower]
  env:
    clear:
      POSTGRES_USER: postgres
      POSTGRES_DB:   btaa_ogm_api
    secret:
      - POSTGRES_PASSWORD
  port: "127.0.0.1:5432:5432"
  directories:
    - pgdata:/var/lib/postgresql/data
```

### Elasticsearch Production Settings

Current configuration in `deploy.yml`:

```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:9.0.0
  roles: [web, worker, flower]
  env:
    clear:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms2g -Xmx2g"
      cluster.routing.allocation.disk.threshold_enabled: "true"
```

## SSL/HTTPS Configuration

Kamal uses Traefik proxy with Let's Encrypt for automatic SSL:

```yaml
proxy:
  ssl: true
  host: api.yourdomain.com
  app_port: 8000
  # Optional: Force HTTPS redirect
  response_timeout: 300
```

Let's Encrypt will automatically:
- Obtain SSL certificate
- Renew certificates before expiration
- Handle HTTPS redirects

## Troubleshooting

### Container Won't Start

```bash
# Check logs
kamal app logs --tail 100

# Check Docker on server
kamal ssh
docker ps -a
docker logs btaa-geospatial-api-web
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
kamal accessory details paradedb

# Test connection from app container
kamal app exec "python -c 'from db.config import DATABASE_URL; print(DATABASE_URL)'"

# Access PostgreSQL directly
kamal accessory exec paradedb "psql -U postgres -c '\\l'"
```

### Elasticsearch Not Responding

```bash
# Check Elasticsearch health
curl http://YOUR_SERVER_IP:9200/_cluster/health

# View logs
kamal accessory logs elasticsearch

# Restart if needed
kamal accessory restart elasticsearch
```

### Cron container (bridge sync, blog sync)

The cron container runs daily at 2 AM (bridge sync) and 3 AM (blog sync) in the container's local timezone. If jobs aren't running:

```bash
# 1. Run diagnostics (crontab, timezone, env)
source .kamal/secrets
make kamal-cron-debug

# 2. Manually test the bridge sync trigger (same as 2 AM job)
make kamal-cron-test-bridge

# 3. Check bridge status after a run
make kamal-bridge-status
```

**Common causes:**

- **Python path**: Crontab must use `/opt/venv/bin/python3` (cron has minimal PATH; system `python3` lacks `requests`). See `config/crontab`.
- **Timezone**: Cron uses container TZ. 2 AM Central = bridge sync; confirm with `date` in `kamal-cron-debug`.
- **APPLICATION_URL**: Must be set so the trigger script can POST to the API. Check env in `kamal-cron-debug`.
- **First run**: If deployed mid-day, the first 2 AM run is the next calendar day.

### Image Build Failures

```bash
# Build locally first
docker build -t your-dockerhub-username/btaa-data-api:latest .

# Test image locally
docker run -p 8000:8000 your-dockerhub-username/btaa-data-api:latest

# Check build args in deploy.yml
```

## Data Persistence & Database Management

Kamal creates Docker volumes for data persistence:

```bash
# List volumes on server
kamal ssh
docker volume ls
```

### Database Export/Import

Use the Makefile tasks to sync your local database to production:

```bash
# Export local ParadeDB database
make db-export

# Import to remote server (via Kamal)
make db-import

# Do both in one command
make db-sync
```

This will:
1. Export your local database to `tmp/btaa_ogm_api_export.sql.gz`
2. Copy it to the remote server
3. Import it into the ParadeDB container
4. Clean up temporary files

### Manual Database Backup

```bash
# Source environment variables first
source .kamal/secrets

# Backup ParadeDB data
ssh $KAMAL_SSH_USER@$KAMAL_HOST '\
          docker exec btaa-geospatial-api-paradedb pg_dump \
    -U postgres \
    -d btaa_geospatial_api \
    --clean --if-exists | gzip > ~/btaa_geospatial_api_backup_$(date +%Y%m%d).sql.gz'

# Download backup to local
scp $KAMAL_SSH_USER@$KAMAL_HOST:~/btaa_geospatial_api_backup_*.sql.gz ./backups/
```

## Scaling

### Horizontal Scaling (Multiple Servers)

```yaml
servers:
  web:
    hosts:
      - 192.168.0.1
      - 192.168.0.2
  worker:
    hosts:
      - 192.168.0.3
      - 192.168.0.4
  flower:
    hosts:
      - 192.168.0.3  # Usually on same host as workers
```

### Vertical Scaling (Resource Limits)

```yaml
resources:
  limits:
    cpus: '2.0'
    memory: 4G
  reservations:
    cpus: '1.0'
    memory: 2G
```

## Security Best Practices

1. **Use SSH Keys**: Disable password authentication
2. **Firewall**: Only expose necessary ports (80, 443, 22)
3. **Secrets**: Never commit `.kamal/secrets` to git
4. **Registry**: Use private registry for production images
5. **Updates**: Regularly update Docker images and dependencies
6. **Backups**: Automate database backups
7. **Monitoring**: Set up external monitoring (Datadog, New Relic, etc.)

## GitHub Actions Integration

Automate deployments with GitHub Actions:

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: 3.2
      
      - name: Install Kamal
        run: gem install kamal
      
      - name: Set up secrets
        run: |
          mkdir -p .kamal
          cat > .kamal/secrets << EOF
          # Environment-specific configuration
          export KAMAL_HOST=${{ secrets.KAMAL_HOST }}
          export KAMAL_SSH_USER=${{ secrets.KAMAL_SSH_USER }}
          export KAMAL_REGISTRY_USERNAME=${{ secrets.KAMAL_REGISTRY_USERNAME }}
          
          # Credentials
          KAMAL_REGISTRY_PASSWORD=${{ secrets.KAMAL_REGISTRY_PASSWORD }}
          POSTGRES_PASSWORD=${{ secrets.POSTGRES_PASSWORD }}
          DATABASE_URL=postgresql+asyncpg://postgres:${{ secrets.POSTGRES_PASSWORD }}@btaa-geospatial-api-paradedb:5432/btaa_geospatial_api
          ADMIN_USERNAME=${{ secrets.ADMIN_USERNAME }}
          ADMIN_PASSWORD=${{ secrets.ADMIN_PASSWORD }}
          OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}
          OPENAI_MODEL=${{ secrets.OPENAI_MODEL }}
          EOF
          chmod 600 .kamal/secrets
      
      - name: Set up SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan ${{ secrets.KAMAL_HOST }} >> ~/.ssh/known_hosts
      
      - name: Deploy
        run: kamal deploy
```

## Next Steps

1. ✅ Configure `config/deploy.yml`
2. ✅ Create `.kamal/secrets`
3. ✅ Prepare your server
4. ✅ Set up DNS
5. ✅ Run `kamal setup`
6. ✅ Run migrations
7. ✅ Test deployment
8. ✅ Set up monitoring
9. ✅ Configure backups
10. ✅ Automate deployments

## Additional Resources

- [Kamal Documentation](https://kamal-deploy.org/)
- [Traefik Proxy Docs](https://doc.traefik.io/traefik/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Let's Encrypt](https://letsencrypt.org/)
