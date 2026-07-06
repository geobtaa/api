from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from geomg.data import store

PACKAGE_ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="GEOMG Admin Prototype",
    description="Standalone local prototype for GEOMG metadata administration.",
    version="0.1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(PACKAGE_ROOT / "static")),
    name="geomg_static",
)

templates = Jinja2Templates(directory=str(PACKAGE_ROOT / "templates"))


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/resources", status_code=303)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "geomg_prototype"}


@app.get("/resources")
def list_resources(
    request: Request,
    q: str | None = None,
    resource_class: str | None = None,
    resource_type: str | None = None,
    provider: str | None = None,
    publisher: str | None = None,
    publication_state: str | None = None,
):
    resources = store.list_resources(
        query=q,
        resource_class=resource_class,
        resource_type=resource_type,
        provider=provider,
        publisher=publisher,
        publication_state=publication_state,
    )
    return templates.TemplateResponse(
        request=request,
        name="geomg/resources.html",
        context={
            "request": request,
            "resources": resources,
            "imports": store.imports,
            "resource_classes": store.resource_classes,
            "resource_types": store.resource_types,
            "providers": store.providers,
            "publishers": store.publishers,
            "publication_states": store.publication_states,
            "filters": {
                "q": q or "",
                "resource_class": resource_class or "",
                "resource_type": resource_type or "",
                "provider": provider or "",
                "publisher": publisher or "",
                "publication_state": publication_state or "",
            },
            "total_count": len(store.list_resources()),
        },
    )


@app.get("/resources/{resource_id}")
def resource_detail(request: Request, resource_id: str):
    resource = store.get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return templates.TemplateResponse(
        request=request,
        name="geomg/resource_detail.html",
        context={
            "request": request,
            "resource": resource,
            "imports": store.imports,
            "publication_states": store.publication_states,
        },
    )


@app.get("/harvest-records")
def list_harvest_records(request: Request, q: str | None = None):
    harvest_records = store.list_harvest_records(query=q)
    return templates.TemplateResponse(
        request=request,
        name="geomg/harvest_records.html",
        context={
            "request": request,
            "harvest_records": harvest_records,
            "harvest_columns": store.harvest_columns,
            "filters": {"q": q or ""},
            "total_count": len(store.list_harvest_records()),
        },
    )


@app.get("/harvest-records/{harvest_id}")
def harvest_record_detail(request: Request, harvest_id: str):
    harvest_record = store.get_harvest_record(harvest_id)
    if harvest_record is None:
        raise HTTPException(status_code=404, detail="Harvest record not found")
    return templates.TemplateResponse(
        request=request,
        name="geomg/harvest_record_detail.html",
        context={
            "request": request,
            "harvest_record": harvest_record,
        },
    )
