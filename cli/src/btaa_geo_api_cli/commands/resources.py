from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ..output import print_data
from ..runtime import Runtime

app = typer.Typer(help="Inspect resources, metadata, downloads, and citations.")


@app.command("get")
def get_resource(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    fields: Annotated[Optional[str], typer.Option()] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    params = {"fields": fields} if fields else None
    payload = runtime.client.get(f"/resources/{resource_id}", params=params)
    print_data(payload, output=output or "json")
    runtime.analytics.record_event(
        runtime.client, "cli.command.get", properties={}, resource_id=resource_id
    )


@app.command()
def metadata(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    format: Annotated[
        str, typer.Option("--format", "-f", help="combined, ogm, b1g, display")
    ] = "combined",
    fields: Annotated[Optional[str], typer.Option()] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    suffix = "" if format == "combined" else f"/{format}"
    params = {"fields": fields} if fields else None
    payload = runtime.client.get(f"/resources/{resource_id}/metadata{suffix}", params=params)
    print_data(payload, output=output or "json")
    runtime.analytics.record_event(
        runtime.client,
        "cli.command.metadata",
        properties={"format": format},
        resource_id=resource_id,
    )


@app.command()
def cite(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    format: Annotated[
        str, typer.Option("--format", "-f", help="json, json-ld, ris, bibtex")
    ] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    suffix = "" if format == "json" else f"/{format}"
    payload = runtime.client.get(f"/resources/{resource_id}/citation{suffix}")
    if isinstance(payload, str):
        print(payload)
    else:
        print_data(payload, output="json")
    runtime.analytics.record_event(
        runtime.client, "cli.command.cite", properties={"format": format}, resource_id=resource_id
    )


@app.command()
def downloads(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    payload = runtime.client.get(f"/resources/{resource_id}/downloads")
    print_data(payload, output=output or "json")
    runtime.analytics.record_event(
        runtime.client, "cli.command.download", properties={"mode": "list"}, resource_id=resource_id
    )


@app.command()
def download(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    out: Annotated[Path, typer.Option("--out", help="Output directory.")] = Path("."),
    type: Annotated[Optional[str], typer.Option("--type", help="Download type to select.")] = None,
    best: Annotated[bool, typer.Option("--best", help="Use the first available download.")] = False,
    filename: Annotated[Optional[str], typer.Option("--filename")] = None,
    no_clobber: Annotated[bool, typer.Option("--no-clobber")] = False,
) -> None:
    runtime: Runtime = ctx.obj
    payload = runtime.client.get(f"/resources/{resource_id}/downloads")
    selected = select_download(payload, preferred_type=type, best=best)
    url = selected.get("url") or selected.get("href") or selected.get("download_url")
    if not url and selected.get("download_type"):
        generated = runtime.client.get(
            f"/resources/{resource_id}/downloads/generated/{selected['download_type']}"
        )
        url = (
            generated.get("file_url")
            or generated.get("url")
            or f"/resources/{resource_id}/downloads/generated/{selected['download_type']}/file"
        )
    if not url:
        raise typer.BadParameter("No downloadable URL found for this resource.")
    name = (
        filename or selected.get("file_name") or selected.get("label") or f"{resource_id}.download"
    )
    safe_name = str(name).replace("/", "_")
    output_path = out / safe_name
    if no_clobber and output_path.exists():
        raise typer.BadParameter(f"Output exists: {output_path}")
    bytes_written, content_type = runtime.client.stream_download(str(url), output_path)
    typer.echo(f"Downloaded {bytes_written} bytes to {output_path}")
    runtime.analytics.record_event(
        runtime.client,
        "cli.command.download",
        properties={"bytes": bytes_written, "content_type": content_type, "type": type or "best"},
        resource_id=resource_id,
    )


def select_download(payload: dict, *, preferred_type: str | None, best: bool) -> dict:
    downloads = payload.get("downloads", []) if isinstance(payload, dict) else []
    if not isinstance(downloads, list) or not downloads:
        raise typer.BadParameter("No downloads available for this resource.")
    if preferred_type:
        lowered = preferred_type.lower()
        for item in downloads:
            haystack = " ".join(
                str(item.get(k, "")) for k in ("type", "download_type", "label", "format")
            ).lower()
            if lowered in haystack:
                return item
        raise typer.BadParameter(f"No download matches type '{preferred_type}'.")
    if best or len(downloads) == 1:
        return downloads[0]
    raise typer.BadParameter("Multiple downloads available. Use --best or --type.")
