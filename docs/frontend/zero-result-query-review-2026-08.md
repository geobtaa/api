# Zero-result query review: August 2026

## Scope and status

The August **top-100 audit is complete**. The September 10, 2026 export ranks
all 885 distinct trimmed, non-empty zero-result query strings with no
minimum-frequency cutoff, ordered by count descending then query text using
database collation. Case is preserved. All 100 August rows are categorized below;
the original September 9 top 50 is unchanged.

Source: [complete query aggregate](../../frontend/src/data/analytics/zeroResultQueries2026.json).
See [monthly totals](../../frontend/src/data/analytics/august2026.ts),
[query/blank breakdown](../../frontend/src/data/analytics/reportsAugust2026.ts),
and [report definitions](monthly-analytics.md).

August recorded 7,545 searches and 1,455 zero-result searches (19.3%): 1,148
with query text and 307 without. The top 100 represent **298 events**, or
20.5% of all zero-result searches and 26.0% of those with query text. The remaining
785 query strings represent 850 zero-result events. The cutoff falls within
queries with two events; alphabetical tie ordering affects which appear, so this
is a ranked sample rather than a complete intent distribution.

July was also expanded to 100 rows: 545 distinct query strings and 268 ranked
zero-result events. All original 34 July rows are unchanged. July's totals
reconcile to 6,457 searches, 1,098 zero results, and 758/340 with/without query
text. July provides supplementary examples; the category audit counts only
August, avoiding a combined ranking constructed from truncated monthly lists.

Counts measure recorded searches, not distinct patrons or intent. Repeated
requests, filters, page state, errors, and automation can affect them. Blank-query
failures need a separate filter/extent investigation. Category assignments below
are manual intent hypotheses, not verified causes of historical failure.

## Category summary

Each row receives exactly one primary category; interpretation notes preserve
secondary intent and uncertainty. Shares describe the 298 reviewed August events.

| Order | Category | Query rows | Zero-result searches | Share of reviewed events | Issue |
| --- | --- | ---: | ---: | ---: | --- |
| 01 | Address and street search | 38 | 97 | 32.6% | [#397](https://github.com/geobtaa/api/issues/397) |
| 02 | Named places and postal geography | 22 | 65 | 21.8% | [#399](https://github.com/geobtaa/api/issues/399) |
| 03 | Coordinates and Plus Codes | 12 | 44 | 14.8% | [#398](https://github.com/geobtaa/api/issues/398) |
| 04 | Subject or map series plus place/date | 6 | 23 | 7.7% | [#401](https://github.com/geobtaa/api/issues/401) |
| 05 | Known map, title, citation, or creator | 7 | 20 | 6.7% | [#403](https://github.com/geobtaa/api/issues/403) |
| 06 | Township/range/section and land descriptions | 4 | 13 | 4.4% | [#400](https://github.com/geobtaa/api/issues/400) |
| 07 | Ambiguous mixed query | 3 | 13 | 4.4% | [#406](https://github.com/geobtaa/api/issues/406) |
| 08 | Opaque identifiers or diagnostic-looking text | 4 | 11 | 3.7% | [#404](https://github.com/geobtaa/api/issues/404) |
| 09 | Subject-only search | 2 | 7 | 2.3% | [#402](https://github.com/geobtaa/api/issues/402) |
| 10 | Conversational or person-information request | 1 | 3 | 1.0% | [#405](https://github.com/geobtaa/api/issues/405) |
| 11 | Date-only search | 1 | 2 | 0.7% | [#407](https://github.com/geobtaa/api/issues/407) |

Tracking issue: [#396](https://github.com/geobtaa/api/issues/396).

## Recovery design and sequencing

The table above is the recommended category work order: start with addresses,
then named places, then coordinates. Build the shared recovery controls in
[#396](https://github.com/geobtaa/api/issues/396) alongside the address issue;
closing the umbrella issue is not a prerequisite. Rank primarily by observed
frequency, use dependencies and interpretation confidence to break ties, and
reassess after measuring recovery. The first three geographic categories together
cover 206 of 298 reviewed events (69.1%).
Show “We found this location” only after reliable resolution or patron selection;
the pin describes their search location, not a catalog result. Keep the chosen
location visible even when catalog results are zero. Present a text equivalent
and allow correction or disambiguation.

Offer “Search a wider area” using progressively larger extents, with bounded
preview requests and actual counts. Keep the point and original extent visible.
Use spatial intersection for coverage, but explain that an intersecting regional
map is not necessarily a detailed map of the address. Do not promise nearby
items before querying. If no extent produces useful matches, offer broader
collection browsing or help. Preserve subject and other filters unless a
suggestion explicitly explains their removal. Reset pagination on a new search.

Then address structured land descriptions, subject/place/date queries, and known
items. Identifier-like, conversational, and ambiguous queries need clarification
paths; the most frequent August string is still ambiguous despite its rank.
Spelling, alternate names, and multilingual handling cut across categories.
July supplies supplementary examples such as `ایران قم سال  میلادی1963`,
`татарка`, and signed coordinates with hemisphere letters; these are not included
in August counts. Preserve Unicode and avoid silently changing meanings.

Current behavior already offers keyword and geographic suggestions, but
`NoResultsSearchHelp.tsx` discards current constraints in suggestion URLs and
renders failed suggestion requests like empty successful responses. The search
page test explicitly expects the location map to disappear at zero results.
The search event also uses an empty page result array for its zero-results flag;
verify empty pagination and API failures separately from true zero total matches
before using future metrics to judge improvement. These observations identify
implementation work, not proven explanations for the historical query counts.

Measure eligible recovery impressions, suggestion selection rate, next-search
nonzero rate, and subsequent record engagement. Separate errors, abandonment,
query category, and blank-query/filter-only cases. Previews must not count as
patron searches. Set numeric improvement targets after validating this baseline.
Coordinate with existing issues [#270](https://github.com/geobtaa/api/issues/270)
and [#231](https://github.com/geobtaa/api/issues/231).

## Export validation and maintenance

The reusable [exporter](../../backend/scripts/export_zero_result_queries_2026.py)
reads both months in one consistent read-only transaction and refuses changed or
incomplete monthly totals. The September 10 export reconciled search, zero-result,
and blank/non-blank counts for both months and preserved both original ranking
prefixes. No raw request records or visitor identifiers are exported.

All 100 August rows are assigned once; category row counts total 100 and event
counts total 298. Future refreshes must rerun those checks, preserve actual rank
ordering, and update issue evidence together with the report. Supporting
constraint/client aggregates can test failure hypotheses separately. Restricted
database access procedures must remain outside this public document.

## Published query inventory

Rank is the source export order. Exact query strings and counts were reviewed
from the authorized September 10 aggregate; no visitor identifiers are included.

| Rank | Query | Zero-result searches | Primary category | Interpretation note |
| --- | --- | ---: | --- | --- |
| 1 | indiana field survey iran hardin i 38l | 9 | Ambiguous mixed query | Low confidence; possible map-series/sheet reference mixed with places. |
| 2 | 32.503232, 44.449000 | 8 | Coordinates and Plus Codes | Intent inferred from query text. |
| 3 | Iowa City Sanborn, 1883 | 8 | Subject or map series plus place/date | Intent inferred from query text. |
| 4 | 31.971794,48.809872 | 7 | Coordinates and Plus Codes | Intent inferred from query text. |
| 5 | 9266 town line rd Larsen wi | 7 | Address and street search | Intent inferred from query text. |
| 6 | 32.654583, 44.405139 | 6 | Coordinates and Plus Codes | Intent inferred from query text. |
| 7 | maple range township mi | 6 | Named places and postal geography | Intent inferred from query text. |
| 8 | 205 E Sycamore Street Westport, Indiana | 5 | Address and street search | Intent inferred from query text. |
| 9 | 3115 hickman rd des moines | 5 | Address and street search | Intent inferred from query text. |
| 10 | Map of the settled part of Wisconsin and Iowa | 5 | Known map, title, citation, or creator | Intent inferred from query text. |
| 11 | 15N 9E | 4 | Township/range/section and land descriptions | Missing survey context. |
| 12 | 3901 S Green Bay Rd, Mount Pleasant, WI | 4 | Address and street search | Intent inferred from query text. |
| 13 | Calmimilolco | 4 | Named places and postal geography | Unverified place spelling. |
| 14 | chukar ln Burbank wa | 4 | Address and street search | Intent inferred from query text. |
| 15 | Edmondson arkansas | 4 | Named places and postal geography | Intent inferred from query text. |
| 16 | fiji contours | 4 | Subject or map series plus place/date | Intent inferred from query text. |
| 17 | Lost lake saint germain | 4 | Named places and postal geography | Intent inferred from query text. |
| 18 | redlining | 4 | Subject-only search | Intent inferred from query text. |
| 19 | 101N068 | 3 | Opaque identifiers or diagnostic-looking text | Unresolved code; possibly cadastral. |
| 20 | 10560 E Richview Rd Mount Vernon IL | 3 | Address and street search | Intent inferred from query text. |
| 21 | 1122 prospect Toledo, Ohio | 3 | Address and street search | Intent inferred from query text. |
| 22 | 14.375000 46.745833 | 3 | Coordinates and Plus Codes | Intent inferred from query text. |
| 23 | 2005 bergan st south bend | 3 | Address and street search | Intent inferred from query text. |
| 24 | 2670232 | 3 | Opaque identifiers or diagnostic-looking text | Unresolved numeric identifier; compare rank 70 without assuming same patron. |
| 25 | 27.014435, 1.072616 | 3 | Coordinates and Plus Codes | Intent inferred from query text. |
| 26 | 34.73859, 36.55421 | 3 | Coordinates and Plus Codes | Intent inferred from query text. |
| 27 | 36°42'44.4"N 46°52'25.1"E | 3 | Coordinates and Plus Codes | Intent inferred from query text. |
| 28 | 7662 walnut dr | 3 | Address and street search | Incomplete address; locality needed. |
| 29 | 8219 City Centre Dr, La Vista, NE 68128 | 3 | Address and street search | Intent inferred from query text. |
| 30 | 8C37+H7، اليمن | 3 | Coordinates and Plus Codes | Short Plus Code with Arabic locality; separate decoding path. |
| 31 | calgary | 3 | Named places and postal geography | Intent inferred from query text. |
| 32 | can u glide me information on theodore ruanda haritonovici | 3 | Conversational or person-information request | Conversational request about a person; intent not established. |
| 33 | crime | 3 | Subject-only search | Intent inferred from query text. |
| 34 | Greenview IL | 3 | Named places and postal geography | Intent inferred from query text. |
| 35 | Mandi shah jewana | 3 | Named places and postal geography | Intent inferred from query text. |
| 36 | map of jessenland township township 113 n, range 2 | 3 | Township/range/section and land descriptions | Mixed map/place and land-description intent. |
| 37 | Meeker MN | 3 | Named places and postal geography | County/locality ambiguous. |
| 38 | missing_bbox | 3 | Opaque identifiers or diagnostic-looking text | Looks diagnostic; attribution unverified. |
| 39 | Morgan Mn | 3 | Named places and postal geography | Intent inferred from query text. |
| 40 | N9009 Lakeshore dr van dyne wi 54979 | 3 | Address and street search | Intent inferred from query text. |
| 41 | Park County, Indiana soil productivity map | 3 | Subject or map series plus place/date | Topic/place; verify place spelling. |
| 42 | Plat Book of Sibley County Minnesota | 3 | Known map, title, citation, or creator | Intent inferred from query text. |
| 43 | RANCHO SON VICENTEE AND SANTA MONICA T1S R11W SEC 2 | 3 | Township/range/section and land descriptions | Mixed named place and survey description. |
| 44 | Reserve township, mn | 3 | Named places and postal geography | Intent inferred from query text. |
| 45 | Sanborn Maps Goose Island, Chicago | 3 | Subject or map series plus place/date | Intent inferred from query text. |
| 46 | SouthWest Indiana 46614 | 3 | Named places and postal geography | Regional phrase and postal code may conflict. |
| 47 | spring mills, pa | 3 | Named places and postal geography | Intent inferred from query text. |
| 48 | spring mills, potter township, pa | 3 | Named places and postal geography | Intent inferred from query text. |
| 49 | T1S R11W SEC 2 | 3 | Township/range/section and land descriptions | Intent inferred from query text. |
| 50 | U.S. Army Map Service. (2016). U.S. Army Map Series K501: Iraq and Iran: Zenjan J-39S. U.S. Army Map Service. https://isac-idb.uchicago.edu/id/94ecf195-fa5f-4120-9504-23e9550234cb | 3 | Known map, title, citation, or creator | Full citation with source URL; potential known-item intent. |
| 51 | village boundary andra pradesh | 3 | Subject or map series plus place/date | Boundary data plus place; unverified place spelling. |
| 52 | Warner, Higgins & Beers | 3 | Known map, title, citation, or creator | Likely creator/publisher lookup; verify catalog context. |
| 53 | Williamsburg to White House | 3 | Named places and postal geography | Possible route/corridor or named-item intent; locations ambiguous. |
| 54 | Yemen shabwa | 3 | Named places and postal geography | Intent inferred from query text. |
| 55 | 1415 primrose lane Lancaster wi | 2 | Address and street search | Intent inferred from query text. |
| 56 | 15168 franchesca ln | 2 | Address and street search | Intent inferred from query text. |
| 57 | 160 east kellog blvd | 2 | Address and street search | Address with spelling variant; compare rank 58. |
| 58 | 160 east kellogg blvd | 2 | Address and street search | Intent inferred from query text. |
| 59 | 160 ferne ridge lane | 2 | Address and street search | Intent inferred from query text. |
| 60 | 175 rockwood ln | 2 | Address and street search | Intent inferred from query text. |
| 61 | 1903 w 3rd st davenport, ia | 2 | Address and street search | Intent inferred from query text. |
| 62 | 1913 New Sweden Township plat map | 2 | Subject or map series plus place/date | Map type, township, and year. |
| 63 | 19th St and Benning | 2 | Address and street search | Street intersection; locality needed. |
| 64 | 2016 haven ave ocean city nj | 2 | Address and street search | Intent inferred from query text. |
| 65 | 204 high street jeffersonville indiana | 2 | Address and street search | Intent inferred from query text. |
| 66 | 2189 mercer road | 2 | Address and street search | Intent inferred from query text. |
| 67 | 2189 mercer road, stoneboro, pa | 2 | Address and street search | Intent inferred from query text. |
| 68 | 2375 Harrisburg Pike Grove City, Ohio Utilities | 2 | Address and street search | Address plus utilities subject; retain subject when resolving location. |
| 69 | 23w545 james way | 2 | Address and street search | Intent inferred from query text. |
| 70 | 2670232 -79.6270572 | 2 | Coordinates and Plus Codes | Malformed coordinate-like pair; first value outside latitude/longitude range. Ask for correction. |
| 71 | 311 S Pleasant St Cambridge Wi | 2 | Address and street search | Intent inferred from query text. |
| 72 | 351 northwestern | 2 | Address and street search | Intent inferred from query text. |
| 73 | 35.2065341, 47.1094729 | 2 | Coordinates and Plus Codes | Intent inferred from query text. |
| 74 | 37-02-2711N | 2 | Opaque identifiers or diagnostic-looking text | Opaque code or partial coordinate; no reliable interpretation. |
| 75 | 39.758333, -76.268056 | 2 | Coordinates and Plus Codes | Intent inferred from query text. |
| 76 | 41.57864,-92.25404 | 2 | Coordinates and Plus Codes | Intent inferred from query text. |
| 77 | 46240 | 2 | Named places and postal geography | Possible postal code; country/context unverified. |
| 78 | 46628 | 2 | Named places and postal geography | Possible postal code; country/context unverified. |
| 79 | 47733 cross manor road st. inigoes md | 2 | Address and street search | Intent inferred from query text. |
| 80 | 575 chukar ln | 2 | Address and street search | Intent inferred from query text. |
| 81 | 575 chukar ln Burbank wa | 2 | Address and street search | Intent inferred from query text. |
| 82 | 641 S Midland Ave, Rockdale, IL 60436, USA | 2 | Address and street search | Intent inferred from query text. |
| 83 | 734 Highcliff Trl, Madison, WI, 53718-3227 | 2 | Address and street search | Intent inferred from query text. |
| 84 | 734 highcliff trl madison wi 5738 3257 | 2 | Address and street search | Address with potentially malformed postal text; compare rank 83. |
| 85 | 824 pine st santa cruz | 2 | Address and street search | Intent inferred from query text. |
| 86 | 90277 | 2 | Named places and postal geography | Possible postal code; country/context unverified. |
| 87 | 9726 s. avers, evergreen park | 2 | Address and street search | Intent inferred from query text. |
| 88 | albany st, springfield, ma | 2 | Address and street search | Intent inferred from query text. |
| 89 | atkin | 2 | Ambiguous mixed query | Could be name, place, or spelling variant; low confidence. |
| 90 | August 13, 2026 | 2 | Date-only search | Temporal intent uncertain: coverage, publication, or event date. |
| 91 | Baltic Provinces | 2 | Named places and postal geography | Historical regional name. |
| 92 | Bartz Farihaven Mn | 2 | Ambiguous mixed query | Possible name plus misspelled locality; low confidence. |
| 93 | bethlehem | 2 | Named places and postal geography | Intent inferred from query text. |
| 94 | Bird's eye view of Iowa City | 2 | Known map, title, citation, or creator | Likely map-title search. |
| 95 | black forest and rhine | 2 | Named places and postal geography | Multiple places/region; preserve both. |
| 96 | braun road | 2 | Address and street search | Intent inferred from query text. |
| 97 | Brother Avenue Kingston Pennsylvania | 2 | Address and street search | Intent inferred from query text. |
| 98 | Calgary | 2 | Named places and postal geography | Case variant of rank 31; counts remain separate. |
| 99 | Carta geologica delle | 2 | Known map, title, citation, or creator | Partial non-English map title; preserve language. |
| 100 | Carta geologica delle Tre Venezie, Legnago | 2 | Known map, title, citation, or creator | Non-English map title and place. |
