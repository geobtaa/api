"""Version-one declarative authoring contract; configuration never contains executable code."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.sets.schemas import SetID
from app.sources.schemas import SourceFields

PROCESS_TYPES = {
    "template_children": ("Template children", "Create child metadata from a named template."),
    "template_csv": ("CSV template", "Construct metadata using a named CSV template."),
    "template_website": ("Website template", "Construct website metadata using a named template."),
    "template_json": ("JSON template", "Construct metadata using a named JSON template."),
    "harvest": ("Harvest", "Acquire source candidates for validation and review."),
    "transform": ("Transform", "Apply a named, versioned metadata mapping."),
    "validate": ("Validate", "Check metadata against the managed validation contract."),
    "review": ("Review", "Review candidates before accepting managed changes."),
    "publish": ("Publish", "Deliver accepted metadata through managed publication."),
}
CONFIG_FIELDS = {
    **{key: ["template_ref"] for key in PROCESS_TYPES if key.startswith("template_")},
    "harvest": ["endpoint_url", "credential_ref"],
    "transform": ["mapping_ref"],
    "validate": [],
    "review": [],
    "publish": [],
}
Reference = Annotated[
    str,
    Field(
        pattern=r"^[a-z][a-z0-9]*(?:[._/-][a-z0-9]+)*$",
        min_length=1,
        max_length=120,
        description="Named reference, never a credential value or executable expression.",
    ),
]


class Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    endpoint_url: str | None = Field(default=None, max_length=2048, title="Endpoint override")
    template_ref: Reference | None = Field(default=None, title="Template reference")
    mapping_ref: Reference | None = Field(default=None, title="Mapping reference")
    credential_ref: Reference | None = Field(default=None, title="Managed credential reference")

    @model_validator(mode="after")
    def safe_endpoint(self):
        if self.endpoint_url is not None:
            SourceFields.safe_link(self.endpoint_url)
            parsed = urlsplit(self.endpoint_url)
            if parsed.query or parsed.fragment:
                raise ValueError("Use an endpoint without query parameters or fragment")
        return self


class Process(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    position: int = Field(ge=1, le=100, strict=True)
    process_type: str
    name: str = Field(min_length=1, max_length=200)
    configuration_schema_version: Literal[1] = 1
    configuration: Configuration = Field(default_factory=Configuration)

    @model_validator(mode="after")
    def supported_configuration(self):
        if self.process_type not in PROCESS_TYPES:
            raise ValueError("Unknown process type")
        supplied = self.configuration.model_dump(exclude_none=True)
        if set(supplied) - set(CONFIG_FIELDS[self.process_type]):
            raise ValueError("Configuration fields are not supported by this process type")
        return self


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    processes: list[Process] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def ordered(self):
        if [p.position for p in self.processes] != list(range(1, len(self.processes) + 1)):
            raise ValueError("Process positions must be unique, contiguous, and ordered from 1")
        return self


class WorkflowCreate(Definition):
    set_id: SetID
    title: str = Field(min_length=1, max_length=250)


class DraftUpdate(Definition):
    lock_version: int = Field(ge=1, strict=True)


class VersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lock_version: int = Field(ge=1, strict=True)


class Activation(VersionCommand):
    version_id: UUID
    confirmed: Literal[True]


class VersionResponse(BaseModel):
    version_id: UUID
    workflow_id: UUID
    number: int
    state: Literal["draft", "active", "superseded"]
    checksum: str | None
    created_at: datetime
    activated_at: datetime | None
    processes: list[Process]


class WorkflowSummary(BaseModel):
    workflow_id: UUID
    set_id: SetID
    title: str
    lock_version: int
    created_at: datetime
    updated_at: datetime


class WorkflowResponse(WorkflowSummary):
    active: VersionResponse | None
    draft: VersionResponse | None
    can_change: bool
    can_activate: bool


class WorkflowPage(BaseModel):
    items: list[WorkflowSummary]
    total: int
    offset: int
    limit: int


class VersionPage(BaseModel):
    items: list[VersionResponse]
    total: int
    offset: int
    limit: int
