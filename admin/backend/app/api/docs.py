"""Presentation-only Swagger ordering; runtime route precedence stays unchanged."""

from fastapi import Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

# Swagger passes Immutable.js operation maps to operationsSorter.
# Read collection, read member, read member associations, then writes and utilities.
OPERATIONS_SORTER = """(a, b) => {
    const key = (operation) => {
        const path = operation.get("path");
        const method = operation.get("method").toLowerCase();
        const parts = path.replace(/^\\/api\\/v1\\/(?:admin\\/)?/, "").split("/");
        const member = parts[1]?.startsWith("{");
        const collection = parts.length === 1
            && operation.getIn(["operation", "tags"])?.includes(parts[0]);
        const rank = method === "get"
            ? (collection ? 0 : member ? (parts.length === 2 ? 1 : 2) : 3)
            : (collection ? 4 : member ? (parts.length === 2 ? 5 : 6) : 7);
        return [rank, member ? parts.slice(2).join("/") : path, path, method];
    };
    const left = key(a), right = key(b);
    for (let i = 0; i < left.length; i++) {
        if (left[i] < right[i]) return -1;
        if (left[i] > right[i]) return 1;
    }
    return 0;
}"""


async def swagger_docs(request: Request) -> HTMLResponse:
    root = request.scope.get("root_path", "").rstrip("/")
    response = get_swagger_ui_html(
        openapi_url=root + request.app.openapi_url,
        title=f"{request.app.title} - Swagger UI",
        swagger_ui_parameters={"operationsSorter": "geomgResourceOrder"},
    )
    # FastAPI serializes parameters as JSON. Replace only our fixed sentinel with
    # executable, server-owned JavaScript; no request content enters the function.
    return HTMLResponse(response.body.decode().replace('"geomgResourceOrder"', OPERATIONS_SORTER))
