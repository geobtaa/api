"""Public preview contracts. Source records are never rewritten by this pipeline."""

import hashlib
import json
import math
import os
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PIPELINE_VERSION = "2"


class Outcome(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"
    OVER_LIMIT = "over-limit"
    NEEDS_REVIEW = "needs-review"


class PreviewError(Exception):
    def __init__(self, status: Outcome, detail: str):
        super().__init__(detail)
        self.status = status


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True)
    download_bytes: int = Field(default=1 << 30, gt=0)
    extracted_bytes: int = Field(default=4 << 30, gt=0)
    archive_entries: int = Field(default=10000, gt=0)
    layers: int = Field(default=8, gt=0)
    seconds: int = Field(default=900, gt=0)
    memory_bytes: int = Field(default=4 << 30, gt=0)
    temporary_bytes: int = Field(default=10 << 30, gt=0)
    output_bytes: int = Field(default=2 << 30, gt=0)

    @classmethod
    def from_env(cls):
        return cls(
            **{
                name: int(os.environ[f"PREVIEW_{name.upper()}"])
                for name in cls.model_fields
                if f"PREVIEW_{name.upper()}" in os.environ
            }
        )


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["rgb", "scalar", "classified", "vector"]
    bands: list[int] = Field(default_factory=lambda: [1])
    value_range: tuple[float, float] | None = None
    palette: dict[int, tuple[int, int, int, int]] | None = None
    ramp: Literal["viridis"] = "viridis"
    nodata: float | None = None
    units: str | None = None
    color: str = "#176b91"
    fill_opacity: float = Field(default=0.25, ge=0, le=1)
    stroke_width: float = Field(default=1.5, gt=0, le=10)
    point_radius: float = Field(default=3, gt=0, le=20)
    max_dimension: int | None = Field(default=None, ge=512)
    thumbnail_bounds: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def validate_recipe(self):
        if not self.bands or min(self.bands) < 1:
            raise ValueError("Band numbers must be positive")
        if self.kind == "rgb" and len(self.bands) != 3:
            raise ValueError("RGB recipes require three bands")
        if self.kind == "classified" and not self.palette:
            raise ValueError("Classified recipes require a known palette")
        if self.value_range and self.value_range[0] >= self.value_range[1]:
            raise ValueError("Value range must increase")
        if self.thumbnail_bounds:
            west, south, east, north = self.thumbnail_bounds
            if self.kind != "vector" or not (
                all(math.isfinite(value) for value in self.thumbnail_bounds)
                and -180 <= west < east <= 180
                and -85.0511 <= south < north <= 85.0511
            ):
                raise ValueError("Thumbnail detail requires geographic vector bounds")
        return self


class Coverage(BaseModel):
    geometry: dict | None = None
    kind: Literal[
        "data-footprint", "indexed-coverage", "metadata-extent", "geographic-focus", "unavailable"
    ]
    label: str
    provenance: str


class Layer(BaseModel):
    id: str
    name: str
    url: str
    format: Literal["cog", "pmtiles", "geojson", "wms", "arcgis", "iiif", "image"]
    source_layer: str | None = None
    bounds: list[float] | None = None
    recipe: Recipe | None = None
    asset_key: str | None = None
    byte_size: int = 0


class Manifest(BaseModel):
    version: str = "1"
    status: Outcome
    layers: list[Layer] = Field(default_factory=list)
    scope: Literal["resource", "sample"] = "resource"
    source_url: str | None = None
    source_fingerprint: str | None = None
    generated_at: str | None = None
    processing_version: str = PIPELINE_VERSION
    transformations: list[str] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)
    coverage: Coverage | None = None
    coverage_key: str | None = None
    coverage_url: str | None = None
    thumbnail_status: Outcome = Outcome.UNSUPPORTED
    thumbnail_scope: Literal["resource", "sample"] = "resource"
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None
    detail: str | None = None
    metrics: dict = Field(default_factory=dict)


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def enabled() -> bool:
    return os.getenv("PREVIEW_ASSETS_ENABLED", "false").lower() == "true"


def publication_allowed(resource_id: str) -> bool:
    """Explicit rollout selection after access/reuse and visual review; no wildcard."""
    approved = {
        value.strip()
        for value in os.getenv("PREVIEW_APPROVED_RESOURCE_IDS", "").split(",")
        if value.strip() and value.strip() != "*"
    }
    return str(resource_id) in approved


def eligible(record: dict) -> bool:
    fields = {key.lower(): value for key, value in record.items()}
    return (
        fields.get("dct_accessrights_s") == "Public"
        and not fields.get("gbl_suppressed_b", False)
        and fields.get("publication_state", "published") == "published"
    )
