# Rate Limiting Recommendations

{% include-markdown "includes/wip.md" %}

Servers **MUST** protect shared resources. The following sane defaults are **RECOMMENDED** and **MAY** be adjusted per deployment:

* **Burst:** 100 requests in any 10‑second window  
* **Sustained:** 1, 000 requests per minute  
* **Daily Cap:** 100,000 requests per 24 hours

Implementations on very small servers **MAY** reduce the burst limit to 50 requests per 10‑second window and the sustained limit to 500 requests per minute if monitoring indicates strain.

The server **SHOULD** convey limits using \[RFC 6585\] `429 Too Many Requests` and the headers:

RateLimit-Limit: 1000  
RateLimit-Remaining: 253  
RateLimit-Reset: 42

## TODOs

* Implement Rate Limiting in API