import logging
import os
import sys
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_oauth2_redirect_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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

# Add rate limiting middleware (after CORS, before routes)
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


# Frontend directory path
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# Serve static assets directly (CSS, JS, images, etc.)
app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

# Institution-branded docs assets
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/api/docs", include_in_schema=False)
async def custom_docs(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "docs.html",
        {
            "request": request,
            "title": "BTAA Geospatial API — Endpoints",
            "openapi_url": app.openapi_url,
        },
    )


@app.get("/api/docs/oauth2-redirect", include_in_schema=False)
async def swagger_oauth2_redirect() -> HTMLResponse:
    return HTMLResponse(get_swagger_ui_oauth2_redirect_html())


# Optional: serve common static files
@app.get("/robots.txt")
async def robots():
    robots_path = os.path.join(FRONTEND_DIR, "robots.txt")
    if os.path.isfile(robots_path):
        return FileResponse(robots_path)
    return JSONResponse(content={"message": "robots.txt not found"}, status_code=404)


@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(FRONTEND_DIR, "favicon.ico")
    if os.path.isfile(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse(content={"message": "favicon.ico not found"}, status_code=404)


# SPA fallback: any other path → index.html unless a file exists
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """
    SPA history fallback handler.
    Serves static files if they exist, otherwise returns index.html for client-side routing.
    """
    # Skip API routes (they should be handled by the API router above)
    if full_path.startswith("api/"):
        return JSONResponse(content={"message": "API endpoint not found"}, status_code=404)

    # Check if the requested path is a file that exists
    candidate_path = os.path.join(FRONTEND_DIR, full_path)
    if os.path.isfile(candidate_path):
        return FileResponse(candidate_path)

    # For any other path (including root), serve index.html for SPA routing
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    # Fallback if index.html doesn't exist
    return JSONResponse(
        content={"message": "Frontend not found. Please build the React app."}, status_code=404
    )


# Add uvicorn configuration for running the application directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
