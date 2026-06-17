import logging
import os
import sys
from contextlib import asynccontextmanager

try:
    import appsignal
except ImportError:
    appsignal = None  # Optional: not installed in minimal/test envs

try:
    from opentelemetry import trace
except ImportError:
    trace = None  # Optional: requires appsignal/otel stack

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
except ImportError:
    FastAPIInstrumentor = None  # Optional: requires appsignal/otel stack
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.errors import (
    RequestIDMiddleware,
    get_request_id,
    http_exception_handler,
    internal_server_error_response,
    validation_exception_handler,
)
from app.api.ogc import router as ogc_router
from app.api.v1.endpoints import router as public_router
from app.elasticsearch import close_elasticsearch, init_elasticsearch
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.middleware.turnstile_middleware import TurnstileMiddleware
from app.services.sitemap_service import (
    SITEMAP_ROOT_NAME,
    build_robots_txt,
    build_x_robots_tag,
    close_store,
    generate_and_store,
    get_current_sitemap_document,
    is_valid_sitemap_part_name,
)
from db.async_engine import dispose_app_async_engines
from db.database import database
from db.sync_engine import dispose_app_sync_engines

# Load environment variables from .env file
load_dotenv()


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


APPSIGNAL_ENABLED = (
    appsignal is not None
    and os.getenv("APP_ENV") != "test"
    and _env_flag("APPSIGNAL_BACKEND_ACTIVE", os.getenv("APPSIGNAL_ACTIVE", "true"))
)

if APPSIGNAL_ENABLED:
    appsignal.start()

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log"),
    ],
)
logger = logging.getLogger(__name__)

# Get CORS configuration from environment variable
# For production public APIs, we allow all origins
cors_origins_env = os.getenv("CORS_ORIGINS", "*").strip()
if cors_origins_env == "*":
    cors_origins = ["*"]
else:
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
# In non-production, always allow common local dev origins so frontend on 3000/5173 works
_dev_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if cors_origins != ["*"] and os.getenv("APP_ENV") != "production":
    for origin in _dev_origins:
        if origin not in cors_origins:
            cors_origins.append(origin)

# In dev, allow all origins so CORS never blocks local frontend. Set APP_ENV=production to restrict.
if os.getenv("APP_ENV") not in ("production", "test"):
    cors_origins = ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    try:
        await database.connect()
        logger.info("Connected to database")
    except Exception as e:
        # Log a safe, redacted view of the database URL for easier diagnosis
        logger.error("Failed to connect to database: %s", str(e))
        raise

    try:
        await init_elasticsearch()
        logger.info("Connected to Elasticsearch")
    except Exception as e:
        logger.error(f"Failed to connect to Elasticsearch: {str(e)}")
        # Don't raise the exception, allow the app to start without Elasticsearch

    yield

    # Shutdown
    try:
        await database.disconnect()
        logger.info("Disconnected from database")
    except Exception as e:
        logger.error(f"Error disconnecting from database: {str(e)}")

    try:
        await close_elasticsearch()
        logger.info("Disconnected from Elasticsearch")
    except Exception as e:
        logger.error(f"Error disconnecting from Elasticsearch: {str(e)}")

    try:
        await close_store()
    except Exception as e:
        logger.error(f"Error disconnecting from sitemap store: {str(e)}")

    try:
        await dispose_app_async_engines()
        dispose_app_sync_engines()
        logger.info("Disposed SQLAlchemy engines")
    except Exception as e:
        logger.error(f"Error disposing SQLAlchemy engines: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title="BTAA Geospatial API",
    version="0.8.7",
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

if FastAPIInstrumentor is not None and APPSIGNAL_ENABLED:
    FastAPIInstrumentor().instrument_app(app)


# Optional: compress responses (negotiated via Accept-Encoding)
# - GZipMiddleware supports gzip only; brotli should typically be handled at the edge
#   (e.g., CDN/Nginx).
# - Disabled automatically during tests to avoid surprising header-level assertions.
if os.getenv("APP_ENV") != "test" and _env_flag("ENABLE_RESPONSE_COMPRESSION", "true"):
    gzip_minimum_size = int(os.getenv("GZIP_MINIMUM_SIZE", "1000"))
    gzip_compresslevel = int(os.getenv("GZIP_COMPRESSLEVEL", "6"))
    app.add_middleware(
        GZipMiddleware,
        minimum_size=gzip_minimum_size,
        compresslevel=gzip_compresslevel,
    )


# Custom middleware to add security headers for cross-origin access
class CrossOriginHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Ensure CORS header on every response (errors may bypass CORSMiddleware).
        origin = request.headers.get("origin")
        if origin and "Access-Control-Allow-Origin" not in response.headers:
            if cors_origins == ["*"]:
                response.headers["Access-Control-Allow-Origin"] = "*"
            elif origin in cors_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
        # Allow cross-origin resource loading
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        # Only set COEP/COOP if not already set by endpoint
        if "Cross-Origin-Embedder-Policy" not in response.headers:
            response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        if "Cross-Origin-Opener-Policy" not in response.headers:
            response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"

        robots_tag = build_x_robots_tag()
        if robots_tag:
            response.headers["X-Robots-Tag"] = robots_tag

        return response


def _set_appsignal_route_name(request: Request) -> None:
    if not APPSIGNAL_ENABLED:
        return

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        root_path = request.scope.get("root_path") or ""
        action_name = f"{request.method} {root_path}{route_path}"
    else:
        action_name = f"{request.method} unmatched_route"

    tracing = getattr(appsignal, "tracing", None)
    for setter_name in ("set_name", "set_root_name"):
        setter = getattr(tracing, setter_name, None) if tracing is not None else None
        if callable(setter):
            setter(action_name)

    if trace is not None:
        current_span = trace.get_current_span()
        if current_span is not None:
            try:
                current_span.update_name(action_name)
                if route_path:
                    current_span.set_attribute("http.route", route_path)
            except Exception:
                logger.debug("Unable to set OpenTelemetry route name", exc_info=True)


class AppSignalRouteNameMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        finally:
            _set_appsignal_route_name(request)


# Add CORS middleware - Permissive for public API
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "User-Agent",
        "DNT",
        "Cache-Control",
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Visit-Token",
        "X-BTAA-Client-Name",
        "X-BTAA-Client-Version",
        "X-BTAA-Client-Channel",
        "X-BTAA-Client-Instance",
        "X-Turnstile-Session",
    ],
    expose_headers=[
        "Content-Type",
        "Content-Length",
        "X-Total-Count",
        "Link",
        "X-Turnstile-Required",
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add cross-origin headers middleware
app.add_middleware(CrossOriginHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Add Cloudflare Turnstile browser gate middleware
app.add_middleware(TurnstileMiddleware)

# Keep AppSignal incident grouping stable even when instrumentation sees raw URLs.
app.add_middleware(AppSignalRouteNameMiddleware)

# Add request IDs after other middleware so it runs first in the Starlette stack.
app.add_middleware(RequestIDMiddleware)

# Include routers
app.include_router(public_router, prefix="/api/v1")
app.include_router(ogc_router, prefix="/api/v1/ogc")

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/api/v1", include_in_schema=False)
async def api_v1_no_slash_redirect():
    # Ensure /api/v1 (no trailing slash) works by redirecting to the canonical /api/v1/
    return RedirectResponse(url="/api/v1/")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    xml_content = await get_current_sitemap_document(SITEMAP_ROOT_NAME)
    if xml_content is None:
        result, _stored = await generate_and_store()
        xml_content = result.documents[SITEMAP_ROOT_NAME]

    response = Response(content=xml_content, media_type="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.get("/sitemaps/{filename}.xml", include_in_schema=False)
async def sitemap_part_xml(filename: str) -> Response:
    part_name = f"{filename}.xml"
    if not is_valid_sitemap_part_name(part_name):
        raise HTTPException(status_code=404, detail="Sitemap part not found")

    xml_content = await get_current_sitemap_document(part_name)
    if xml_content is None:
        result, _stored = await generate_and_store()
        xml_content = result.documents.get(part_name)
        if xml_content is None:
            raise HTTPException(status_code=404, detail="Sitemap part not found")

    response = Response(content=xml_content, media_type="application/xml")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    response = PlainTextResponse(build_robots_txt())
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for the application."""
    request_id = get_request_id(request)
    logger.error(
        "Global exception handler caught request_id=%s path=%s",
        request_id,
        request.url.path,
        exc_info=True,
    )

    if isinstance(exc, HTTPException):
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response

    return internal_server_error_response(request)


# Frontend is now served by React Router v7 in a separate Docker container
# No need to serve static files here - React Router v7 handles all frontend routing

# Frontend directory path (monorepo: frontend is at repo root, backend is in backend/)
# From /app/backend/app/main.py: go up 2 levels to /app, then to frontend/dist
# Use absolute path based on known container structure
# COMMENTED OUT: Frontend is now served by React Router v7
# FRONTEND_DIR = os.path.join("/app", "frontend", "dist")

# Serve static assets directly (CSS, JS, images, etc.)
# COMMENTED OUT: Frontend is now served by React Router v7
# assets_dir = os.path.join(FRONTEND_DIR, "assets")
# if os.path.exists(assets_dir):
#     app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Institution-branded docs assets
# Use absolute paths based on known container structure, or relative paths when not in Docker
# Check if we're in Docker by looking for /app directory, otherwise use relative paths
if os.path.exists("/app"):
    # In Docker: check both possible locations
    # - Production (Dockerfile.kamal): /app/templates and /app/static
    # - Development (docker-compose): /app/backend/templates and /app/backend/static
    # Check if template file exists in production location first
    prod_template = os.path.join("/app", "templates", "docs.html")
    dev_template = os.path.join("/app", "backend", "templates", "docs.html")
    if os.path.exists(prod_template):
        # Production: templates copied to /app/templates
        STATIC_DIR = os.path.join("/app", "static")
        TEMPLATES_DIR = os.path.join("/app", "templates")
    elif os.path.exists(dev_template):
        # Development: templates at /app/backend/templates (mounted volume)
        STATIC_DIR = os.path.join("/app", "backend", "static")
        TEMPLATES_DIR = os.path.join("/app", "backend", "templates")
    else:
        # Fallback: try production directories even if template doesn't exist yet
        STATIC_DIR = os.path.join("/app", "static")
        TEMPLATES_DIR = os.path.join("/app", "templates")
else:
    # When running outside Docker, use paths relative to backend directory
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STATIC_DIR = os.path.join(backend_dir, "static")
    TEMPLATES_DIR = os.path.join(backend_dir, "templates")

# Only create directories if they don't exist and we have write access
# Skip in test environments where these directories may not be needed
try:
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
except (OSError, PermissionError):
    # If we can't create directories (e.g., read-only filesystem in tests), continue anyway
    # The static file serving will just fail gracefully if directories don't exist
    pass

# Only mount static files if directory exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Create templates object only if directory exists
if os.path.exists(TEMPLATES_DIR):
    templates = Jinja2Templates(directory=TEMPLATES_DIR)
else:
    # Create a dummy templates object for tests (won't be used if templates don't exist)
    templates = None


@app.get("/api/docs", include_in_schema=False)
async def custom_docs(request: Request) -> HTMLResponse:
    # Check if templates are available and the template file exists
    template_path = os.path.join(TEMPLATES_DIR, "docs.html") if TEMPLATES_DIR else None
    # Construct OAuth2 redirect URL (since docs_url=None, we need to build it manually)
    oauth2_redirect_url = str(request.url_for("swagger_oauth2_redirect"))
    if templates is None or not template_path or not os.path.exists(template_path):
        # Fallback to FastAPI's built-in Swagger UI if templates aren't available
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " — Swagger UI",
            oauth2_redirect_url=oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )
    try:
        return templates.TemplateResponse(
            "docs.html",
            {
                "request": request,
                "title": "BTAA Geospatial API — Endpoints",
                "openapi_url": app.openapi_url,
            },
        )
    except Exception:
        # Fallback to FastAPI's built-in Swagger UI if template rendering fails
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " — Swagger UI",
            oauth2_redirect_url=oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )


@app.get("/api/docs/oauth2-redirect", include_in_schema=False)
async def swagger_oauth2_redirect() -> HTMLResponse:
    return HTMLResponse(get_swagger_ui_oauth2_redirect_html())


# Optional: serve common static files
# COMMENTED OUT: Frontend is now served by React Router v7
# @app.get("/robots.txt")
# async def robots():
#     robots_path = os.path.join(FRONTEND_DIR, "robots.txt")
#     if os.path.isfile(robots_path):
#         return FileResponse(robots_path)
#     return JSONResponse(content={"message": "robots.txt not found"}, status_code=404)


# @app.get("/favicon.ico")
# async def favicon():
#     favicon_path = os.path.join(FRONTEND_DIR, "favicon.ico")
#     if os.path.isfile(favicon_path):
#         return FileResponse(favicon_path)
#     return JSONResponse(content={"message": "favicon.ico not found"}, status_code=404)


# SPA fallback: any other path → index.html unless a file exists
# COMMENTED OUT: Frontend is now served by React Router v7 in a separate container
# React Router v7 handles all frontend routing on port 3000
# @app.get("/{full_path:path}")
# async def spa_fallback(full_path: str):
#     """
#     SPA history fallback handler.
#     Serves static files if they exist, otherwise returns index.html for client-side routing.
#     """
#     # Skip API routes (they should be handled by the API router above)
#     if full_path.startswith("api/"):
#         return JSONResponse(content={"message": "API endpoint not found"}, status_code=404)
#
#     # Check if the requested path is a file that exists
#     candidate_path = os.path.join(FRONTEND_DIR, full_path)
#     if os.path.isfile(candidate_path):
#         return FileResponse(candidate_path)
#
#     # For any other path (including root), serve index.html for SPA routing
#     index_path = os.path.join(FRONTEND_DIR, "index.html")
#     if os.path.isfile(index_path):
#         return FileResponse(index_path)
#
#     # Fallback if index.html doesn't exist
#     return JSONResponse(
#         content={"message": "Frontend not found. Please build the React app."}, status_code=404
#     )


# Add uvicorn configuration for running the application directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
