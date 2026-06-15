from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer

from ..client import iter_resources
from ..filters import apply_filter_params, parse_filters
from ..output import print_data, print_field_values, print_jsonl_item, print_rows, resource_summary
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
    all_pages: Annotated[
        bool, typer.Option("--all", help="Fetch every result page before printing.")
    ] = False,
    stream: Annotated[
        bool,
        typer.Option(
            "--stream",
            help="Stream resources as JSON Lines while paging. Implies --all and --output jsonl.",
        ),
    ] = False,
    each: Annotated[
        bool,
        typer.Option(
            "--each",
            help="Read newline-delimited queries from stdin and run one search per query.",
        ),
    ] = False,
    ids_only: Annotated[
        bool, typer.Option("--ids-only", help="Print only resource IDs, one per line.")
    ] = False,
    field: Annotated[
        Optional[str], typer.Option("--field", help="Print one dotted field path per result.")
    ] = None,
    fail_if_empty: Annotated[
        bool, typer.Option("--fail-if-empty", help="Exit non-zero when no resources match.")
    ] = False,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    runtime: Runtime = ctx.obj
    runtime.analytics.command = "search"
    try:
        filters = parse_filters(include, exclude)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    queries = _queries_from_input(query, each=each)
    if each:
        _run_each_search(
            runtime,
            queries,
            page=page,
            per_page=per_page,
            sort=sort,
            search_field=search_field,
            fields=fields,
            facets=facets,
            adv_q=adv_q,
            filters=filters,
            output=output or runtime.config.output,
            all_pages=all_pages or stream,
            stream=stream,
            ids_only=ids_only,
            field=field,
            fail_if_empty=fail_if_empty,
        )
        return

    params = _search_params(
        query=queries[0] if queries else "",
        page=page,
        per_page=per_page,
        sort=sort,
        search_field=search_field,
        fields=fields,
        facets=facets,
        adv_q=adv_q,
    )
    params = apply_filter_params(params, filters)
    selected_output = "jsonl" if stream else output or runtime.config.output
    if stream:
        found = 0
        last_payload = {}
        for payload in _iter_search_payloads(
            runtime,
            params,
            all_pages=True,
            stream=True,
        ):
            last_payload = payload
            for item in iter_resources(payload):
                found += 1
                print_jsonl_item(item)
        if fail_if_empty and found == 0:
            raise typer.Exit(3)
        runtime.analytics.record_search(runtime.client, last_payload, query, params)
        return
    payloads = list(
        _iter_search_payloads(
            runtime,
            params,
            all_pages=all_pages or stream,
            stream=stream,
        )
    )
    resources = [item for payload in payloads for item in iter_resources(payload)]
    if fail_if_empty and not resources:
        raise typer.Exit(3)
    if ids_only:
        print_field_values(resources, "id")
    elif field:
        print_field_values(resources, field)
    elif selected_output in {"json", "jsonl"} and not all_pages:
        print_data(payloads[0], output=selected_output)
    elif selected_output == "jsonl":
        for item in resources:
            print_jsonl_item(item)
    elif selected_output == "json":
        print_data({"data": resources, "meta": _merged_meta(payloads)}, output="json")
    else:
        rows = [resource_summary(item) for item in resources]
        print_rows(rows, output=selected_output, columns=["id", "title", "year", "provider"])
    runtime.analytics.record_search(runtime.client, payloads[-1] if payloads else {}, query, params)


def grep(
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
    state: Annotated[
        Optional[str], typer.Option("--state", help="Shortcut for dct_spatial_sm.")
    ] = None,
    page: Annotated[int, typer.Option(help="Page number.")] = 1,
    per_page: Annotated[int, typer.Option(help="Results per page.")] = 25,
    all_pages: Annotated[bool, typer.Option("--all", help="Fetch every page.")] = False,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="jsonl, json, csv, or table.")
    ] = "jsonl",
    ids_only: Annotated[bool, typer.Option("--ids-only", help="Print only IDs.")] = False,
) -> None:
    filters = list(include or [])
    if state:
        filters.append(f"dct_spatial_sm={state}")
    search(
        ctx,
        query=query,
        include=filters,
        exclude=exclude,
        page=page,
        per_page=per_page,
        sort=None,
        search_field=None,
        fields=None,
        facets=None,
        adv_q=None,
        output=output,
        all_pages=all_pages,
        stream=output == "jsonl" and all_pages,
        each=False,
        ids_only=ids_only,
        field=None,
        fail_if_empty=False,
    )


def context(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Research topic or keyword query.")],
    per_page: Annotated[int, typer.Option(help="Number of resources to include.")] = 10,
    format: Annotated[str, typer.Option("--format", "-f", help="markdown or json.")] = "markdown",
) -> None:
    runtime: Runtime = ctx.obj
    params = {"q": query, "page": 1, "per_page": per_page}
    payload = runtime.client.get("/search", params=params)
    resources = list(iter_resources(payload))
    if format == "json":
        print_data({"query": query, "resources": resources}, output="json")
        return
    print(f"# BTAA Geospatial Context: {query}\n")
    for item in resources:
        summary = resource_summary(item)
        attrs = item.get("attributes", {}) if isinstance(item, dict) else {}
        ogm = attrs.get("ogm", attrs) if isinstance(attrs, dict) else {}
        description = ogm.get("dct_description_sm") or attrs.get("description") or ""
        if isinstance(description, list):
            description = " ".join(str(value) for value in description[:2])
        print(f"## {summary['title'] or summary['id']}")
        print(f"- ID: {summary['id']}")
        if summary["year"]:
            print(f"- Year: {summary['year']}")
        if summary["provider"]:
            print(f"- Provider: {summary['provider']}")
        if description:
            print(f"- Description: {description}")
        print()


def _search_params(
    *,
    query: str,
    page: int,
    per_page: int,
    sort: str | None,
    search_field: str | None,
    fields: str | None,
    facets: str | None,
    adv_q: str | None,
) -> dict[str, object]:
    params: dict[str, object] = {
        "q": query,
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
    return params


def _iter_search_payloads(
    runtime: Runtime,
    params: dict[str, object],
    *,
    all_pages: bool,
    stream: bool,
):
    current_page = int(params.get("page", 1))
    while True:
        params["page"] = current_page
        payload = runtime.client.get("/search", params=params)
        yield payload
        if not all_pages:
            break
        meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        total_pages = meta.get("totalPages") or meta.get("total_pages")
        if total_pages is not None and current_page >= int(total_pages):
            break
        resources = list(iter_resources(payload))
        if not resources:
            break
        current_page += 1
        if stream:
            typer.echo(f"Fetched page {current_page - 1}", err=True)


def _queries_from_input(query: str | None, *, each: bool) -> list[str]:
    if query == "-" or each:
        text = sys.stdin.read()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if query and query != "-":
            return [query, *lines]
        return lines
    return [query or ""]


def _run_each_search(
    runtime: Runtime,
    queries: list[str],
    *,
    page: int,
    per_page: int,
    sort: str | None,
    search_field: str | None,
    fields: str | None,
    facets: str | None,
    adv_q: str | None,
    filters,
    output: str,
    all_pages: bool,
    stream: bool,
    ids_only: bool,
    field: str | None,
    fail_if_empty: bool,
) -> None:
    found = 0
    for item in _iter_each_resource(
        runtime,
        queries,
        page=page,
        per_page=per_page,
        sort=sort,
        search_field=search_field,
        fields=fields,
        facets=facets,
        adv_q=adv_q,
        filters=filters,
        all_pages=all_pages,
        stream=stream,
    ):
        found += 1
        if ids_only:
            print(item.get("id", ""))
        elif field:
            print_field_values([item], field)
        elif output == "jsonl":
            print_jsonl_item(item)
        else:
            print_data(item, output="json")
    if fail_if_empty and found == 0:
        raise typer.Exit(3)


def _iter_each_resource(
    runtime: Runtime,
    queries: list[str],
    *,
    page: int,
    per_page: int,
    sort: str | None,
    search_field: str | None,
    fields: str | None,
    facets: str | None,
    adv_q: str | None,
    filters,
    all_pages: bool,
    stream: bool,
):
    for query in queries:
        params = _search_params(
            query=query,
            page=page,
            per_page=per_page,
            sort=sort,
            search_field=search_field,
            fields=fields,
            facets=facets,
            adv_q=adv_q,
        )
        params = apply_filter_params(params, filters)
        for payload in _iter_search_payloads(runtime, params, all_pages=all_pages, stream=stream):
            for item in iter_resources(payload):
                item["_query"] = query
                yield item


def _merged_meta(payloads: list[dict]) -> dict[str, object]:
    if not payloads:
        return {}
    meta = payloads[-1].get("meta", {}) if isinstance(payloads[-1], dict) else {}
    total = 0
    for payload in payloads:
        page_meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
        total += len(list(iter_resources(payload)))
        if "totalCount" in page_meta:
            meta["totalCount"] = page_meta["totalCount"]
    meta["returnedCount"] = total
    return meta
