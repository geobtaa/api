from __future__ import annotations

import csv
import json
import sys
from typing import Any, Iterable

from rich.console import Console
from rich.table import Table

console = Console()


def print_data(data: Any, *, output: str = "json") -> None:
    if output == "json":
        console.print_json(json.dumps(data, default=str))
    elif output == "jsonl":
        rows = (
            data
            if isinstance(data, list)
            else data.get("data", [])
            if isinstance(data, dict)
            else [data]
        )
        for row in rows:
            print(json.dumps(row, default=str))
    else:
        print(json.dumps(data, indent=2, default=str))


def print_rows(rows: Iterable[dict[str, Any]], *, output: str, columns: list[str]) -> None:
    row_list = list(rows)
    if output == "json":
        print_data(row_list, output="json")
        return
    if output == "jsonl":
        print_data(row_list, output="jsonl")
        return
    if output == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=columns)
        writer.writeheader()
        for row in row_list:
            writer.writerow({column: row.get(column, "") for column in columns})
        return

    table = Table()
    for column in columns:
        table.add_column(column)
    for row in row_list:
        table.add_row(*(str(row.get(column, "")) for column in columns))
    console.print(table)


def resource_summary(item: dict[str, Any]) -> dict[str, Any]:
    attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
    ogm = attrs.get("ogm", attrs) if isinstance(attrs, dict) else {}
    title = ogm.get("dct_title_s") or attrs.get("title") or item.get("id", "")
    if isinstance(title, list):
        title = title[0] if title else ""
    year = ogm.get("gbl_indexYear_im") or attrs.get("year", "")
    if isinstance(year, list):
        year = ", ".join(str(v) for v in year)
    provider = ogm.get("schema_provider_s") or attrs.get("provider", "")
    if isinstance(provider, list):
        provider = ", ".join(str(v) for v in provider)
    return {
        "id": item.get("id", ""),
        "title": title or "",
        "year": year or "",
        "provider": provider or "",
    }
