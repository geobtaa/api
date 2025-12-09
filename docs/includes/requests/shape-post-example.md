```json
{
  "q": "land cover",
  "filters": {
    "geo": {
      "type": "shape",
      "field": "locn_geometry",
      "relation": "within",
      "shape": {
        "type": "envelope",
        "coordinates": [[-94, 46], [-92, 44]]
      }
    }
  }
}
```

