from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .api.routes import router
from .config import get_settings, validate_security_settings
from .database import init_db
from .services.rate_limit import check_rate_limit
from .services.telemetry import reset_trace_id, set_trace_id


logger = logging.getLogger("careerfit.api")
TRACE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_settings(get_settings())
    init_db()
    yield


settings = get_settings()
app = FastAPI(
    title="Career Fit AI API",
    version="0.1.0",
    description="Profile-aware job fit scoring and resume advice.",
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "Server-Timing", "X-Trace-ID"],
)


@app.middleware("http")
async def public_beta_rate_limit(request, call_next):
    supplied_trace = request.headers.get("x-request-id", "")
    trace_id = supplied_trace if TRACE_PATTERN.fullmatch(supplied_trace) else uuid4().hex
    trace_token = set_trace_id(trace_id)
    started = time.perf_counter()
    limited = check_rate_limit(request)
    if limited is not None:
        limited.headers["X-Trace-ID"] = trace_id
        reset_trace_id(trace_token)
        return limited
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000)
        logger.exception(
            "request_failed method=%s path=%s trace_id=%s duration_ms=%s",
            request.method,
            request.url.path,
            trace_id,
            duration_ms,
        )
        response = JSONResponse(
            {
                "detail": "Unexpected server error. Try again and keep the reference code if the problem continues.",
                "code": "SERVER_ERROR",
                "trace_id": trace_id,
            },
            status_code=500,
        )
    duration_ms = round((time.perf_counter() - started) * 1000)
    response.headers["X-Trace-ID"] = trace_id
    response.headers["Server-Timing"] = f'app;dur={duration_ms}'
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    logger.info(
        "request_complete method=%s path=%s status=%s trace_id=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        trace_id,
        duration_ms,
    )
    reset_trace_id(trace_token)
    return response


app.include_router(router)
