from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

SourceID = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
Title = Annotated[str, Field(min_length=1, max_length=250)]


class SourceFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: Title
    description: str = Field(default="", max_length=5000)
    landing_page: str | None = Field(
        default=None,
        max_length=2048,
        description="Public homepage or browse URL, not an acquisition endpoint or credential.",
    )
    admin_notes: str = Field(default="", max_length=10000, description="Staff-only notes")
    legacy_code: str | None = Field(
        default=None, max_length=128, description="Non-unique original code; not Source identity"
    )

    @field_validator("landing_page")
    @classmethod
    def safe_link(cls, value):
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "\\" in value
            or any(c.isspace() or ord(c) < 32 for c in value)
        ):
            raise ValueError("Use an HTTP(S) public URL without embedded credentials")
        _ = parsed.port
        return value


class SourceCreate(SourceFields):
    source_id: SourceID = Field(
        default_factory=lambda: uuid4().hex,
        description="Immutable, case-sensitive ID. Supply an inventory ID or omit to generate.",
    )


class SourceUpdate(SourceFields):
    title: Title | None = None
    lock_version: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def editable_fields(self):
        changed = self.model_fields_set - {"lock_version"}
        if not changed:
            raise ValueError("Supply at least one editable field")
        if "title" in changed and self.title is None:
            raise ValueError("Title cannot be cleared")
        return self


class SourceResponse(SourceFields):
    source_id: str
    lock_version: int
    created_at: datetime
    updated_at: datetime


class SourcePage(BaseModel):
    items: list[SourceResponse]
    total: int
    offset: int
    limit: int


class SourceEditorContract(BaseModel):
    create: bool
    update: bool
    activity_read: bool
    resource_read: bool
    set_read: bool
    fields: dict[str, dict[str, Any]]


ActivityOutcome = Literal["succeeded", "partially_succeeded", "failed", "cancelled", "rejected"]


class SourceActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["review.completed", "harvest.completed"]
    outcome: ActivityOutcome
    reason: str = Field(
        min_length=1, max_length=1000, description="Staff account of work and outcome"
    )
    occurred_at: AwareDatetime | None = Field(
        default=None,
        description="When work occurred, with timezone; omit for server time. No future dates.",
    )

    @field_validator("occurred_at")
    @classmethod
    def utc_time(cls, value):
        return value.astimezone(UTC) if value is not None else None


class SourceActivityResponse(BaseModel):
    id: UUID
    source_id: str
    actor_id: UUID
    actor_display_name: str
    action: Literal["source.created", "source.updated", "review.completed", "harvest.completed"]
    outcome: ActivityOutcome
    occurred_at: datetime
    recorded_at: datetime
    origin: str
    correlation_id: UUID
    reason: str | None
    details: dict


class SourceActivityPage(BaseModel):
    items: list[SourceActivityResponse]
    total: int
    offset: int
    limit: int
