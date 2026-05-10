from __future__ import annotations

from typing import Annotated, Optional

import typer

from ..filters import apply_filter_params, parse_filters
from ..output import print_data, print_rows
from ..runtime import Runtime

app = typer.Typer(help="List facet values.")


@app.callback(invoke_without_command=True)
def facets(
    ctx: typer.Context,
    facet_name: Annotated[str, typer.Argument(help="Facet field name.")],
    q: Annotated[Optional[str], typer.Option(help="Search query context.")] = None,
    include: Annotated[Optional[list[str]], typer.Option("--include", "-i")] = None,
    exclude: Annotated[Optional[list[str]], typer.Option("--exclude", "-x")] = None,
    page: Annotated[int, typer.Option()] = 1,
    per_page: Annotated[int, typer.Option()] = 10,
    sort: Annotated[str, typer.Option()] = "count_desc",
    q_facet: Annotated[Optional[str], typer.Option("--q-facet")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = None,
) -> None:
    runtime: Runtime = ctx.obj
    runtime.analytics.command = "facets"
    params: dict[str, object] = {"page": page, "per_page": per_page, "sort": sort}
    if q:
        params["q"] = q
    if q_facet:
        params["q_facet"] = q_facet
    params = apply_filter_params(params, parse_filters(include, exclude))
    payload = runtime.client.get(f"/search/facets/{facet_name}", params=params)
    selected_output = output or runtime.config.output
    if selected_output == "table":
        values = payload.get("data", []) if isinstance(payload, dict) else []
        rows = []
        for item in values:
            attrs = item.get("attributes", item) if isinstance(item, dict) else {}
            rows.append(
                {
                    "value": attrs.get("value") or item.get("id", ""),
                    "count": _facet_count(attrs),
                }
            )
        print_rows(rows, output="table", columns=["value", "count"])
    else:
        print_data(payload, output=selected_output)
    runtime.analytics.record_event(
        runtime.client, "cli.command.facets", properties={"facet": facet_name}
    )


def _facet_count(attrs: dict) -> object:
    for key in ("count", "hits", "doc_count"):
        value = attrs.get(key)
        if value is not None:
            return value
    return ""
