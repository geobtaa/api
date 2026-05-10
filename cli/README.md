# BTAA Geo API CLI

`btaa-geo-api` is a command line client for the BTAA Geospatial API.

## Install For Development

```bash
cd cli
python -m pip install -e ".[dev]"
```

## Quick Start

```bash
btaa-geo-api search "water"
btaa-geo-api search "seattle" --include gbl_resourceClass_sm=Maps
btaa-geo-api search "seattle" --include dct_spatial_sm=Washington --exclude schema_provider_s="Pennsylvania State University"
btaa-geo-api schema facets
btaa-geo-api schema queryables
btaa-geo-api get b1g_example --output json
```

## Configuration

The CLI reads configuration from flags, environment variables, and its user config file.

```bash
BTAA_GEO_API_BASE_URL=https://lib-btaageoapi-dev-app-01.oit.umn.edu/api/v1
BTAA_GEO_API_KEY=your-key
BTAA_GEO_API_ANALYTICS=0
```

Use `--no-analytics` for a single command.

## Testing

```bash
make test
make lint
```
