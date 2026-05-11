# BTAA Geo API CLI

`btaa-geo-api` is a command line client for the BTAA Geospatial API. The package
also installs the shorter `btaa` alias.

## Install For Development

```bash
cd cli
python -m pip install -e ".[dev]"
```

## Quick Start

```bash
btaa-geo-api search "water"
btaa-geo-api search "water" --ids-only
btaa-geo-api search "water" --all --output jsonl
cat places.txt | btaa-geo-api search --each --output jsonl
btaa-geo-api search "seattle" --include gbl_resourceClass_sm=Maps
btaa-geo-api search "seattle" --include dct_spatial_sm=Washington --exclude schema_provider_s="Pennsylvania State University"
btaa-geo-api grep "soil survey" --state Iowa
btaa-geo-api context "Mississippi River maps"
btaa-geo-api validate record.json
btaa-geo-api crosswalk metadata.xml --from iso --validate
btaa-geo-api crosswalk metadata.xml --from fgdc --validate
btaa-geo-api crosswalks --output table
btaa-geo-api schema facets
btaa-geo-api schema queryables
btaa-geo-api get b1g_example --output json
btaa-geo-api thumbnail b1g_example --out thumbnail.png
btaa-geo-api static-map b1g_example --out map.png
```

## Unix-Style Pipelines

The CLI is designed to keep stdout machine-readable and progress/status messages on stderr.

```bash
btaa-geo-api search railroads --ids-only
btaa-geo-api search railroads --field attributes.ogm.dct_title_s
btaa-geo-api search railroads --all --output jsonl | jq '.id'
cat places.txt | btaa-geo-api search --each --output jsonl
btaa-geo-api search "plat map" --ids-only | btaa-geo-api download --ids - --best --out ./data
```

Use `-` as the search query to read one query from stdin:

```bash
printf "water\n" | btaa-geo-api search - --ids-only
```

## Convenience Commands

```bash
btaa-geo-api grep "flood insurance" --state Iowa --output jsonl
btaa-geo-api context "University Avenue streetcar history" --format markdown
btaa-geo-api open b1g_example
btaa-geo-api open "dakota county parcels"
```

## Aardvark Validation And Crosswalks

Validate an existing OGM Aardvark JSON record:

```bash
btaa-geo-api validate record.json --output table
```

Crosswalk ISO 19139 or FGDC XML into Aardvark JSON. The mapping follows the same
field families used by GeoCombine's ISO/FGDC XSL transforms.

```bash
btaa-geo-api crosswalk iso19139.xml --from iso --validate
btaa-geo-api crosswalk fgdc.xml --from fgdc --validate
btaa-geo-api crosswalks --from iso
btaa-geo-api crosswalks --from fgdc
```

## Shell Completion

Typer provides shell completion for the CLI:

```bash
btaa-geo-api --show-completion zsh
btaa-geo-api --install-completion zsh
```

## Configuration

The CLI reads configuration from flags, environment variables, and its user config file.

```bash
BTAA_GEO_API_BASE_URL=https://lib-geoportal-prd-web-01.oit.umn.edu/api/v1
BTAA_GEO_API_KEY=your-key
BTAA_GEO_API_ANALYTICS=0
```

Use `--no-analytics` for a single command.

## Testing

```bash
make test
make lint
```
