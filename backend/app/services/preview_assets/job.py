"""Child-process entrypoint. The worker supplies memory/time/disk isolation."""

import json
import sys
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import select, text

from db.models import resources
from db.session import sync_engine

from .coverage_map import render_coverage
from .io import download
from .models import Outcome, PreviewError
from .pipeline import Pipeline
from .repository import hydrate_sources
from .storage import storage


@contextmanager
def provider_lease(host):
    with sync_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        key = "preview-provider:" + host
        if not connection.execute(
            text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"), {"key": key}
        ).scalar():
            raise PreviewError(Outcome.UNAVAILABLE, "Provider busy; retry later")
        try:
            yield
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": key}
            )


def provider_download(url, target, budget):
    return download(url, target, budget, host_guard=provider_lease)


def child_record(identifier):
    with sync_engine.connect() as connection:
        row = (
            connection.execute(select(resources).where(resources.c.id == identifier))
            .mappings()
            .first()
        )
        return hydrate_sources(connection, row) if row else None


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    audit_root = request.pop("audit_root", None)
    if audit_root:
        from .storage import LocalStorage

        store = LocalStorage(Path(audit_root))
        fetch = download
        lookup = None
    else:
        store, fetch, lookup = storage(), provider_download, child_record
    result = Pipeline(
        store,
        fetch=fetch,
        child_lookup=lookup,
        coverage_renderer=render_coverage,
        work_root=Path(sys.argv[2]).parent,
    ).prepare(**request)
    Path(sys.argv[2]).write_text(result.model_dump_json())


if __name__ == "__main__":
    main()
