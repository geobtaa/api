from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ..aardvark import CROSSWALK_TABLES, crosswalk, load_json_record, validate_aardvark
from ..output import print_data, print_jsonl_item, print_rows
from ..runtime import Runtime

app = typer.Typer(help="Validate and crosswalk OGM Aardvark metadata.")


@app.command()
def validate(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="Aardvark JSON file to validate.")],
    output: Annotated[Optional[str], typer.Option("--output", "-o", help="json or table.")] = None,
) -> None:
    runtime: Runtime = ctx.obj
    try:
        record = load_json_record(file)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    result = validate_aardvark(record)
    selected_output = output or runtime.config.output
    payload = {"valid": result.valid, "errors": result.errors}
    if selected_output == "table":
        if result.valid:
            print_rows(
                [{"status": "valid", "path": "", "message": ""}],
                output="table",
                columns=["status", "path", "message"],
            )
        else:
            rows = [{"status": "error", **error} for error in result.errors]
            print_rows(rows, output="table", columns=["status", "path", "message"])
    else:
        print_data(payload, output=selected_output)
    runtime.analytics.record_event(
        runtime.client,
        "cli.command.aardvark.validate",
        properties={"valid": result.valid},
    )
    if not result.valid:
        raise typer.Exit(1)


@app.command("crosswalk")
def crosswalk_cmd(
    ctx: typer.Context,
    file: Annotated[Path, typer.Argument(help="ISO 19139 or FGDC XML file to crosswalk.")],
    source: Annotated[str, typer.Option("--from", help="Source metadata standard: iso or fgdc.")],
    output: Annotated[str, typer.Option("--output", "-o", help="json or jsonl.")] = "json",
    validate_output: Annotated[
        bool, typer.Option("--validate", help="Validate the generated Aardvark record.")
    ] = False,
) -> None:
    runtime: Runtime = ctx.obj
    try:
        record = crosswalk(file, source.lower())
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if validate_output:
        result = validate_aardvark(record)
        payload = {"record": record, "validation": {"valid": result.valid, "errors": result.errors}}
    else:
        payload = record
    if output == "jsonl":
        print_jsonl_item(payload)
    else:
        print_data(payload, output=output)
    runtime.analytics.record_event(
        runtime.client,
        "cli.command.aardvark.crosswalk",
        properties={"source": source.lower(), "validate": validate_output},
    )


@app.command("crosswalks")
def crosswalks(
    ctx: typer.Context,
    source: Annotated[Optional[str], typer.Option("--from", help="iso or fgdc.")] = None,
    output: Annotated[Optional[str], typer.Option("--output", "-o")] = None,
) -> None:
    runtime: Runtime = ctx.obj
    selected_output = output or runtime.config.output
    if source:
        rows = CROSSWALK_TABLES[source.lower()]
    else:
        rows = [
            {"standard": source_name, **row}
            for source_name, table in CROSSWALK_TABLES.items()
            for row in table
        ]
    if selected_output == "table":
        if source:
            print_rows(rows, output="table", columns=["aardvark", "source"])
        else:
            print_rows(rows, output="table", columns=["standard", "aardvark", "source"])
    else:
        print_data(rows, output=selected_output)
    runtime.analytics.record_event(
        runtime.client,
        "cli.command.aardvark.crosswalks",
        properties={"source": source or "all"},
    )
