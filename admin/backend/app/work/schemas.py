from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.sets.schemas import SetID

WorkType = Literal["review", "ingest", "other"]
RecurringType = Literal["review", "ingest"]
TaskStatus = Literal["open", "in_progress", "blocked", "completed", "cancelled"]
Cadence = Annotated[str, Field(pattern=r"^P(?:[1-9][0-9]{0,2}|1000)[DWMY]$")]
Title = Annotated[str, Field(min_length=1, max_length=250)]


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskCreate(Command):
    set_id: SetID
    work_type: WorkType
    title: Title
    description: str = Field(default="", max_length=5000)
    due_on: date
    planned_on: date | None = None
    assignee_id: UUID | None = None


class TaskUpdate(Command):
    lock_version: int = Field(ge=1, strict=True)
    title: Title | None = None
    description: str | None = Field(default=None, max_length=5000)
    due_on: date | None = None
    planned_on: date | None = None
    assignee_id: UUID | None = None
    status: Literal["open", "in_progress", "blocked", "cancelled"] | None = None
    reason: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def supplied_fields(self):
        changed = self.model_fields_set - {"lock_version", "reason"}
        if not changed:
            raise ValueError("Supply at least one change")
        for name in changed - {"planned_on", "assignee_id"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self


class Evidence(Command):
    label: str = Field(min_length=1, max_length=250)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def public_link(cls, value):
        from app.sources.schemas import SourceFields

        return SourceFields.safe_link(value)


class TaskCompletion(Command):
    lock_version: int = Field(ge=1, strict=True)
    completed_at: AwareDatetime
    summary: str = Field(min_length=1, max_length=5000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    processed_count: int = Field(default=0, ge=0, le=2147483647, strict=True)
    changed_count: int = Field(default=0, ge=0, le=2147483647, strict=True)

    @field_validator("completed_at")
    @classmethod
    def utc(cls, value):
        if value > datetime.now(UTC):
            raise ValueError("Completion cannot be in the future")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def counts(self):
        if self.changed_count > self.processed_count:
            raise ValueError("Changed count cannot exceed processed count")
        return self


class TaskResponse(BaseModel):
    task_id: UUID
    set_id: str
    set_title: str
    source_id: str
    source_title: str
    work_type: WorkType
    title: str
    description: str
    status: TaskStatus
    due_on: date
    planned_on: date | None
    assignee_id: UUID | None
    assignee_name: str | None
    recurring: bool
    predecessor_id: UUID | None
    lock_version: int
    created_at: datetime
    updated_at: datetime
    created_by_id: UUID
    completed_at: datetime | None
    completion_recorded_at: datetime | None
    completed_by_id: UUID | None
    completed_by_name: str | None
    completion_summary: str | None
    evidence: list[Evidence]
    processed_count: int
    changed_count: int


class TaskPage(BaseModel):
    items: list[TaskResponse]
    total: int
    offset: int
    limit: int


class MaintenanceUpdate(Command):
    lock_version: int = Field(
        ge=0, strict=True, description="Use 0 to create; otherwise last read version"
    )
    interval: Cadence
    enabled: bool = True
    next_due_on: date | None = Field(
        default=None, description="Required when creating the first open occurrence"
    )
    assignee_id: UUID | None = None


class MaintenanceResponse(BaseModel):
    next_due_on: date | None
    set_id: str
    work_type: RecurringType
    interval: str
    enabled: bool
    assignee_id: UUID | None
    lock_version: int
    created_at: datetime
    updated_at: datetime


class PeriodCreate(Command):
    name: str = Field(min_length=1, max_length=120)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def valid_range(self):
        if self.ends_on < self.starts_on:
            raise ValueError("End date must be on or after start date")
        return self


class PeriodResponse(PeriodCreate):
    created_by_id: UUID
    period_id: UUID
    lock_version: int
    created_at: datetime


class EventResponse(BaseModel):
    event_id: UUID
    task_id: UUID
    actor_id: UUID
    actor_name: str
    action: str
    occurred_at: datetime
    recorded_at: datetime
    details: dict[str, object]


class EventPage(BaseModel):
    items: list[EventResponse]
    total: int
    offset: int
    limit: int


class ReportGroup(BaseModel):
    key: str
    label: str
    completed: int
    processed: int
    changed: int
    late: int


class WorkReport(BaseModel):
    starts_on: date
    ends_on: date
    group_by: Literal["source", "set", "work_type", "completed_by"]
    completed: int
    processed: int
    changed: int
    late: int
    groups: list[ReportGroup]
    total_groups: int
    offset: int
    limit: int


class Assignee(BaseModel):
    actor_id: UUID
    display_name: str
