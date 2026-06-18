# Repository Scripts

This page covers repository-level script conventions. Most backend utility
scripts live in `backend/scripts/` and are documented in
[backend/scripts.md](backend/scripts.md).

Prefer Makefile targets for routine local development work because they wrap the
expected environment and Docker commands.

## Recommended Public Entry Points

| Need | Preferred command |
| --- | --- |
| Backend lint/format/test | `make lint`, `make format`, `make test`, `make test-no-coverage` |
| Frontend lint/format/test | `cd frontend && npm run lint && npm run format:check && npm test` |
| Local reindex | `make reindex` |
| Local H3 verification | `make verify-h3-index` |
| Local cache clearing | `make clear_cache` |
| Public docs | `make docs-serve`, `make docs-build` |

Remote deployment, backup, cache, indexing, bridge, worker, host, and network
operations are restricted operations material. Do not document destination
names, secret-loading behavior, remote command blocks, hostnames, backup paths,
or production troubleshooting procedures in this public repository.

## Script Maintenance Checklist

- Add a Makefile target when a script becomes part of a repeated local workflow.
- Document new public-safe target variables in [make_tasks.md](make_tasks.md).
- Add or update backend tests when a script mutates database, cache, index, or
  external service state.
- Keep destructive scripts guarded by clear names, dry-run flags, or Makefile
  comments.
- Do not commit generated outputs from `tmp/`, `logs/`, data volumes, cache
  directories, or Python/Node build artifacts.
