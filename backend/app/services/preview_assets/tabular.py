"""Bounded, offline table conversion. CSV values are deliberately not type-guessed."""

import csv
import json
import sys
from pathlib import Path

from .process import run_tool


def prepare_table(source, budget):
    output = source.parent / "table.parquet"
    metadata = source.parent / "table-schema.json"
    run_tool(
        [
            sys.executable,
            "-m",
            "app.services.preview_assets.tabular",
            str(source),
            str(output),
            str(metadata),
        ],
        budget,
    )
    budget.check()
    return output, json.loads(metadata.read_text())


def convert(source, output, metadata):
    import duckdb

    with duckdb.connect(
        config={
            "threads": "1",
            "memory_limit": "512MB",
            "temp_directory": str(source.parent / "duckdb-tmp"),
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
        }
    ) as connection:
        # Local file access must be enabled for these explicitly supplied paths;
        # no user SQL, remote URLs, or extension installation is accepted.
        if source.suffix == ".parquet":
            table = connection.read_parquet(str(source))
        else:
            with source.open(encoding="utf-8-sig", newline="") as stream:
                header = next(
                    csv.reader(stream, delimiter="\t" if source.suffix == ".tsv" else ","), []
                )
            if (
                not header
                or any(not name for name in header)
                or len({name.casefold() for name in header}) != len(header)
            ):
                raise ValueError("CSV/TSV requires unique, nonempty column names")
            table = connection.read_csv(
                str(source),
                header=True,
                all_varchar=True,
                delimiter="\t" if source.suffix == ".tsv" else ",",
                strict_mode=True,
                null_padding=False,
            )
        columns = [
            {"name": name, "type": str(kind)} for name, kind in zip(table.columns, table.types)
        ]
        if not columns or len(columns) > 256:
            raise ValueError("Table must contain between 1 and 256 columns")
        if any(
            any(token in col["type"] for token in ("STRUCT", "[]", "MAP(", "BLOB"))
            for col in columns
        ):
            raise ValueError("Nested and binary table columns require review")
        table.write_parquet(str(output), compression="zstd", row_group_size=16384)
        count = connection.read_parquet(str(output)).count("*").fetchone()[0]
        metadata.write_text(json.dumps({"columns": columns, "row_count": count}))


if __name__ == "__main__":
    convert(*(Path(arg) for arg in sys.argv[1:]))
