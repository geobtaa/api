from __future__ import annotations

import os
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.slackbot_service import handle_slack_command, verify_slack_signature

router = APIRouter()


@router.get("/slack", include_in_schema=False)
async def slack_info():
    return JSONResponse(
        content={
            "name": "BTAA Geoportal Slackbot",
            "command_endpoint": "/api/v1/slack/commands",
            "configured": bool(os.getenv("SLACK_SIGNING_SECRET")),
        }
    )


@router.post("/slack/commands", include_in_schema=False)
async def slack_command(request: Request):
    body = await request.body()
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    if not signing_secret:
        raise HTTPException(status_code=503, detail="Slackbot is not configured")

    if not verify_slack_signature(
        signing_secret=signing_secret,
        body=body,
        timestamp=request.headers.get("X-Slack-Request-Timestamp"),
        signature=request.headers.get("X-Slack-Signature"),
    ):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form_data = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    response = await handle_slack_command(form_data)
    return JSONResponse(content=response)
