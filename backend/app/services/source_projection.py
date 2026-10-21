"""Validated read-through of GEOMG's public Source representation.

GEOMG remains canonical. There is no cache, local ingest, or Resource hydration.
"""

import asyncio
import json
import os
from typing import Annotated, Literal, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter, field_validator

SOURCE_PATH = "/api/v1/admin/projections/sources"
SESSION_COOKIE = "__Host-geomg-session"
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
READ_TIMEOUT_SECONDS = 10
SourceID = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]


class ProjectionFailure(Exception):
    def __init__(self, status=502):
        self.status = status
        super().__init__("Source service unavailable")


class ProjectionSettings(BaseModel):
    origin: str
    session_token: SecretStr = Field(repr=False)

    @field_validator("origin")
    @classmethod
    def safe_origin(cls, value):
        parsed = urlsplit(value)
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or any(c.isspace() or ord(c) < 32 for c in value)
            or "\\" in value
            or not (
                parsed.scheme == "https"
                or (
                    parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                )
            )
        ):
            raise ValueError("Expected an HTTPS origin or local loopback HTTP origin")
        _ = parsed.port
        return value.rstrip("/")

    @field_validator("session_token")
    @classmethod
    def opaque_session(cls, value):
        token = value.get_secret_value()
        if (
            not token
            or len(token) > 4096
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in token
            )
        ):
            raise ValueError("Expected an opaque session token")
        return value

    @classmethod
    def from_environment(cls):
        try:
            return cls(
                origin=os.environ.get("GEOMG_SOURCE_ORIGIN", ""),
                session_token=os.environ.get("GEOMG_SOURCE_SESSION_TOKEN", ""),
            )
        except ValueError:
            raise ProjectionFailure(503) from None


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Source(PublicModel):
    source_id: SourceID
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(max_length=5000)
    landing_page: str | None = Field(max_length=2048)
    resource_count: int = Field(ge=0)

    @field_validator("landing_page")
    @classmethod
    def safe_link(cls, value):
        if value is None:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "\\" in value
            or any(c.isspace() or ord(c) < 32 for c in value)
        ):
            raise ValueError("Invalid Source landing page")
        _ = parsed.port
        return value


class SourceDetail(PublicModel):
    schema_version: Literal["1"]
    source: Source


class ResourceReference(PublicModel):
    id: str = Field(min_length=1, max_length=512)
    title: str | None


class Page(PublicModel):
    schema_version: Literal["1"]
    total: int = Field(ge=0)
    offset: int = Field(ge=0, le=1000000)
    limit: int = Field(ge=1, le=500)


class SourcePage(Page):
    items: list[Source] = Field(max_length=500)


class SourceResources(Page):
    source_id: SourceID
    items: list[ResourceReference] = Field(max_length=500)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


Result = TypeVar("Result", bound=PublicModel)


class SourceAdapter:
    def __init__(self, settings=None, transport=None):
        self.settings = settings
        self.transport = transport

    async def read(
        self, model: type[Result], source_id=None, *, resources=False, q="", offset=0, limit=100
    ) -> Result:
        settings = self.settings or ProjectionSettings.from_environment()
        if source_id is not None:
            source_id = TypeAdapter(SourceID).validate_python(source_id)
        suffix = f"/{source_id}" if source_id is not None else ""
        if resources:
            suffix += "/resources"
        paged = model is not SourceDetail
        params = {"offset": offset, "limit": limit} if paged else {}
        if model is SourcePage:
            params["q"] = q
        headers = {
            "Accept": "application/json",
            "Cookie": f"{SESSION_COOKIE}={settings.session_token.get_secret_value()}",
        }
        try:
            async with asyncio.timeout(READ_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    timeout=READ_TIMEOUT_SECONDS,
                    follow_redirects=False,
                    trust_env=False,
                    transport=self.transport,
                ) as client:
                    async with client.stream(
                        "GET",
                        settings.origin + SOURCE_PATH + suffix,
                        params=params,
                        headers=headers,
                    ) as response:
                        if response.status_code == 404 and source_id is not None:
                            raise ProjectionFailure(404)
                        if (
                            response.status_code != 200
                            or response.headers.get("content-type", "").split(";")[0]
                            != "application/json"
                        ):
                            raise ProjectionFailure()
                        content = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            content.extend(chunk)
                            if len(content) > MAX_RESPONSE_BYTES:
                                raise ProjectionFailure()
            result = model.model_validate(json.loads(content, object_pairs_hook=unique_object))
            if isinstance(result, (SourcePage, SourceResources)):
                ids = [row.source_id if isinstance(row, Source) else row.id for row in result.items]
                if (
                    result.offset != offset
                    or result.limit != limit
                    or len(result.items) != min(limit, max(0, result.total - offset))
                    or len(ids) != len(set(ids))
                    or ids != sorted(ids)
                ):
                    raise ProjectionFailure()
            if isinstance(result, SourceDetail) and result.source.source_id != source_id:
                raise ProjectionFailure()
            if isinstance(result, SourceResources) and result.source_id != source_id:
                raise ProjectionFailure()
            return result
        except (httpx.TimeoutException, TimeoutError):
            raise ProjectionFailure(504) from None
        except (httpx.HTTPError, ValueError):
            # Never surface upstream bodies, URLs, cookies, or exception text publicly.
            raise ProjectionFailure() from None
