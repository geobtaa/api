```bash
curl -s -X POST '/api/v1/search' \
  -H 'Content-Type: application/json' \
  -d '{
    "q": "land cover",
    "per_page": 10,
    "include_filters": {
      "geo": {
        "type": "distance",
        "field": "dcat_centroid",
        "center": {"lat": 44.98, "lon": -93.27},
        "distance": "25km"
      }
    }
  }'
```

