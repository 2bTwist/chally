from __future__ import annotations
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.logging_setup import configure_logging
import structlog

configure_logging()
log = structlog.get_logger()

app = FastAPI(title="PeerPush API", version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "dev" else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    structlog.contextvars.bind_contextvars(request_id=rid)
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    structlog.contextvars.clear_contextvars()
    return response

@app.on_event("startup")
async def on_startup():
    log.info("startup", env=settings.environment, version=settings.app_version, git_sha=settings.git_sha)

@app.on_event("shutdown")
async def on_shutdown():
    log.info("shutdown")