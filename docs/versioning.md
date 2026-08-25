# Release Versioning

The authoritative application release metadata lives in
`backend/app/_release/release.json`. Update that one file when preparing a new
application release.

The metadata drives:

- Python package metadata in `backend/pyproject.toml`;
- the FastAPI/OpenAPI version and API root response;
- MCP service metadata;
- the production frontend build's client-version value; and
- the current version, date, and summary in the public MkDocs specification.

`backend/uv.lock` is generated output and no longer stores a separate project
version. Do not add or edit a package version there by hand. The local Docker
Compose image uses a stable `local` tag, while deployed images are tagged by the
deployment workflow rather than the application release number.
