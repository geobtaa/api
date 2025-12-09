# Protocol &amp; Versioning

{% include-markdown "includes/wip.md" %}

* API Base URI:  
    * [`https://api.geo.btaa.org/`](https://api.geo.btaa.org/)
* Content types:  
    * `application/json` (default)  
    * `application/ld+json` (when `Accept` header includes JSON‑LD)  
    * `text/csv` (when `Accept` header includes CSV)  
* HTTP 1.1 or HTTP/2 over TLS 1.2+
* Minor revisions to this spec will increment the *patch* version (e.g., `1.0.1`) and **MUST NOT** introduce breaking changes.

## TODOs

* Support HTTP/3
