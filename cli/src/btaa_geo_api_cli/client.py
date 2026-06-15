from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import httpx

from . import __version__
from .config import CliConfig


class BtaaApiError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class BtaaApiClient:
    def __init__(
        self,
        config: CliConfig,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._headers(),
            follow_redirects=True,
            transport=transport,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": f"BTAA-Geo-API-CLI/{__version__}",
            "X-BTAA-Client-Name": "btaa-geo-api-cli",
            "X-BTAA-Client-Version": __version__,
            "X-BTAA-Client-Channel": "cli",
            "X-BTAA-Client-Instance": self.config.client_instance,
            "Accept": "application/json",
        }
        if self.config.api_key:
            headers["X-API-Key"] = self.config.api_key
        return headers

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        try:
            response = self.client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail, error_code = _error_detail(exc.response)
            raise BtaaApiError(
                detail,
                status_code=exc.response.status_code,
                error_code=error_code,
            ) from exc
        except httpx.TimeoutException as exc:
            raise BtaaApiError("Request timed out") from exc
        except httpx.RequestError as exc:
            raise BtaaApiError(f"Network request failed: {exc}") from exc

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or response.text.startswith(("{", "[")):
            return response.json()
        return response.text

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return self.request("GET", path, params=params)

    def post(self, path: str, *, json: Any | None = None) -> Any:
        return self.request("POST", path, json=json)

    def stream_download(self, url_or_path: str, output_path: Path) -> tuple[int, str | None]:
        request_url = (
            url_or_path if url_or_path.startswith("http") else f"{self.base_url}{url_or_path}"
        )
        bytes_written = 0
        content_type = None
        try:
            with self.client.stream("GET", request_url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        if chunk:
                            bytes_written += len(chunk)
                            handle.write(chunk)
        except httpx.HTTPStatusError as exc:
            detail, error_code = _error_detail(exc.response)
            raise BtaaApiError(
                detail,
                status_code=exc.response.status_code,
                error_code=error_code,
            ) from exc
        except httpx.RequestError as exc:
            raise BtaaApiError(f"Download failed: {exc}") from exc
        return bytes_written, content_type

    def resource_url(self, path: str) -> str:
        return f"{self.base_url}{path if path.startswith('/') else f'/{path}'}"


def _error_detail(response: httpx.Response) -> tuple[str, str | None]:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error_code = payload.get("error") if isinstance(payload.get("error"), str) else None
        message = payload.get("message") or payload.get("detail")
        if error_code and message:
            return f"{response.status_code}: {error_code} - {message}", error_code
        detail = message or error_code
        if detail:
            return f"{response.status_code}: {detail}", error_code
    return f"{response.status_code}: {response.reason_phrase}", None


def iter_resources(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    data = payload.get("data", []) if isinstance(payload, dict) else []
    if isinstance(data, list):
        yield from (item for item in data if isinstance(item, dict))
