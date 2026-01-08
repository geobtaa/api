from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import duckdb


@dataclass(frozen=True)
class OGMRunDumpPaths:
    run_dir: Path
    dataset_ndjson: Path
    dataset_json: Path
    dataset_parquet: Path
    manifest_json: Path


class OGMHarvestDumpWriter:
    """
    Writes per-harvest dump artifacts:
      - dataset.ndjson (one record per line)
      - dataset.json (JSON array of records)
      - dataset.parquet (via DuckDB)
      - manifest.json (metadata about the dump)
    """

    def __init__(self, repo_name: str, run_id: int, base_dir: str | Path | None = None):
        # Default is relative to backend/ working dir in Docker (`cd /app/backend`):
        # -> /app/backend/data/harvest_dumps/ogm
        base = Path(base_dir or os.getenv("OGM_DUMP_BASE_DIR", "data/harvest_dumps/ogm"))
        date_part = datetime.utcnow().strftime("%Y-%m-%d")
        run_dir = base / repo_name / date_part / str(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        self.paths = OGMRunDumpPaths(
            run_dir=run_dir,
            dataset_ndjson=run_dir / "dataset.ndjson",
            dataset_json=run_dir / "dataset.json",
            dataset_parquet=run_dir / "dataset.parquet",
            manifest_json=run_dir / "manifest.json",
        )

        self._ndjson_fp = self.paths.dataset_ndjson.open("w", encoding="utf-8")
        self._json_fp = self.paths.dataset_json.open("w", encoding="utf-8")
        self._json_fp.write("[")
        self._first_json = True
        self.count = 0

    def write_record(self, record: Dict[str, Any]) -> None:
        self._ndjson_fp.write(json.dumps(record, ensure_ascii=False) + "\n")

        if self._first_json:
            self._first_json = False
        else:
            self._json_fp.write(",")
        self._json_fp.write(json.dumps(record, ensure_ascii=False))

        self.count += 1

    def finalize(
        self,
        *,
        repo_name: str,
        run_id: int,
        head_sha: Optional[str],
        stats: Dict[str, Any],
    ) -> OGMRunDumpPaths:
        # Close JSON array
        self._json_fp.write("]")
        self._json_fp.flush()
        self._ndjson_fp.flush()
        self._json_fp.close()
        self._ndjson_fp.close()

        # Write parquet via DuckDB from NDJSON (streaming friendly).
        # Notes:
        # - DuckDB parameter binding with COPY/TO can behave unexpectedly; embed quoted paths.
        # - If no records were written, skip parquet generation (avoid read_json_auto failures).
        parquet_written = False
        try:
            if self.count > 0 and self.paths.dataset_ndjson.exists() and self.paths.dataset_ndjson.stat().st_size > 0:
                ndjson_path = str(self.paths.dataset_ndjson).replace("'", "''")
                parquet_path = str(self.paths.dataset_parquet).replace("'", "''")
                con = duckdb.connect()
                try:
                    con.execute(
                        f"COPY (SELECT * FROM read_json_auto('{ndjson_path}')) TO '{parquet_path}' (FORMAT 'parquet')"
                    )
                    parquet_written = True
                finally:
                    con.close()
        except Exception:
            # Dumps are helpful but should not fail the harvest; keep JSON/NDJSON + manifest.
            parquet_written = False

        manifest = {
            "ogm_repo_name": repo_name,
            "ogm_run_id": run_id,
            "ogm_head_sha": head_sha,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "counts": {"records": self.count, **(stats or {})},
            "files": {
                "dataset_ndjson": self.paths.dataset_ndjson.name,
                "dataset_json": self.paths.dataset_json.name,
                **({"dataset_parquet": self.paths.dataset_parquet.name} if parquet_written else {}),
            },
        }
        self.paths.manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return self.paths

