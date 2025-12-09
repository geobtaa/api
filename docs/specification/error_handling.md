# Error Handling

{% include-markdown "includes/wip.md" %}

Errors **MUST** return a JSON object with `type`, `title`, `status`, and `detail` properties.

```json
{
  "type": "https://opengeometadata.org/api/errors/RateLimitExceeded",
  "title": "Rate limit exceeded",
  "status": 429,
  "detail": "Allowed 1000 requests per minute; received 1423."
}
```

| HTTP Status | Meaning |
| :---- | :---- |
| 400 | Bad request / parameter validation error |
| 401 | Missing or invalid API key |
| 404 | Record or endpoint not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |