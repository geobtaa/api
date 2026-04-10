# Resource relationships

Relationships drive the "Has part" / "Is part of" links on resource detail pages and the "Browse all X records..." search filter.

## Elasticsearch mapping

The field `dct_isPartOf_sm` is defined in the index mapping (text + keyword subfield) so the "Browse all" filter works. If the index was created before this mapping was added, recreate the index and run `make reindex`, or run a full reindex so that documents include `dct_isPartOf_sm` and (if dynamic mapping was used) the keyword subfield is available for filtering.

## Building relationships

- **DB table**: `resource_relationships` (subject_id, predicate, object_id). Populated from the `resources` table columns (e.g. `dct_isPartOf_sm`, `pcdm_memberOf_sm`).
- **OGM harvest behavior**: OpenGeoMetadata harvests now sync `resource_relationships` automatically for the harvested records and any unchanged resources that point at them.
- **Make task** (from project root):
  ```bash
  make populate-relationships
  ```
  Runs `scripts/populate_relationships.py` inside the API container. Use this after bulk imports that do not already sync relationships incrementally, or when relationship-sync code changes and you want a full rebuild.
- **Search filter**: "Browse all X records..." uses:
  - **Has part**: `include_filters[dct_isPartOf_sm][]=<parent_id>` — children must have the parent ID in `resources.dct_isPartOf_sm`.
  - **Collection records**: `include_filters[pcdm_memberOf_sm][]=<collection_id>` — member resources must have the collection ID in `resources.pcdm_memberOf_sm`.
  Filters are applied in Elasticsearch using the indexed fields (with `.keyword` for exact match). So:
  1. Run `make populate-relationships` so the UI relationship lists are correct (from `resource_relationships`).
  2. Run `make reindex` so Elasticsearch has up-to-date `dct_isPartOf_sm` and `pcdm_memberOf_sm` for the search filters.

## Querying the database

Use the ParadeDB (PostgreSQL) container. From the project root, with Docker running:

```bash
docker compose exec paradedb psql -U postgres -d btaa_geospatial_api -c "..."
```

### Check "Has part" rows for a resource (e.g. Wabash parent)

Replace `eee6150b-ce2f-4837-9d17-ce72a0c1c26f` with your resource ID.

**Rows in `resource_relationships` where this resource is the parent (dct:hasPart):**

```sql
SELECT predicate, subject_id AS child_id, object_id AS parent_id, r.dct_title_s AS child_title
FROM resource_relationships rr
JOIN resources r ON r.id = rr.subject_id
WHERE rr.object_id = 'eee6150b-ce2f-4837-9d17-ce72a0c1c26f'
  AND rr.predicate = 'dct:hasPart'
ORDER BY r.dct_title_s;
```

### Check which resources have a given parent in `dct_isPartOf_sm`

These are the documents that should match the "Browse all" search filter.

```sql
SELECT id, dct_title_s, "dct_isPartOf_sm"
FROM resources
WHERE "dct_isPartOf_sm" IS NOT NULL
  AND 'eee6150b-ce2f-4837-9d17-ce72a0c1c26f' = ANY("dct_isPartOf_sm")
ORDER BY dct_title_s;
```

If this returns 0 rows, the DB doesn’t have any children with that parent ID in `dct_isPartOf_sm`; the search filter will correctly return 0 results. If it returns 25 rows but search still returns 0, run `make reindex` so Elasticsearch gets the updated `dct_isPartOf_sm` values.

### Count relationships by type

```sql
SELECT predicate, COUNT(*) FROM resource_relationships GROUP BY predicate ORDER BY predicate;
```
