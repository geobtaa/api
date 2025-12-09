# Authentication (API Keys)

{% include-markdown "includes/wip.md" %}

The API uses simple **apiKey** authentication. Clients **MUST** supply a valid key via one of:

HTTPS header (preferred):

*  X-API-Key: \<key\>  
* Query parameter (fallback): `?api_key=<key>`

Keys are provisioned out‑of‑band by the service operator. A new key **MUST** be a 32‑character URL‑safe random string.

## Key Status Endpoint

| Method | Path | Description |
| :---- | :---- | :---- |
| GET | `/keys/self` | Returns metadata about the calling key (plan, quota, issued at, expires at). |

## TODOs

* Add Authentication to API