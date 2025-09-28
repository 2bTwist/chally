from __future__ import annotations
from fastapi import APIRouter, Request
from datetime import datetime, timezone
from app.config import settings

router = APIRouter()

@router.get("/health")
async def health(request: Request):
    return{
        "status": "ok",
        "env": settings.environment,
        "time": datetime.now(timezone.utc).isoformat(),
        "request_id": request.headers.get("x-request-id") or request.state.request_id,
    }

@router.get("/version")
async def version():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "git_sha": settings.git_sha,
        "build": "docker",
    }
