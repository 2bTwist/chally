from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.config import settings
from app.logging_setup import configure_logging
from app.routes.system import router as system_router
from app.routes.auth import router as auth_router
from app.routes.challenges import router as challenges_router
from app.routes.feed import router as feed_router
from app.routes.reviews import router as reviews_router
from app.routes.ledger import router as ledger_router
from app.routes.wallet import router as wallet_router
from app.routes.stripe_webhooks import router as stripe_router
import structlog

configure_logging()
log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log.info("startup", env=settings.environment, version=settings.app_version, git_sha=settings.git_sha)
    yield
    # Shutdown
    log.info("shutdown")

app = FastAPI(
    title=f"{settings.app_display_name} API", 
    version=settings.app_version, 
    lifespan=lifespan,
    description=f"{settings.app_display_name} API for peer accountability challenges"
)

# Add security scheme for Swagger UI
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "dev" else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(challenges_router)
app.include_router(feed_router)
app.include_router(reviews_router)
app.include_router(ledger_router)
app.include_router(wallet_router) 
app.include_router(stripe_router)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    structlog.contextvars.bind_contextvars(request_id=rid)
    response: Response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    structlog.contextvars.clear_contextvars()
    return response