"""Typed supporting contracts and shared error representations."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

CSV_RESPONSE = {200: {"content": {"text/csv": {"schema": {"type": "string"}}}}}


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    errors: list[ValidationIssue] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: ErrorDetail


class ProcessType(BaseModel):
    key: str
    label: str
    definition: str
    configuration_fields: list[str]


class WorkflowContract(BaseModel):
    process_types: list[ProcessType]
    configuration_schema: dict[str, Any]
    maximum_processes: int
    configuration_schema_version: int
    can_create: bool


class JobContract(BaseModel):
    can_cancel: bool
    can_download: bool


class Provider(BaseModel):
    name: str
    entity_id: str


class ProvidersResponse(BaseModel):
    items: list[Provider]


class InvitationResponse(BaseModel):
    invitation_id: UUID
    token: str | None = Field(description="Returned once on creation; null on replay.")
    expires_at: datetime


class RevocationResponse(BaseModel):
    revoked: Literal[True]


class AccountResponse(BaseModel):
    actor_id: UUID
    display_name: str
    active: bool
    lock_version: int
    permissions: list[str]
    set_ids: list[str] | None


class AccountUpdateResponse(BaseModel):
    actor_id: UUID
    lock_version: int


class SignInResponse(BaseModel):
    authenticated: Literal[True]
    expires_at: datetime


class SignOutResponse(BaseModel):
    authenticated: Literal[False]
