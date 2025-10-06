# Distribution Tables - Quick Reference

## Quick Start

### Run All Migrations
```bash
python db/migrations/run_distribution_migrations.py
```

### Test Migrations
```bash
python db/migrations/test_distribution_migrations.py
```

## API Endpoint

### Get Resource Distributions
```bash
curl "http://localhost:8000/api/v1/resources/{id}/distributions"
```

**Response:**
```json
{
  "data": {
    "type": "distributions",
    "id": "resource-id",
    "attributes": {
      "distributions": [...],
      "count": 5
    }
  }
}
```

## Common Queries

### Get All Distributions for a Resource
```sql
SELECT rd.url, rd.label, dt.distribution_type
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE rd.resource_id = 'your-resource-id'
ORDER BY rd.position;
```

### Find Resources with Downloads
```sql
SELECT DISTINCT rd.resource_id
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
WHERE dt.name = 'download';
```

### Count by Distribution Type
```sql
SELECT dt.distribution_type, COUNT(*) as count
FROM resource_distributions rd
JOIN distribution_types dt ON rd.distribution_type_id = dt.id
GROUP BY dt.distribution_type
ORDER BY count DESC;
```

## Table Structure

### `distribution_types`
- `id` (PK)
- `name` (unique identifier)
- `distribution_type` (human-readable name)
- `distribution_uri` (standard URI)
- `label` (boolean)
- `note` (description)
- `position` (display order)

### `resource_distributions`
- `id` (PK)
- `resource_id` (FK to resources)
- `distribution_type_id` (FK to distribution_types)
- `url` (distribution URL)
- `label` (optional label)
- `position` (order within resource)
- `created_at`, `updated_at` (timestamps)

## Migration Files

| File | Purpose |
|------|---------|
| `create_distribution_tables.py` | Create tables and indexes |
| `populate_resource_distributions.py` | Migrate data from JSON |
| `rename_friendlier_id_to_resource_id.py` | Rename column for consistency |
| `run_distribution_migrations.py` | Run all migrations |
| `test_distribution_migrations.py` | Verify migration success |

## Key Benefits

✅ **Normalized Structure** - Proper relational design  
✅ **Better Performance** - Indexed queries vs JSON parsing  
✅ **Data Integrity** - Foreign key constraints  
✅ **Queryability** - Standard SQL operations  
✅ **Extensibility** - Easy to add new types  

## Statistics

- **Resources processed**: 74,579
- **Total distributions**: 270,997
- **Distribution types**: 27
- **Success rate**: 100%

For detailed documentation, see [Distribution Tables Documentation](./distribution_tables.md)
