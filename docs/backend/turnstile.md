# Cloudflare Turnstile

The BTAA Geoportal can use Cloudflare Turnstile as an application-layer browser
gate. This does not require Cloudflare WAF or proxying the site through
Cloudflare.

## Flow

1. The React app renders a Turnstile widget when `VITE_TURNSTILE_SITE_KEY` is set,
   `VITE_TURNSTILE_ENABLED` is not `false`, and the frontend is not running in
   local dev/test mode.
2. The browser posts the widget token to `POST /api/v1/turnstile/verify`.
3. FastAPI validates the single-use token with Cloudflare Siteverify.
4. On success, FastAPI creates an opaque Redis-backed browser session, returns
   the session token for frontend fetches, and sets an HttpOnly cookie for
   same-origin production traffic.
5. `TurnstileMiddleware` requires that verified session only when a request to
   a configured hot path is explicitly marked as frontend browser gate traffic.
6. If a browser tab stays open after that session expires, protected frontend
   requests return `403` with `X-Turnstile-Required: true`; the React API client
   clears its stale session token and reopens the global Turnstile gate in place.

By default the protected backend paths are:

- `/api/v1/search`
- `/api/v1/suggest`
- `/api/v1/map/h3`

Anonymous direct API requests bypass the Turnstile middleware. This includes
normal browser-origin requests to public API endpoints, such as examples running
from the MkDocs site. Turnstile is not an API authentication layer and must not
interfere with public direct API access.

Friendly crawler and monitoring user agents also bypass Turnstile, even when
they hit a frontend-gated hot path. This keeps search indexing and external
monitoring from depending on an interactive browser challenge. The built-in
allowlist includes `Googlebot`, `Googlebot-Image`, `Googlebot-Video`, `Bingbot`,
`Slurp`, `DuckDuckBot`, `Baiduspider`, `YandexBot`, `facebookexternalhit`,
`Twitterbot`, `LinkedInBot`, `Applebot`, and approved monitoring bots.

The single-host nginx `/search/results` BFF route and the React Router
`/search/results` loader add a frontend gate marker for normal browser traffic,
so frontend search traffic is still protected. When a caller supplies its own
`X-API-Key`, the BFF path treats the request as API-client traffic instead: it
forwards that key and does not add the frontend gate marker. This keeps k6 and
other keyed clients testable without opening the browser path to anonymous
traffic.

## Configuration

Backend runtime env:

```bash
TURNSTILE_ENABLED=true
TURNSTILE_SECRET_KEY=<cloudflare-secret-key>
TURNSTILE_ALLOWED_HOSTNAMES=geo.example.edu
TURNSTILE_EXPECTED_ACTION=geoportal_gate
TURNSTILE_PROTECTED_PATHS=/api/v1/search,/api/v1/suggest,/api/v1/map/h3
TURNSTILE_SESSION_TTL_SECONDS=3600
TURNSTILE_COOKIE_SECURE=true
```

Frontend build env:

```bash
VITE_TURNSTILE_ENABLED=true
VITE_TURNSTILE_SITE_KEY=<cloudflare-site-key>
VITE_TURNSTILE_ACTION=geoportal_gate
```

Deployed Turnstile key placement, secret handling, and environment-specific
enablement are restricted operations material. The site key is public and baked
into the Vite bundle; the secret key must only be present in backend runtime
configuration.

## Local Development

Turnstile is off by default. Vite dev/test builds also bypass the browser gate
even if production-like Turnstile values leak into the local environment. To
test Turnstile locally, use Cloudflare's Turnstile test keys or a local widget
configured for `localhost`, then opt back in:

```bash
TURNSTILE_ENABLED=true
TURNSTILE_ENABLE_LOCAL=true
TURNSTILE_COOKIE_SECURE=false
TURNSTILE_ALLOWED_HOSTNAMES=localhost,127.0.0.1
VITE_TURNSTILE_ENABLED=true
VITE_TURNSTILE_ENABLE_LOCAL=true
```

When local Turnstile is not opted in, FastAPI bypasses the browser gate for
local `localhost`, `127.0.0.1`, `::1`, and `0.0.0.0` requests when the app is
not running in a deployed context. The React Router `/search/results`
proxy also strips frontend gate markers before calling FastAPI so local search
traffic can still use the server-side API key without receiving
`turnstile_required`.

The frontend stores the returned session token in `sessionStorage` so local
cross-origin Docker traffic from `localhost:5173` to `localhost:8000` can carry
`X-Turnstile-Session` without relying on cross-origin cookies. Production
same-origin traffic also receives an HttpOnly cookie.

To review the branded gate shell without Cloudflare keys or backend Turnstile
verification, run the Vite dev server and open:

```text
http://localhost:5173/turnstile-preview
```

This route only works in Vite dev mode. It renders the same BTAA Geoportal gate
layout with a mock local verification control, then sends the browser back to
the homepage.


## Verification failures and recovery

Siteverify requests send a UUID `idempotency_key`. A validation attempt retries
transport errors, HTTP 5xx responses, and Cloudflare `internal-error` responses
at most twice, reusing the same UUID and token. Definitive rejections (including
expired or duplicate tokens), action mismatches, and hostname mismatches do not
retry. Tokens longer than Cloudflare's 2048-character maximum are rejected
locally, and malformed upstream responses fail closed.

The browser bounds its status/verification requests to 15 seconds. A failed
request stops the challenge and displays an explicit retry button, rather than
resetting the widget indefinitely. Rate-limited requests respect the supplied
retry delay; service outages have a short cooldown. Retrying checks for an
existing session first, because a response may have been lost after the session
cookie was established. Server error codes remain available on the client error
object without exposing raw provider responses in the page. Failure to load the
Cloudflare script itself still requires a page reload.

Focused local regression checks:

```bash
cd backend
BTAA_SKIP_TEST_DB=1 REDIS_HOST=127.0.0.1 REDIS_PORT=1 python -m pytest --noconftest tests/services/test_turnstile_service.py tests/api/v1/test_turnstile_endpoints.py tests/middleware/test_turnstile_middleware.py -q
cd ../frontend
npm test -- --run src/__tests__/services/turnstile.test.ts src/__tests__/components/security/TurnstileGate.test.tsx
```

These focused tests use fake upstream responses and do not require Cloudflare
credentials or live databases. Session-store outages, shared anonymous rate
limits, and stale requests remain separate from Cloudflare token validation;
a successful widget challenge alone does not guarantee session establishment.
