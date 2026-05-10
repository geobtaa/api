from __future__ import annotations

import json
from typing import Annotated, Optional

import typer

from ..client import iter_resources
from ..filters import apply_filter_params, parse_filters
from ..output import print_data, print_rows, resource_summary
from ..runtime import Runtime

app = typer.Typer(help="Search BTAA Geo API resources.")


@app.callback(invoke_without_command=True)
def search(
    ctx: typer.Context,
    query: Annotated[Optional[str], typer.Argument(help="Keyword query.")] = None,
    include: Annotated[
        Optional[list[str]],
        typer.Option("--include", "-i", help="Include facet filter as FIELD=VALUE."),
    ] = None,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option("--exclude", "-x", help="Exclude facet filter as FIELD=VALUE."),
    ] = None,
    page: Annotated[int, typer.Option(help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option(help="Results per page.")] = 10,
    sort: Annotated[Optional[str], typer.Option(help="Sort option.")] = None,
    search_field: Annotated[
        Optional[str], typer.Option("--search-field", help="Restrict query to one field.")
    ] = None,
    fields: Annotated[Optional[str], typer.Option(help="Comma-separated response fields.")] = None,
    facets: Annotated[
        Optional[str], typer.Option(help="Comma-separated facet aggregations.")
    ] = None,
    adv_q: Annotated[
        Optional[str],
        typer.Option("--adv-q", help="Advanced query JSON array, passed to the API unchanged."),
    ] = None,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="table, json, jsonl, or csv.")
    ] = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    runtime: Runtime = ctx.obj
    runtime.analytics.command = "search"
    try:
        filters = parse_filters(include, exclude)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    params: dict[str, object] = {
        "q": query or "",
        "page": page,
        "per_page": per_page,
    }
    if sort:
        params["sort"] = sort
    if search_field:
        params["search_field"] = search_field
    if fields:
        params["fields"] = fields
    if facets:
        params["facets"] = facets
    if adv_q:
        try:
            json.loads(adv_q)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter("--adv-q must be valid JSON") from exc
        params["adv_q"] = adv_q

    params = apply_filter_params(params, filters)
    payload = runtime.client.get("/search", params=params)
    selected_output = output or runtime.config.output
    if selected_output in {"json", "jsonl"}:
        print_data(payload, output=selected_output)
    else:
        rows = [resource_summary(item) for item in iter_resources(payload)]
        print_rows(rows, output=selected_output, columns=["id", "title", "year", "provider"])
    runtime.analytics.record_search(runtime.client, payload, query, params)
