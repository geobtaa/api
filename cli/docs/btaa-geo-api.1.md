# btaa-geo-api(1)

## NAME

btaa-geo-api - command line client for the BTAA Geospatial API

## SYNOPSIS

`btaa-geo-api [GLOBAL OPTIONS] COMMAND [ARGS]`

## DESCRIPTION

`btaa-geo-api` searches, inspects, and downloads records from the BTAA Geospatial API using the same public contracts as the web frontend and QGIS plugin.

## GLOBAL OPTIONS

- `--base-url URL`: API base URL.
- `--api-key KEY`: API key sent as `X-API-Key`.
- `--profile NAME`: config profile.
- `--output FORMAT`: default output format.
- `--no-analytics`: disable command analytics for this run.

## ENVIRONMENT

- `BTAA_GEO_API_BASE_URL`
- `BTAA_GEO_API_KEY`
- `BTAA_GEO_API_ANALYTICS`
- `BTAA_GEO_API_OUTPUT`

## COMMANDS

- `search`
- `schema`
- `facets`
- `get`
- `metadata`
- `cite`
- `downloads`
- `download`
- `ogc`
- `config`

## EXAMPLES

```bash
btaa-geo-api search "water"
btaa-geo-api schema facets
btaa-geo-api get RESOURCE_ID
```

## EXIT STATUS

Returns zero on success. API errors return a non-zero status.

## SEE ALSO

`btaa-geo-api-search(1)`, `btaa-geo-api-schema(1)`, `btaa-geo-api-download(1)`
