# Parameter Reference

{% include-markdown "includes/wip.md" %}

| Parameter | Type | Description |
| :---- | :---- | :---- |
| `q` | string | Full‑text query (default `*:*`). |
| `fq` | object | Active facet include filters (same as include_filters) |
| `search_field` | string (CSV) | Search field (all_fields [default], etc.) |
| `page` | integer | Current page of results |
| `per_page` | integer | Number of results to return |
| `sort` | string | Sort option (relevance, year\_desc, year\_asc, title\_asc, title\_desc) |
| `format` | string | Format option (JSON [default], JSONP) |
| `callback` | string | JSONP callback name |
| `fields` | string (CSV) | List of fields to return |
| `facets` | string (CSV) | List of facets to return |
| `include_filters` | object | Active facet include filters (same as fq) |
| `exclude_filters` | object | Active facet exclude filters |
| `meta` | boolean | Include META (default true) |
| `adv_q` | string | JSON array of advanced query clauses. Example: `{'op': 'AND|OR|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}` | 