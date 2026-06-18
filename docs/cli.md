# BTAA Geo API CLI

The BTAA Geo API CLI provides terminal access to the same API contracts used by the frontend, QGIS plugin, MkDocs examples, and external integrations. The console command is:

```bash
btaa-geo-api
```

The package also installs a shorter alias:

```bash
btaa
```

## Development Install

```bash
cd cli
python -m pip install -e ".[dev]"
btaa-geo-api --help
```

## Configuration

The CLI resolves configuration in this order: command flags, environment variables, saved profile, defaults.

Useful environment variables:

```bash
BTAA_GEO_API_BASE_URL=http://localhost:8000/api/v1
BTAA_GEO_API_KEY=your-api-key
BTAA_GEO_API_ANALYTICS=0
BTAA_GEO_API_OUTPUT=json
```

API keys are sent as `X-API-Key` so backend analytics can record traffic by `api_key_id` and tier. Raw API keys are never written to CLI analytics payloads.

## Searching

Simple search:

```bash
btaa-geo-api search "water"
```

JSON output:

```bash
btaa-geo-api search "water" --output json
```

Stream every result page as JSON Lines:

```bash
btaa-geo-api search "water" --all --output jsonl
btaa-geo-api search "water" --stream
```

Print IDs or one dotted field path for shell pipelines:

```bash
btaa-geo-api search "water" --ids-only
btaa-geo-api search "water" --field attributes.ogm.dct_title_s
```

Read search input from stdin:

```bash
printf "water\n" | btaa-geo-api search - --ids-only
cat places.txt | btaa-geo-api search --each --output jsonl
```

Field-directed search:

```bash
btaa-geo-api search "Transportation" --search-field dct_subject_sm
```

Faceted include search:

```bash
btaa-geo-api search "seattle" --include gbl_resourceClass_sm=Maps
```

Faceted include and exclude search:

```bash
btaa-geo-api search "seattle" \
  --include gbl_resourceClass_sm=Maps \
  --include dct_spatial_sm=Washington \
  --exclude schema_provider_s="Pennsylvania State University"
```

Advanced search passes `adv_q` JSON through to the API:

```bash
btaa-geo-api search "" --adv-q '[{"op":"AND","f":"gbl_resourceClass_sm","q":"Maps"},{"op":"AND","f":"dct_title_s","q":"Island"},{"op":"NOT","f":"dct_title_s","q":"antarctica"}]'
```

## Schema And Facets

Discover searchable and facetable fields:

```bash
btaa-geo-api schema fields
btaa-geo-api schema facets
btaa-geo-api schema filters
btaa-geo-api schema search-params
```

Use OGC schema endpoints:

```bash
btaa-geo-api schema queryables
btaa-geo-api schema sortables
```

List facet values:

```bash
btaa-geo-api facets dct_spatial_sm --q "water"
btaa-geo-api facets schema_provider_s --include dct_accessRights_s=Public
```

## Grep-Style Search

`grep` is a Unix-friendly alias for resource discovery. It defaults to JSON Lines so it composes cleanly with `jq`, `xargs`, and other shell tools.

```bash
btaa-geo-api grep "railroad"
btaa-geo-api grep "soil survey" --state Iowa
btaa-geo-api grep "plat map" --ids-only | btaa-geo-api download --ids - --best --out ./data
```

## Resources, Metadata, Citations, And Downloads

```bash
btaa-geo-api get RESOURCE_ID
btaa-geo-api metadata RESOURCE_ID --format ogm
btaa-geo-api cite RESOURCE_ID --format bibtex
btaa-geo-api downloads RESOURCE_ID
btaa-geo-api download RESOURCE_ID --best --out ./data
btaa-geo-api search "plat map" --ids-only | btaa-geo-api download --ids - --best --out ./data
btaa-geo-api thumbnail RESOURCE_ID --out thumbnail.png
btaa-geo-api static-map RESOURCE_ID --out static_map.png
```

## Research Context

Generate compact Markdown or JSON context for notebooks, AI tools, and quick literature/resource scans:

```bash
btaa-geo-api context "Mississippi River maps"
btaa-geo-api context "University Avenue streetcar history" --format json
```

## Aardvark Validation And Crosswalks

Validate an OGM Aardvark JSON record before sharing or ingesting it:

```bash
btaa-geo-api validate record.json --output table
```

Crosswalk ISO 19139 or FGDC XML into Aardvark JSON:

```bash
btaa-geo-api crosswalk iso19139.xml --from iso --validate
btaa-geo-api crosswalk fgdc.xml --from fgdc --validate
```

Inspect the supported crosswalk table:

```bash
btaa-geo-api crosswalks --from iso
btaa-geo-api crosswalks --from fgdc
```

The crosswalks are modeled on GeoCombine's metadata transformation approach:
`isoAardvark.xsl`, `iso2geoBL.xsl`, and `fgdc2geoBL.xsl` map the same core
source families into discovery metadata fields, including title, abstract,
creators, publishers, provider, rights, resource class/type, subjects, places,
issued dates, bounding boxes, and references.

## Open Resource URLs

Print the resource URL, or resolve the first search result for a query:

```bash
btaa-geo-api open RESOURCE_ID
btaa-geo-api open "dakota county parcels"
```

Use `--browser` to launch the URL with the operating system browser.

## OGC API

```bash
btaa-geo-api ogc collections
btaa-geo-api ogc queryables
btaa-geo-api ogc sortables
btaa-geo-api ogc items --q water --bbox -94,44,-92,45
btaa-geo-api ogc item RESOURCE_ID
```

## Analytics

Every request identifies the CLI with `X-BTAA-Client-*` headers. The backend usage log records endpoint traffic, status, response time, API key id, tier id, and client channel. The CLI also sends best-effort command events to `/api/v1/analytics/events`.

Disable command analytics:

```bash
btaa-geo-api --no-analytics search "water"
BTAA_GEO_API_ANALYTICS=0 btaa-geo-api search "water"
btaa-geo-api config set analytics.enabled false
```

## Google Colab Tutorial

A beginner-friendly notebook is available at [`docs/cli_colab_tutorial.ipynb`](cli_colab_tutorial.ipynb). It starts with installation and help output, then builds from simple search to include/exclude faceting, advanced search, metadata, citation, and downloads.

## Man Pages

Man page sources live in `cli/docs/*.1.md`, and generated man artifacts live in `cli/man/`.

```bash
make -C cli man
man cli/man/btaa-geo-api.1
```

## Shell Completion

Typer provides shell completion for bash, zsh, fish, and PowerShell:

```bash
btaa-geo-api --show-completion zsh
btaa-geo-api --install-completion zsh
```

## Testing

Run the CLI suite:

```bash
make cli-test
make -C cli test
```

Other targets:

```bash
make cli-lint
make cli-format
make cli-build
make cli-man
```
