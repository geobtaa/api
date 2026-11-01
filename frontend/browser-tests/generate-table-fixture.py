"""Regenerate with backend's pinned DuckDB: run from the frontend directory."""

import duckdb

with duckdb.connect() as database:
    database.sql("""
        SELECT lpad(i::VARCHAR, 5, '0') AS id,
            CASE WHEN i=1 THEN 'O''Brien' ELSE 'Record ' || i END AS name,
            CASE WHEN i=2 THEN 2 WHEN i=3 THEN 10
                 ELSE 9007199254740993+i END::BIGINT AS amount
        FROM range(120000) t(i)
    """).write_parquet(
        "browser-tests/fixtures/table.parquet", compression="zstd", row_group_size=16384
    )
