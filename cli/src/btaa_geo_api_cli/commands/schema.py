from __future__ import annotations

from typing import Annotated, Optional

import typer

from .. import schema_registry
from ..output import print_data, print_rows
from ..runtime import Runtime

app = typer.Typer(help="Inspect searchable fields, facets, queryables, and sortables.")


def _print_values(values: list[str], *, output: str) -> None:
    rows = [{"name": value} for value in values]
    print_rows(rows, output=output, columns=["name"])


@app.callback(invoke_without_command=True)
def schema_root(
    ctx: typer.Context,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = None,
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    runtime: Runtime = ctx.obj
    _print_values(
        ["fields", "facets", "filters", "queryables", "sortables", "search-params"],
        output=output or runtime.config.output,
    )


@app.command()
def fields(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    runtime: Runtime = ctx.obj
    _print_values(schema_registry.SEARCH_FIELDS, output=output or runtime.config.output)
    runtime.analytics.record_event(
        runtime.client, "cli.command.schema", properties={"schema": "fields"}
    )


@app.command()
def facets(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    runtime: Runtime = ctx.obj
    _print_values(schema_registry.FACET_FIELDS, output=output or runtime.config.output)
    runtime.analytics.record_event(
        runtime.client, "cli.command.schema", properties={"schema": "facets"}
    )


@app.command()
def filters(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    facets(ctx, output=output)


@app.command("search-params")
def search_params(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    runtime: Runtime = ctx.obj
    _print_values(schema_registry.SEARCH_PARAMS, output=output or runtime.config.output)


@app.command()
def queryables(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    runtime: Runtime = ctx.obj
    payload = runtime.client.get("/ogc/collections/btaa-records/queryables")
    if (output or runtime.config.output) == "table":
        props = payload.get("properties", {}) if isinstance(payload, dict) else {}
        rows = [{"name": key, "type": value.get("type", "")} for key, value in props.items()]
        print_rows(rows, output="table", columns=["name", "type"])
    else:
        print_data(payload, output=output or runtime.config.output)
    runtime.analytics.record_event(
        runtime.client, "cli.command.schema", properties={"schema": "queryables"}
    )


@app.command()
def sortables(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = None
) -> None:
    runtime: Runtime = ctx.obj
    payload = runtime.client.get("/ogc/collections/btaa-records/sortables")
    if (output or runtime.config.output) == "table":
        props = payload.get("properties", {}) if isinstance(payload, dict) else {}
        rows = [{"name": key, "type": value.get("type", "")} for key, value in props.items()]
        print_rows(rows, output="table", columns=["name", "type"])
    else:
        print_data(payload, output=output or runtime.config.output)
    runtime.analytics.record_event(
        runtime.client, "cli.command.schema", properties={"schema": "sortables"}
    )
