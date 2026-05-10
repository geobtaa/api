from __future__ import annotations

from typing import Annotated, Optional

import typer

from ..output import print_data
from ..runtime import Runtime

app = typer.Typer(help="Internal admin and operations commands.")


repos_app = typer.Typer(help="OpenGeoMetadata repository admin commands.")
harvest_app = typer.Typer(help="OpenGeoMetadata harvest commands.")
bridge_app = typer.Typer(help="Bridge sync commands.")

app.add_typer(repos_app, name="repos")
app.add_typer(harvest_app, name="harvest")
app.add_typer(bridge_app, name="bridge")


@repos_app.command("list")
def list_repos(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(runtime.client.get("/admin/ogm/repos"), output=output or "json")


@repos_app.command("enable")
def enable_repo(
    ctx: typer.Context,
    repo_name: Annotated[str, typer.Argument()],
    watch: Annotated[
        str, typer.Option("--watch", help="Watch mode, for example weekly.")
    ] = "weekly",
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    payload = {"ogm_enabled": True, "ogm_watch_mode": watch}
    print_data(
        runtime.client.request("PATCH", f"/admin/ogm/repos/{repo_name}", json=payload),
        output=output or "json",
    )


@harvest_app.command("run")
def run_harvest(
    ctx: typer.Context,
    repo_name: Annotated[Optional[str], typer.Option("--repo")] = None,
    all_weekly: Annotated[bool, typer.Option("--all-weekly")] = False,
    trigger: Annotated[str, typer.Option("--trigger")] = "manual",
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    payload = {"ogm_trigger": "weekly" if all_weekly else trigger}
    if all_weekly:
        payload["ogm_all"] = True
    elif repo_name:
        payload["ogm_repo_name"] = repo_name
    else:
        raise typer.BadParameter("Use --repo REPO_NAME or --all-weekly.")
    print_data(runtime.client.post("/admin/ogm/harvest", json=payload), output=output or "json")
    runtime.analytics.record_event(runtime.client, "cli.command.admin.harvest", properties=payload)


@harvest_app.command("runs")
def harvest_runs(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(runtime.client.get("/admin/ogm/harvest/runs"), output=output or "json")


@bridge_app.command("sync")
def bridge_sync(
    ctx: typer.Context,
    resource_id: Annotated[Optional[str], typer.Option("--resource-id")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json",
) -> None:
    runtime: Runtime = ctx.obj
    payload = {"trigger": "manual"}
    if resource_id:
        payload["resource_id"] = resource_id
    print_data(runtime.client.post("/admin/bridge/sync", json=payload), output=output or "json")


@bridge_app.command("status")
def bridge_status(
    ctx: typer.Context, output: Annotated[Optional[str], typer.Option("--output", "-o")] = "json"
) -> None:
    runtime: Runtime = ctx.obj
    print_data(runtime.client.get("/admin/bridge/sync/status"), output=output or "json")
