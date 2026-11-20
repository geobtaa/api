"""Protected loopback API client for reviewed local administration scripts."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PREFIX = "/api/v1/admin"


class ApiError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Api:
    def __init__(self, base, cookie=None):
        parsed = urlsplit(base)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("--api must be a loopback HTTP(S) origin, without credentials or path")
        self.base = base.rstrip("/")
        self.cookie = cookie
        # Direct loopback requests only; do not forward a session through a proxy/redirect.
        from urllib.request import ProxyHandler

        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, body=None, key=None, *, method=None):
        headers = {"Accept": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if body is not None:
            headers.update({"Content-Type": "application/json", "X-GEOMG-Request": "1"})
        if key:
            headers["Idempotency-Key"] = str(key)
        request = Request(
            self.base + PREFIX + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        for attempt in range(4):
            try:
                with self.opener.open(request, timeout=120) as response:
                    return json.load(response)
            except HTTPError as exc:
                status = exc.code
                exc.close()
                if status < 500 or attempt == 3:
                    raise ApiError(f"GEOMG API returned HTTP {status}", status) from None
            except URLError, TimeoutError, ConnectionError:
                if attempt == 3:
                    raise ApiError("GEOMG API connection failed after retries") from None
            time.sleep(2**attempt)
