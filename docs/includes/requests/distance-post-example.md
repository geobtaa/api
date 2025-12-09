```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "distance",
      "field": "dcat_centroid",
      "center":   { "lat": 44.98, "lon": -93.27 },
      "distance": "25km"
    }
  },
  "limit": 50
}
```

