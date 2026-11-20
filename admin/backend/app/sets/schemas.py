"""Set catalog contracts; configuration labels do not authorize execution."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.sources.schemas import SourceFields, SourceID, Title

SetID = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
SetStatus = Literal["active", "inactive", "retired"]


class SetFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Title
    legacy_code: str = Field(default="", max_length=128, description="Non-unique legacy label")
    set_scope: str = Field(default="", max_length=5000)
    description: str = Field(default="", max_length=5000)
    endpoint_url: str | None = Field(
        default=None,
        max_length=2048,
        description="HTTP(S) endpoint without embedded credentials; never fetched by this editor",
    )
    endpoint_description: str = Field(default="", max_length=1000)
    workflow_catalog_id: str | None = Field(
        default=None, max_length=128, description="Shared descriptive workflow catalog ID"
    )
    workflow: str = Field(
        default="",
        max_length=128,
        description="Descriptive workflow label, not an executable Workflow binding",
    )
    review_interval: str = Field(
        default="", max_length=64, description="Descriptive interval; does not establish a schedule"
    )
    harvest_interval: str = Field(
        default="", max_length=64, description="Descriptive interval; does not establish a schedule"
    )
    tags: str = Field(default="", max_length=2000, description="Pipe-delimited reference tags")
    admin_notes: str = Field(default="", max_length=10000, description="Staff-only notes")

    @field_validator("endpoint_url")
    @classmethod
    def safe_endpoint(cls, value):
        return SourceFields.safe_link(value)


class SetCreate(SetFields):
    status: Literal["active", "inactive"] = Field(default="active")
    set_id: SetID = Field(
        default_factory=lambda: uuid4().hex,
        description="Immutable case-sensitive identity; omit to generate",
    )
    source_id: SourceID = Field(description="Required existing Source; immutable in this increment")


class SetUpdate(SetFields):
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


class SetResponse(SetFields):
    represented_by_id: str | None = None
    resource_count: int = 0
    status: SetStatus
    set_id: str
    source_id: str
    lock_version: int
    created_at: datetime
    updated_at: datetime


class SetPage(BaseModel):
    items: list[SetResponse]
    total: int
    offset: int
    limit: int


class SetStateAction(BaseModel):
    current: SetStatus
    target: SetStatus
    label: str


class SetStateChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    target: SetStatus
    lock_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=1000)
    confirmed: bool = Field(strict=True)

    @field_validator("confirmed")
    @classmethod
    def confirmation_required(cls, value):
        if not value:
            raise ValueError("Confirm the reviewed state change")
        return value


class SetStatePreview(BaseModel):
    set_id: str
    title: str
    current: SetStatus
    target: SetStatus
    lock_version: int
    open_tasks: int
    active_jobs: int
    managed_resources: int
    can_proceed: bool
    consequences: list[str]


class SetEditorContract(BaseModel):
    create: bool
    update: bool
    activity_read: bool
    workflow_read: bool
    representative_update: bool
    fields: dict[str, dict[str, Any]]
    states: list[SetStatus]
    state_actions: list[SetStateAction]


class SetActivityResponse(BaseModel):
    id: UUID
    set_id: str
    actor_id: UUID
    actor_display_name: str
    action: str
    outcome: Literal["succeeded", "partially_succeeded", "failed", "cancelled", "rejected"]
    resource_id: str | None = None
    workflow_id: UUID | None = None
    workflow_version_id: UUID | None = None
    job_id: UUID | None = None
    occurred_at: datetime
    recorded_at: datetime
    reason: str | None
    details: dict


class SetActivityPage(BaseModel):
    items: list[SetActivityResponse]
    total: int
    offset: int
    limit: int
