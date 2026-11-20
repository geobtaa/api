from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

from app.identity.schemas import Grants

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    ),
]


class LocalAccount(Grants):
    email: Email


class ResetAccount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email


class PasswordLogin(ResetAccount):
    password: SecretStr = Field(min_length=15, max_length=256)
    setup_code: SecretStr | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def nonblank(cls, value):
        if not value.get_secret_value().strip():
            raise ValueError("Enter a password")
        return value


class SetupResponse(BaseModel):
    actor_id: UUID
    expires_at: datetime
    setup_code: str | None
