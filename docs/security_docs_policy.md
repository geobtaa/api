# Security Documentation Policy

This repository is public, so documentation here should help people develop,
test, understand, and use the BTAA Geospatial API without exposing operational
details for deployed environments.

## Keep Public

- Local development setup, linting, formatting, and test commands.
- Public API behavior, schemas, examples, and integration guidance.
- Code architecture, domain models, data flow, and implementation rationale.
- Local Docker service descriptions needed for development.
- Safe troubleshooting for local developer environments.

## Keep Restricted

Put these in the restricted operations documentation instead of this public
repository:

- Deployment, release, rollback, and production verification procedures.
- Hostnames, internal IPs, network ranges, host inventories, and topology maps.
- Remote-login usernames, key setup, privilege-escalation/bootstrap steps, and
  Docker-on-host procedures.
- Secret-file names, secret loading commands, credential setup, and token
  locations.
- Backup schedules, storage layouts, restore procedures, retention rules, and
  disaster-recovery drills.
- Production Redis, Elasticsearch, Postgres, Docker, remote-login, or remote
  deployment command blocks.
- Capacity ceilings, bottlenecks, failure thresholds, performance baselines,
  and launch-readiness reports.
- Third-party dashboard IDs, tag-manager IDs, signing-secret setup, mail relay
  configuration, and internal recipient lists.

## Public Stub Pattern

When a public page needs to keep a stable link for restricted material, replace
the body with a short stub that:

- Describes the topic at a high level.
- Says the detailed runbook is restricted operations material.
- Points public contributors to safe local development, testing, API, or
  architecture docs.
- Does not include the private repository URL.

## Review Checklist

Before merging documentation changes, scan public docs, `README.md`, and
`AGENTS.md` for operational leakage. Watch especially for hostnames, internal
URLs, IP ranges, SSH instructions, secret names, remote deploy commands,
production command examples, backup paths, dashboard IDs, and capacity numbers.
