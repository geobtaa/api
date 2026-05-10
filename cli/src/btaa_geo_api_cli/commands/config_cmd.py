from __future__ import annotations

import typer

from ..config import set_config_value

app = typer.Typer(help="Read and write CLI configuration.")


@app.command("set")
def set_value(key: str, value: str, profile: str = "default") -> None:
    path = set_config_value(key, value, profile=profile)
    typer.echo(f"Updated {path}")
