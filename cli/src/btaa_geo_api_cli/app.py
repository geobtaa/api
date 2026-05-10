from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from .analytics import CommandAnalytics
from .client import BtaaApiClient, BtaaApiError
from .commands import admin, config_cmd, facets, ogc, resources, schema, search
from .config import load_config
from .runtime import Runtime

app = typer.Typer(help="BTAA Geospatial API command line client.", no_args_is_help=True)

app.add_typer(schema.app, name="schema")
app.add_typer(ogc.app, name="ogc")
app.add_typer(config_cmd.app, name="config")
app.add_typer(admin.app, name="admin")
app.command("search")(search.search)
app.command("facets")(facets.facets)
app.command("get")(resources.get_resource)
app.command("metadata")(resources.metadata)
app.command("cite")(resources.cite)
app.command("downloads")(resources.downloads)
app.command("download")(resources.download)


@app.callback()
def callback(
    ctx: typer.Context,
    base_url: Annotated[Optional[str], typer.Option("--base-url", help="API base URL.")] = None,
    api_key: Annotated[Optional[str], typer.Option("--api-key", help="API key.")] = None,
    profile: Annotated[Optional[str], typer.Option("--profile", help="Config profile.")] = None,
    output: Annotated[
        Optional[str], typer.Option("--output", "-o", help="Default output format.")
    ] = None,
    no_analytics: Annotated[
        bool, typer.Option("--no-analytics", help="Disable analytics.")
    ] = False,
) -> None:
    config = load_config(
        profile=profile,
        base_url=base_url,
        api_key=api_key,
        output=output,
        analytics=False if no_analytics else None,
    )
    client = BtaaApiClient(config)
    analytics = CommandAnalytics(config=config, no_analytics=no_analytics)
    ctx.obj = Runtime(config=config, client=client, analytics=analytics)


def main() -> None:
    try:
        app()
    except BtaaApiError as exc:
        typer.echo(f"API error: {exc}", err=True)
        if exc.error_code == "turnstile_required":
            typer.echo(
                "This API endpoint requires either an API key or a local/dev server with "
                "Turnstile disabled. Try setting BTAA_GEO_API_KEY or "
                "BTAA_GEO_API_BASE_URL=http://localhost:8000/api/v1.",
                err=True,
            )
        sys.exit(exc.status_code or 1)


if __name__ == "__main__":
    main()
