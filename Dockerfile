FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libcairo2-dev \
    gdal-bin \
    libgdal-dev \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL version
ENV GDAL_VERSION=3.4.1

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ls -l /root/.local/bin/uv && \
    /root/.local/bin/uv --version

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy backend pyproject.toml and uv.lock first to leverage Docker cache
COPY backend/pyproject.toml backend/uv.lock ./

## Frontend assets are served by the dedicated `frontend` / `frontend-dev` containers.
## The API container no longer bundles or serves frontend static files.

# Ensure operational scripts are present in the runtime image (for kamal exec)
COPY backend/scripts ./scripts

# Copy the backend application
COPY backend/ ./backend/

# Give uv more time to download large wheels (like pyproj)
ENV UV_HTTP_TIMEOUT=300

# Optional: slightly reduce concurrency if your connection is bursty
# ENV UV_CONCURRENT_DOWNLOADS=4

# Install Python dependencies (from backend directory)
RUN uv pip install -e ./backend --system

# Create logs and static maps directories
RUN mkdir -p logs static/maps

# Expose port
EXPOSE 8000

# Command to run the application (monorepo: app is installed as top-level package)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 