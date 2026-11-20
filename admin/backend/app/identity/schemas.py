from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import SESSION_READ_PERMISSION
from app.sets.schemas import SetID


class Grants(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: list[str] = Field(max_length=100)
    set_ids: list[SetID] | None = Field(
        default_factory=list,
        max_length=1000,
        description="Explicit Set scope; empty grants no Sets, null grants all Sets",
    )

    @field_validator("permissions")
    @classmethod
    def controlled_shape(cls, values):
        import re

        if any(
            v != SESSION_READ_PERMISSION
            and not re.fullmatch(r"[a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)+", v)
            for v in values
        ):
            raise ValueError("Permission keys must use controlled colon-separated names")
        return sorted(set(values))


class Invitation(Grants):
    idp_entity_id: str = Field(max_length=1024)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Expiry requires an explicit timezone")
        return value


class AccountChange(Grants):
    lock_version: int = Field(gt=0)
    active: bool


class SignIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation_token: str | None = Field(default=None, max_length=256)
