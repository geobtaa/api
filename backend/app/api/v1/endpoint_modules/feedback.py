import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.services.feedback_service import (
    FEEDBACK_TOPICS,
    FeedbackDeliveryUnavailable,
    FeedbackSubmission,
    send_feedback_email,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    email_address: str = Field(default="", max_length=254)
    topic: str = Field(..., min_length=1, max_length=80)
    description: str = Field(..., min_length=1, max_length=5000)
    contact_info: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=1000)
    user_agent: str = Field(default="", max_length=1000)

    @field_validator("*", mode="before")
    @classmethod
    def strip_string_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("topic")
    @classmethod
    def topic_must_be_known(cls, value: str) -> str:
        if value not in FEEDBACK_TOPICS:
            raise ValueError("Select a feedback topic.")
        return value

    @field_validator("email_address")
    @classmethod
    def email_must_be_valid_when_present(cls, value: str) -> str:
        if value and not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", value):
            raise ValueError("Enter a valid email address.")
        return value


@router.post("/feedback", include_in_schema=False)
async def submit_feedback(payload: FeedbackRequest, request: Request):
    submission = FeedbackSubmission(
        name=payload.name,
        email_address=payload.email_address,
        topic=payload.topic,
        description=payload.description,
        contact_info=payload.contact_info,
        source_url=payload.source_url or request.headers.get("referer", ""),
        user_agent=payload.user_agent or request.headers.get("user-agent", ""),
    )

    try:
        result = send_feedback_email(submission)
    except FeedbackDeliveryUnavailable as exc:
        logger.warning("Feedback delivery unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"message": "Feedback delivery is temporarily unavailable."},
        )
    except Exception:
        logger.exception("Unexpected feedback delivery failure")
        return JSONResponse(
            status_code=503,
            content={"message": "Feedback delivery is temporarily unavailable."},
        )

    return JSONResponse(
        status_code=202,
        content={
            "data": {
                "type": "feedback-submission",
                "id": "submitted",
                "attributes": {
                    "accepted": True,
                    "sent": bool(result.get("sent")),
                },
            }
        },
    )
