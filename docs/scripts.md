# Repository Scripts

This page covers repository-level script conventions. Most operational Python
scripts live in `backend/scripts/` and are documented in
[backend/scripts.md](backend/scripts.md). Prefer Makefile targets for routine
work because they load environment variables and wrap the correct Docker/Kamal
commands.

## Recommended Entry Points

| Need | Preferred command |
| --- | --- |
| Backend lint/format/test | `make lint`, `make format`, `make test`, `make test-no-coverage` |
| Frontend lint/format/test | `cd frontend && npm run lint && npm run format:check && npm test` |
| Local reindex | `make reindex` |
| Remote reindex | `make kamal-reindex KAMAL_DEST=dev1` |
| Local H3 verification | `make verify-h3-index` |
| Remote H3 verification | `make kamal-verify-h3-index KAMAL_DEST=dev1` |
| Cache clearing | `make clear_cache` or `make kamal-clear-cache KAMAL_DEST=...` |
| Public docs | `make docs-serve`, `make docs-build` |

## Kamal Command Pattern

Kamal commands should always specify a destination. Destination secrets are
loaded from `.kamal/secrets-common` and `.kamal/secrets.<dest>` by the Makefile.

```bash
make kamal-reindex KAMAL_DEST=dev1
make kamal-verify-h3-index KAMAL_DEST=dev1
make kamal-clear-cache KAMAL_DEST=dev1 KAMAL_CACHE_TYPE=search
```

Direct Kamal commands are useful for debugging but should stay explicit:

```bash
kamal app exec -d dev1 --roles web "bash -lc 'cd /app/backend && /opt/venv/bin/python scripts/verify_h3_index.py'"
```

## Script Maintenance Checklist

- Add a Makefile target when a script becomes part of a repeated workflow.
- Document new target variables in [make_tasks.md](make_tasks.md).
- Add or update backend tests when a script mutates database, cache, index, or
  external service state.
- Keep destructive scripts guarded by clear names, dry-run flags, or Makefile
  comments.
- Do not commit generated outputs from `tmp/`, `logs/`, data volumes, cache
  directories, or Python/Node build artifacts.
