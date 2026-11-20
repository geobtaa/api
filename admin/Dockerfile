# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS frontend-builder
ARG NPM_VERSION=12.0.2
WORKDIR /build/frontend
RUN npm install --global "npm@${NPM_VERSION}"
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_ADMIN_BASE=/
RUN VITE_ADMIN_BASE="$VITE_ADMIN_BASE" npm run build

FROM python:3.14.7-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app/backend
RUN pip install --no-cache-dir uv==0.12.6
COPY backend/pyproject.toml backend/uv.lock ./

FROM python-base AS development
RUN uv sync --frozen --extra dev --no-install-project
COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python-base AS production
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist
ENV APP_ENV=production \
    FRONTEND_DIST=/app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
