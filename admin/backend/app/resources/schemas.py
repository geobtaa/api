import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.sets.schemas import SetID


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: SetID
    records: list[dict[str, Any]] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def bounded(self):
        try:
            size = len(json.dumps(self.records, allow_nan=False).encode())
        except ValueError as exc:
            raise ValueError("JSON numbers must be finite") from exc
        if size > 1_000_000:
            raise ValueError("Import batches must be at most 1 MB")
        return self


class ImportCommit(ImportRequest):
    preview_hash: str = Field(pattern="^[a-f0-9]{64}$")
    confirmed: bool


class RowOutcome(BaseModel):
    row: int
    resource_id: str | None
    title: str
    outcome: str
    errors: list[str] = []
    warnings: list[str] = []


class ImportPreview(BaseModel):
    set_id: SetID
    set_title: str
    preview_hash: str
    items: list[RowOutcome]
    ready: int


class ImportResult(BaseModel):
    import_id: UUID
    set_id: SetID
    items: list[RowOutcome]
    created: int


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=10000, pattern=r"^[^\x00]+$")
    description: str | None = Field(default=None, max_length=100000, pattern=r"^[^\x00]*$")
    set_id: SetID | None = Field(default=None, description="Omit for an unassigned catalog draft.")


class CreatedResource(BaseModel):
    id: str


class ResourceResponse(BaseModel):
    source_id: str | None = Field(description="Derived from the managing Set when assigned.")
    id: str
    set_id: SetID | None
    set_title: str | None
    publication_state: str
    lock_version: int
    metadata: dict[str, Any]


class ResourcePage(BaseModel):
    can_create: bool = False
    can_bulk_edit: bool = False
    can_validate: bool = False
    can_select: bool = False
    items: list[ResourceResponse]
    total: int
    offset: int
    limit: int


class ResourceDetailResponse(ResourceResponse):
    projection_status: Literal["pending", "live"] | None = None
    can_associate: bool = False
    editable: bool = False
    distributions: list["DistributionEdit"] = []
    source_record: dict[str, Any] | None = Field(
        description="Original import evidence when present."
    )
    import_warnings: list[str]


class DistributionEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribution_type_id: int = Field(strict=True)
    url: str = Field(min_length=1, max_length=8192)
    label: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_url(self):
        from urllib.parse import urlsplit

        try:
            parsed = urlsplit(self.url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or any(c.isspace() for c in self.url)
            ):
                raise ValueError("Use an HTTP(S) URL without credentials or whitespace")
        except ValueError as exc:
            raise ValueError("Use an HTTP(S) URL without credentials or whitespace") from exc
        return self


class ResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lock_version: int = Field(strict=True, ge=1)
    values: dict[str, Any] = Field(
        default_factory=dict,
        max_length=100,
        description="Changed descriptive fields. Source is derived from the managing Set.",
    )
    clear_fields: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Clear optional descriptive fields; omission preserves values.",
    )
    distributions: list[DistributionEdit] | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def bounded(self):
        if len(json.dumps(self.model_dump(mode="json"), allow_nan=False).encode()) > 1_000_000:
            raise ValueError("Edit requests must be at most 1 MB")
        if "distributions" in self.model_fields_set and self.distributions is None:
            raise ValueError(
                "Omit Distributions to preserve them; use [] to remove them explicitly"
            )
        return self


class EditorField(BaseModel):
    name: str
    label: str
    section: str
    kind: str
    required: bool
    choices: list[str]
    multiline: bool


class EditorContract(BaseModel):
    can_bulk_edit: bool = False
    fields: list[EditorField]
    sections: list[str]
    distribution_types: list[dict[str, Any]]
    can_update: bool
    can_create: bool
    can_choose_set: bool
    maximum_values: int = Field(
        description="Maximum Distributions; descriptive arrays have no count cap"
    )


class PublishedEditPreview(BaseModel):
    preview_id: UUID
    changes: dict[str, dict[str, Any]]


class ConfirmPublishedEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_id: UUID
    confirmed: Literal[True]
    edit: ResourceUpdate
