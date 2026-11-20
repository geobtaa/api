"""Scoped Source and Set spreadsheet exchange routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from app import catalog_csv as exchange
from app.api.contracts import CSV_RESPONSE
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.csv_exchange import csv_line


def routes(spec):
    router = APIRouter(prefix=f"/admin/{spec.name}/csv", tags=[spec.name])
    Reader = Annotated[Actor, Depends(require_permissions(spec.service.READ))]
    writes = [Depends(mutation_header)]

    def attachment(name):
        return {
            "Content-Disposition": f'attachment; filename="{spec.name}-{name}.csv"',
            "Cache-Control": "no-store",
        }

    @router.get(
        "/template",
        response_class=Response,
        responses=CSV_RESPONSE,
        operation_id=f"{spec.name}_csv_template",
        summary=f"Download {spec.name} CSV template",
    )
    async def template(actor: Reader):
        spec.authorize(actor)
        return Response(
            csv_line(spec.columns()), media_type="text/csv", headers=attachment("template")
        )

    @router.get(
        "/export",
        response_class=Response,
        responses=CSV_RESPONSE,
        operation_id=f"{spec.name}_csv_export",
        summary=f"Export {spec.name} for editing",
    )
    async def export(actor: Reader, database: Database):
        spec.authorize(actor)

        async def stream():
            async with database.connect() as connection:
                async for line in exchange.export(connection, spec, actor):
                    yield line

        return StreamingResponse(stream(), media_type="text/csv", headers=attachment("export"))

    @router.post(
        "/preview",
        response_model=exchange.CatalogCsvReport,
        dependencies=writes,
        operation_id=f"{spec.name}_csv_preview",
        summary=f"Preview {spec.name} CSV changes",
    )
    async def preview(command: exchange.CatalogCsvRequest, actor: Reader, database: Database):
        return await exchange.preview(database, spec, actor, command)

    @router.post(
        "/import",
        response_model=exchange.CatalogCsvReport,
        dependencies=writes,
        operation_id=f"{spec.name}_csv_import",
        summary=f"Apply reviewed {spec.name} CSV changes",
    )
    async def apply(
        command: exchange.CatalogCsvCommit,
        actor: Reader,
        database: Database,
        key: RequestKey,
        request: Request,
    ):
        return await exchange.apply(
            database, spec, actor, command, key, request.app.state.settings.app_version
        )

    return router
