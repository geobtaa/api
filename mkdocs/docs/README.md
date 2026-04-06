# Documentation

This directory contains the MkDocs documentation for the BTAA Geospatial API and linked data repository.

## Structure

- `index.md` - Main documentation page
- `about.md` - Project overview and mission
- `assets/` - Documentation for linked data assets
  - `contexts.md` - JSON-LD contexts documentation
  - `vocabularies.md` - Controlled vocabularies documentation
  - `ontologies.md` - Semantic models documentation
- `api.md` - API reference
- `contributing.md` - Contributing guidelines

## Building Documentation

To build the documentation:

```bash
mkdocs build
```

To serve the documentation locally:

```bash
mkdocs serve -a localhost:8001
```

The documentation will be available at `http://127.0.0.1:8001/`

## Configuration

The documentation is configured in `mkdocs.yml` at the repository root. It uses the Material theme with various extensions for enhanced functionality.

## Dependencies

Documentation dependencies are listed in `requirements-docs.txt`:

- mkdocs
- mkdocs-material
- mkdocs-git-revision-date-localized-plugin
- pymdown-extensions 