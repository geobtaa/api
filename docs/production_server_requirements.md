# Production Server Requirements Specification (Austere + ES-HA)

This document defines a cost-conscious production footprint with **high availability for Elasticsearch** while keeping other tiers minimal. It is based on the current dev baseline (single VM running the full stack) and is designed to scale up later without re-architecture.

## Goals

- Keep search highly available and fast.
- Stay online during normal deploys and single-node failures in the search tier.
- Keep costs and VM count as low as possible today.
- Maintain a clear upgrade path to full HA later.

## Current Dev Baseline (for Sizing Reference)

The dev server runs the full stack on a single VM and performs well:

- 8 vCPU
- 32 GiB RAM
- ~200 GiB SSD

This baseline informs the per-node sizing below.

## Terminology

- **Node** means a **separate VM** (or physical host). We want ES nodes on different VMs so a single VM failure does not take search down.

## Architecture Summary (Austere + ES-HA)

- Edge: load balancer and CDN in front of the API and SSR.
- App: 2 API/SSR nodes for rolling deploys.
- Background jobs + cache/queue: 1 shared high-memory node running Celery + Redis.
- Database: 1 Postgres primary (no replica yet).
- Search: 3-node Elasticsearch cluster (2 data nodes + 1 master-only node).
- Observability: hosted service (no dedicated VM required).
- Object storage: Amazon S3 for assets and backups.

## Detailed Stack Schematic (Who Runs What)

Use this as the concrete "host + technology" mapping for the Austere + ES-HA plan.

### Recommended edge pattern (managed)

- **DNS + CDN/WAF**: Cloudflare (managed SaaS).
- **Public load balancer**: provider-managed L4/L7 load balancer, for example AWS ALB/NLB, GCP HTTP(S) LB, Azure Application Gateway, or Hetzner Load Balancer.
- **TLS certificates**: terminate at the CDN and/or load balancer using managed certificates.

This means the load balancer is **not** on your app VM; it is run by your infrastructure provider as a managed service.

### Alternative edge pattern (self-hosted)

If managed LB is unavailable, run a small dedicated LB VM:

- **LB VM software**: HAProxy, Traefik, or NGINX.
- **Placement**: one dedicated VM in front of app nodes.
- **Note**: this is lower cost but creates a new single point of failure unless you run two LB VMs with failover.

### Request flow (runtime path)

1. User browser
2. DNS/CDN/WAF (Cloudflare)
3. Public load balancer (managed LB service, or self-hosted HAProxy/Traefik/NGINX VM)
4. API/SSR node A or B (Docker host running app containers)
5. Internal calls from API/SSR to:
   - Postgres primary (ParadeDB/PostgreSQL)
   - Elasticsearch 3-node cluster (2 data + 1 master-only)
   - Redis (cache + Celery broker)
   - S3 (object storage/backups)
6. Background jobs from API enqueue to Redis; Celery worker consumes and writes back to Postgres/ES/S3

### Host-by-host technology mapping

- **Edge DNS/CDN/WAF (managed SaaS)**  
  Tech: Cloudflare (or equivalent).  
  Runs: DNS, CDN cache, WAF, optional DDoS controls.

- **Edge load balancer (managed service preferred)**  
  Tech: cloud LB service (ALB/NLB/Application Gateway/Hetzner LB).  
  Runs: health checks, host/path routing, upstream balancing to app node A/B.

- **App node A (VM)**  
  Tech: Ubuntu + Docker + Kamal-deployed containers.  
  Runs: SSR frontend process, FastAPI app process, reverse-proxy/router container if used.

- **App node B (VM)**  
  Tech: same as node A.  
  Runs: second identical app stack for rolling deploy and failover.

- **Worker node (VM)**  
  Tech: Ubuntu + Docker + Celery worker + Redis 7.x containers (optional Flower).  
  Runs: async jobs, ingest/index tasks, API cache, and Celery broker/queues.  
  Sizing emphasis: prioritize RAM for Redis hot-object cache and queue stability.

- **Database node (VM)**  
  Tech: ParadeDB/PostgreSQL on NVMe-backed VM.  
  Runs: primary relational database.

- **Search data node 1 (VM)**  
  Tech: Elasticsearch data node.  
  Runs: shards, indexing, query execution.

- **Search data node 2 (VM)**  
  Tech: Elasticsearch data node.  
  Runs: replica/primary shards for HA and capacity.

- **Search master-only node (VM)**  
  Tech: Elasticsearch master-only role.  
  Runs: cluster coordination and elections (no data role).

- **Observability (shared or hosted)**  
  Tech: Grafana Cloud / Datadog / New Relic / ELK stack.  
  Runs: metrics, logs, alerting, uptime checks.

- **Object storage (managed)**  
  Tech: Amazon S3.  
  Runs: asset files, snapshots, backup artifacts.

## VM Inventory (Austere + ES-HA)

- 2x API/SSR nodes: 8 vCPU, 32 GB RAM, 100 GB SSD each
- 1x shared jobs/cache node: 8 to 12 vCPU, 64 GB RAM, 200 to 400 GB SSD (Celery + Redis; optional Flower)
- 1x Postgres primary: 12 to 16 vCPU, 48 to 64 GB RAM, 500 GB NVMe (1 TB NVMe for extra growth headroom)
- 2x Elasticsearch data nodes: 16 vCPU, 64 GB RAM, 1 TB NVMe each
- 1x Elasticsearch master-only node: 4 vCPU, 16 GB RAM, 100 GB SSD
- observability via hosted service (no VM in this plan)

## Service Co-location Plan (Austere Default)

- Co-locate **Celery + Redis (+ Flower)** on one VM to reduce node count and operations overhead.
- On the shared jobs/cache node, reserve substantial RAM headroom for Redis so thumbnail and endpoint cache churn does not starve Celery workers.
- Keep **API/SSR separate** on two nodes so deploys and app-node failure do not take down the site.
- Keep **Postgres isolated** on its own VM to avoid storage and memory contention.
- Keep **Elasticsearch isolated** on three VMs to preserve ES high availability.
- Use **hosted observability** to avoid running a dedicated monitoring VM.

If you need a smaller starting point for Postgres or ES data nodes:

- Postgres primary: 8 to 12 vCPU, 32 to 48 GB RAM, 500 GB NVMe (scale to 1 TB as usage grows)
- ES data nodes: 8 to 12 vCPU, 32 to 48 GB RAM, 1 TB NVMe

## Simple Justification (Why These Machines)

- Load balancer + CDN: absorbs spikes, caches hot responses, and protects uptime.
- 2x API/SSR nodes: keeps the site up during deploys or a single app node failure.
- 1x shared jobs/cache node: minimizes VM count while keeping async and cache workloads off API nodes; higher RAM supports larger hot image/object cache.
- Postgres primary: authoritative data store; sized for write load and indexes.
- ES data nodes: memory and fast disk keep search and facets low-latency.
- ES master-only node: prevents split-brain and keeps the ES cluster stable.
- Redis on shared jobs node: keeps hot API responses in memory and runs Celery queues.
- Hosted observability: alerts before outages impact users without another VM to maintain.

## Availability and Performance Targets

- Uptime target: 99.5 to 99.8 percent monthly overall.
- Search uptime target: 99.9 percent (due to ES HA).
- API latency targets (steady state):
  - Cached responses: p95 under 200 ms
  - Search requests: p95 under 600 ms
  - Resource detail requests: p95 under 500 ms

## Known Tradeoffs (Austere Plan)

- Postgres has no replica, so a DB failure causes downtime until recovery.
- Redis and Celery share one node, so a node failure affects both cache and background jobs.
- Worker/cache capacity is still shared on one node, so heavy jobs can impact queue latency unless Redis memory limits and Celery concurrency are tuned.

## Growth Path (Future Upgrades)

- Add a Postgres replica for failover and read scaling.
- Split Redis into cache and broker nodes.
- Add a third ES data node for more capacity and faster reindexing.
- Add more API and worker nodes as traffic grows.

## S3 Integration Requirements

- S3 buckets for assets and backups.
- IAM roles or short-lived credentials.
- Lifecycle policies for retention and cost control.
- Optional cross-region replication for disaster recovery.
