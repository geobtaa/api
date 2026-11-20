from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["available"]
