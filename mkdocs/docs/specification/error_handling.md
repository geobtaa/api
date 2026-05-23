# Error Handling

{% include-markdown "includes/wip.md" %}

Public API errors return a JSON object with an `errors` array. Each error object includes:

```json
{
  "errors": [
    {
      "status": 404,
      "code": "not_found",
      "title": "Not found",
      "detail": "Resource not found",
      "request_id": "01HZY7V9C4V6B2D5W8QZ"
    }
  ]
}
```

| Field | Meaning |
| :---- | :---- |
| `status` | HTTP status code for the error. |
| `code` | Stable machine-readable error code. |
| `title` | Short human-readable category. |
| `detail` | Optional safe detail for client-facing errors. |
| `request_id` | Request correlation ID, also returned in the `X-Request-ID` response header. |

Clients may send an `X-Request-ID` header. If omitted, the API generates one. The same value is returned on normal and error responses.

For 5xx errors, `detail` is intentionally generic. Public responses do not expose raw exception text, Elasticsearch query internals, database connection strings, SQL text, or upstream stack details.

| HTTP Status | Meaning |
| :---- | :---- |
| 400 | Bad request / parameter validation error |
| 401 | Missing or invalid API key |
| 404 | Record or endpoint not found |
| 422 | Request validation error |
| 429 | Rate limit exceeded |
| 502 | Upstream service failed |
| 503 | Service unavailable |
| 500 | Internal server error |
