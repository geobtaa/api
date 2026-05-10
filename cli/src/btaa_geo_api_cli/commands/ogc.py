from __future__ import annotations

from typing import Annotated, Optional

import typer

from ..output import print_data
from ..runtime import Runtime

app = typer.Typer(help="Use OGC API Records facade endpoints.")


@app.command()
def landing(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(runtime.client.get("/ogc/"), output=output or "json")


@app.command()
def collections(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(runtime.client.get("/ogc/collections"), output=output or "json")


@app.command()
def queryables(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(
        runtime.client.get("/ogc/collections/btaa-records/queryables"), output=output or "json"
    )


@app.command()
def sortables(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(
        runtime.client.get("/ogc/collections/btaa-records/sortables"), output=output or "json"
    )


@app.command()
def items(
    ctx: typer.Context,
    q: Annotated[Optional[str], typer.Option()] = None,
    bbox: Annotated[Optional[str], typer.Option()] = None,
    page: Annotated[int, typer.Option()] = 1,
    limit: Annotated[int, typer.Option()] = 10,
    sortby: Annotated[Optional[str], typer.Option()] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    params = {"page": page, "limit": limit}
    if q:
        params["q"] = q
    if bbox:
        params["bbox"] = bbox
    if sortby:
        params["sortby"] = sortby
    print_data(
        runtime.client.get("/ogc/collections/btaa-records/items", params=params),
        output=output or "json",
    )


@app.command("item")
def item(
    ctx: typer.Context,
    record_id: str,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    print_data(
        runtime.client.get(f"/ogc/collections/btaa-records/items/{record_id}"),
        output=output or "json",
    )
