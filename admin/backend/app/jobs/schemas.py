from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.sets.schemas import SetID


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str = Field(min_length=1, max_length=512)
    lock_version: int = Field(gt=0)


class Submit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: SetID
    workflow_version_id: UUID | None = None
    selection: list[Selection] | None = Field(default=None, min_length=1, max_length=500)
    selection_id: UUID | None = None

    @model_validator(mode="after")
    def unique_selection(self):
        if (self.selection is None) == (self.selection_id is None):
            raise ValueError("Supply exactly one inline selection or saved selection ID")
        if self.selection and len({row.resource_id for row in self.selection}) != len(
            self.selection
        ):
            raise ValueError("Selection contains duplicate Resource identifiers")
        return self


class JobResponse(BaseModel):
    job_id: UUID
    set_id: SetID
    workflow_id: UUID | None
    workflow_version_id: UUID | None
    operation: str
    state: Literal[
        "queued", "running", "succeeded", "partially_succeeded", "failed", "cancelled", "rejected"
    ]
    attempt_number: int
    created_at: datetime
    finished_at: datetime | None
    totals: dict[str, int]


class ItemResponse(BaseModel):
    position: int
    resource_id: str
    resource_version: int
    disposition: str
    details: dict


class ItemPage(BaseModel):
    items: list[ItemResponse]
    total: int
    offset: int
    limit: int


class JobPage(BaseModel):
    items: list[JobResponse]
    total: int
    offset: int
    limit: int


class JobReport(BaseModel):
    job_id: UUID
    totals: dict[str, int]
    items: list[ItemResponse]
