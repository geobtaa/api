# Cloudflare Turnstile

The geoportal can use Cloudflare Turnstile as an application-layer browser gate.
This does not require Cloudflare WAF or proxying the site through Cloudflare.

## Flow

1. The React app renders a Turnstile widget when `VITE_TURNSTILE_SITE_KEY` is set
   and `VITE_TURNSTILE_ENABLED` is not `false`.
2. The browser posts the widget token to `POST /api/v1/turnstile/verify`.
3. FastAPI validates the single-use token with Cloudflare Siteverify.
4. On success, FastAPI creates an opaque Redis-backed browser session, returns
   the session token for frontend fetches, and sets an HttpOnly cookie for
   same-origin production traffic.
5. `TurnstileMiddleware` requires that verified session on configured hot paths.

By default the protected backend paths are:

- `/api/v1/search`
- `/api/v1/suggest`
- `/api/v1/map/h3`

API-key requests bypass the Turnstile middleware unless they are explicitly
marked as frontend gate traffic. The single-host nginx `/search/results` BFF
route and the React Router `/search/results` loader both add that marker, so
frontend search traffic is still protected even though it uses the server-side
API key.

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

For Kamal, put the public site key and enable flags in the destination secrets or
deploy environment, and add `TURNSTILE_SECRET_KEY` to the destination secret
file. The site key is public and baked into the Vite bundle; the secret key must
only be present in backend runtime secrets.

## Local Development

Turnstile is off by default. To test locally, use Cloudflare's Turnstile test
keys or a local widget configured for `localhost`, then set:

```bash
TURNSTILE_ENABLED=true
TURNSTILE_COOKIE_SECURE=false
TURNSTILE_ALLOWED_HOSTNAMES=localhost,127.0.0.1
VITE_TURNSTILE_ENABLED=true
```

The frontend stores the returned session token in `sessionStorage` so local
cross-origin dev traffic from `localhost:3000` to `localhost:8000` can carry
`X-Turnstile-Session` without relying on cross-origin cookies. Production
same-origin traffic also receives an HttpOnly cookie.
