import logging
import os
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.endpoints import router as public_router
from app.elasticsearch import close_elasticsearch, init_elasticsearch
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from db.config import DATABASE_URL
from db.database import database

# Load environment variables from .env file
load_dotenv()

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
cors_origins_env = os.getenv("CORS_ORIGINS", "*")
cors_origins = cors_origins_env.split(",") if cors_origins_env != "*" else ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application."""
    # Startup
    try:
        await database.connect()
        logger.info("Connected to database")
    except Exception as e:
        # Log a safe, redacted view of the database URL for easier diagnosis
        try:
            parsed = urlparse(DATABASE_URL) if DATABASE_URL else None
            if parsed:
                safe_location = f"{parsed.hostname or ''}{parsed.path or ''}"
            else:
                safe_location = "<unknown>"
        except Exception:
            safe_location = "<unparseable>"

        logger.error(
            "Failed to connect to database at %s: %s",
            safe_location,
            str(e),
        )
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


# Create FastAPI application
app = FastAPI(
    title="BTAA Geospatial API",
    version="0.2.0-pre-release",
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# Optional: compress responses (negotiated via Accept-Encoding)
# - GZipMiddleware supports gzip only; brotli should typically be handled at the edge
#   (e.g., CDN/Nginx).
# - Disabled automatically during tests to avoid surprising header-level assertions.
def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


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
        # Allow cross-origin resource loading
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        # Only set COEP/COOP if not already set by endpoint
        if "Cross-Origin-Embedder-Policy" not in response.headers:
            response.headers["Cross-Origin-Embedder-Policy"] = "unsafe-none"
        if "Cross-Origin-Opener-Policy" not in response.headers:
            response.headers["Cross-Origin-Opener-Policy"] = "unsafe-none"

        # Prevent search engine indexing - app is in development
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"

        return response


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
    ],
    expose_headers=[
        "Content-Type",
        "Content-Length",
        "X-Total-Count",
        "Link",
    ],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add cross-origin headers middleware
app.add_middleware(CrossOriginHeadersMiddleware)

# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(public_router, prefix="/api/v1")


@app.get("/api/v1", include_in_schema=False)
async def api_v1_no_slash_redirect():
    # Ensure /api/v1 (no trailing slash) works by redirecting to the canonical /api/v1/
    return RedirectResponse(url="/api/v1/")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for the application."""
    logger.error(f"Global exception handler caught: {str(exc)}", exc_info=True)

    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred",
            "error": str(exc),
        },
    )


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

# Institution-branded docs assets (monorepo: static/templates at repo root)
# Use absolute paths based on known container structure, or relative paths when not in Docker
# Check if we're in Docker by looking for /app directory, otherwise use relative paths
if os.path.exists("/app"):
    STATIC_DIR = os.path.join("/app", "static")
    TEMPLATES_DIR = os.path.join("/app", "templates")
else:
    # When running outside Docker (e.g., tests), use relative paths from backend/
    # Go up to repo root, then to static/templates
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(backend_dir)
    STATIC_DIR = os.path.join(repo_root, "static")
    TEMPLATES_DIR = os.path.join(repo_root, "templates")

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
    if templates is None or not template_path or not os.path.exists(template_path):
        # If templates aren't available (e.g., in tests), return a simple HTML response
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>BTAA Geospatial API — Endpoints</title></head>
                <body>
                    <h1>BTAA Geospatial API — Endpoints</h1>
                    <p>Templates not available. Please check the templates directory.</p>
                    <p><a href="{app.openapi_url}">OpenAPI Schema</a></p>
                </body>
            </html>
            """
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
        # If template rendering fails, return a simple HTML response
        return HTMLResponse(
            content=f"""
            <html>
                <head><title>BTAA Geospatial API — Endpoints</title></head>
                <body>
                    <h1>BTAA Geospatial API — Endpoints</h1>
                    <p>Template rendering failed. Please check the templates directory.</p>
                    <p><a href="{app.openapi_url}">OpenAPI Schema</a></p>
                </body>
            </html>
            """
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
