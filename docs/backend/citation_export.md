# Citation Export (JSON-LD, RIS, BibTeX)

The Geoportal exposes high-quality bibliographic metadata for each resource in formats suitable for citation managers (Zotero, EndNote, Mendeley) and search engines (Google Dataset Search).

## API Endpoints

| Endpoint | Format | Content-Type | Use |
|----------|--------|--------------|-----|
| `GET /api/v1/resources/{id}/citation` | JSON | application/json | All citation styles (generic, APA, MLA, Chicago) |
| `GET /api/v1/resources/{id}/citation/json-ld` | JSON-LD | application/ld+json | Schema.org (Dataset/Map/CreativeWork) |
| `GET /api/v1/resources/{id}/citation/ris` | RIS | application/x-research-info-systems | Zotero, EndNote, Mendeley |
| `GET /api/v1/resources/{id}/citation/bibtex` | BibTeX | application/x-bibtex | LaTeX, Zotero |

## JSON-LD (Schema.org)

The JSON-LD endpoint returns Schema.org structured data suitable for:
- **Google Dataset Search** – improves discoverability of geospatial datasets
- **Future Zotero support** – when native JSON-LD import is added
- **Semantic web** – machine-readable metadata for aggregation and linking

Resource types are mapped to Schema.org:
- Datasets / Web services → `Dataset`
- Maps / Imagery → `Map`
- Other → `CreativeWork`

The JSON-LD is also embedded in the `<head>` of each resource page via a `<script type="application/ld+json">` tag for crawlers and tools that parse page HTML.

## RIS Format

RIS (Research Information Systems) is widely supported by:
- Zotero (import)
- EndNote
- Mendeley
- RefWorks

RIS type codes:
- Datasets / Web services → `TY  - DATA`
- Maps / Imagery → `TY  - MAP`
- Other → `TY  - GEN`

## BibTeX

BibTeX format is used by LaTeX and imported by Zotero. Resources are exported as `@misc` with full metadata.

## Configuration

- **GEOPORTAL_BASE_URL** – Base URL for resource pages (e.g. `https://geoportal.btaa.org`). Used when building canonical URLs in citations. If unset, derived from `APPLICATION_URL` by stripping `/api/v1`.

## Citation Styles

The citation endpoint and resource meta return four formal styles:

| Style | Use |
|-------|-----|
| **Generic** | Default format for general use |
| **APA 7th** | American Psychological Association (datasets, maps) |
| **MLA 9th** | Modern Language Association |
| **Chicago** | Chicago author-date style |

Datasets and web services use the `[Data set]` descriptor in APA; maps use `[Map]`.

## Frontend

The **Cite & Reference** section on each resource page includes:
- Style selector: Generic, APA 7th, MLA 9th, Chicago
- Copy citation (formatted text for selected style)
- Copy permalink
- Export links: RIS, BibTeX, JSON-LD
