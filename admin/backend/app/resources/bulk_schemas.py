import json
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.resources.editor import LABELS


class BulkEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selection_id: UUID
    values: dict[str, Any] = Field(default_factory=dict, max_length=100)
    clear_fields: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def valid_payload(self):
        data = json.dumps(self.model_dump(mode="json"), allow_nan=False)
        if len(data.encode()) > 1_000_000:
            raise ValueError("Edit requests must be at most 1 MB")
        if any("\x00" in value for value in self.clear_fields):
            raise ValueError("Fields cannot contain null characters")
        for value in self.values.values():
            entries = value if isinstance(value, list) else [value]
            if any(isinstance(v, str) and "\x00" in v for v in entries):
                raise ValueError("Metadata cannot contain null characters")
        return self


class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]


class BulkId(BaseModel):
    id: UUID


class BulkSummary(BulkId):
    selection_id: UUID
    reverts: UUID | None
    actor_name: str
    created_at: datetime
    applied_at: datetime | None
    applied_by: str | None
    fields: list[str]

    @computed_field
    @property
    def field_labels(self) -> dict[str, str]:
        return {name: LABELS.get(name, name) for name in self.fields}


class BulkHistory(BaseModel):
    items: list[BulkSummary]
    total: int
    offset: int
    limit: int


class FieldChange(BaseModel):
    before: Any
    after: Any


class BulkItem(BaseModel):
    resource_id: str
    before_version: int
    after_version: int | None
    status: Literal["ready", "changed", "unchanged", "conflict", "read_only", "active_job"]
    changes: dict[str, FieldChange]


class BulkDetail(BulkSummary):
    totals: dict[str, int]
    items: list[BulkItem]
    total: int
    offset: int
    limit: int
