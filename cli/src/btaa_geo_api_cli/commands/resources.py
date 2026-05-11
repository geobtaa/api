from __future__ import annotations

import sys
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
    resource_id: Annotated[Optional[str], typer.Argument()] = None,
    out: Annotated[Path, typer.Option("--out", help="Output directory.")] = Path("."),
    type: Annotated[Optional[str], typer.Option("--type", help="Download type to select.")] = None,
    best: Annotated[bool, typer.Option("--best", help="Use the first available download.")] = False,
    filename: Annotated[Optional[str], typer.Option("--filename")] = None,
    no_clobber: Annotated[bool, typer.Option("--no-clobber")] = False,
    ids: Annotated[
        Optional[str],
        typer.Option("--ids", help="Resource ID or '-' for newline-delimited IDs on stdin."),
    ] = None,
) -> None:
    runtime: Runtime = ctx.obj
    resource_ids = _resource_ids(resource_id, ids)
    for current_id in resource_ids:
        _download_one(
            runtime,
            current_id,
            out=out,
            type=type,
            best=best,
            filename=filename if len(resource_ids) == 1 else None,
            no_clobber=no_clobber,
        )


@app.command("thumbnail")
def thumbnail(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    out: Annotated[Path, typer.Option("--out", help="Output image path.")] = Path("thumbnail.png"),
    no_clobber: Annotated[bool, typer.Option("--no-clobber")] = False,
) -> None:
    _download_asset(ctx, resource_id, endpoint="thumbnail", out=out, no_clobber=no_clobber)


@app.command("static-map")
def static_map(
    ctx: typer.Context,
    resource_id: Annotated[str, typer.Argument()],
    out: Annotated[Path, typer.Option("--out", help="Output image path.")] = Path("static_map.png"),
    no_clobber: Annotated[bool, typer.Option("--no-clobber")] = False,
) -> None:
    _download_asset(ctx, resource_id, endpoint="static-map", out=out, no_clobber=no_clobber)


@app.command("open")
def open_resource(
    ctx: typer.Context,
    resource_or_query: Annotated[str, typer.Argument(help="Resource ID or search query.")],
    browser: Annotated[
        bool,
        typer.Option("--browser", help="Launch the URL with the operating system browser."),
    ] = False,
) -> None:
    runtime: Runtime = ctx.obj
    resource_id = resource_or_query
    if " " in resource_or_query:
        payload = runtime.client.get(
            "/search", params={"q": resource_or_query, "page": 1, "per_page": 1}
        )
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not data:
            raise typer.BadParameter("No resource matched that query.")
        resource_id = data[0].get("id", resource_or_query)
    url = _resource_view_url(runtime, resource_id)
    if browser:
        typer.launch(url)
    else:
        typer.echo(url)


def _download_one(
    runtime: Runtime,
    resource_id: str,
    *,
    out: Path,
    type: str | None,
    best: bool,
    filename: str | None,
    no_clobber: bool,
) -> None:
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


def _download_asset(
    ctx: typer.Context,
    resource_id: str,
    *,
    endpoint: str,
    out: Path,
    no_clobber: bool,
) -> None:
    if no_clobber and out.exists():
        raise typer.BadParameter(f"Output exists: {out}")
    runtime: Runtime = ctx.obj
    path = f"/resources/{resource_id}/{endpoint}"
    bytes_written, content_type = runtime.client.stream_download(path, out)
    typer.echo(f"Downloaded {bytes_written} bytes to {out}")
    runtime.analytics.record_event(
        runtime.client,
        f"cli.command.{endpoint.replace('-', '_')}",
        properties={"bytes": bytes_written, "content_type": content_type},
        resource_id=resource_id,
    )


def _resource_ids(resource_id: str | None, ids: str | None) -> list[str]:
    values: list[str] = []
    if resource_id:
        values.append(resource_id)
    if ids == "-":
        values.extend(line.strip() for line in sys.stdin.read().splitlines() if line.strip())
    elif ids:
        values.extend(part.strip() for part in ids.split(",") if part.strip())
    if not values:
        raise typer.BadParameter("Provide RESOURCE_ID or --ids.")
    return values


def _resource_view_url(runtime: Runtime, resource_id: str) -> str:
    api_base = runtime.client.base_url.rstrip("/")
    if api_base.endswith("/api/v1"):
        return f"{api_base[:-7]}/resources/{resource_id}"
    return runtime.client.resource_url(f"/resources/{resource_id}")


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
