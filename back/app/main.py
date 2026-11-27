"""FastAPI application. Every route lives under /api (proxied by nginx)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import async_engine
from app.errors import FormError, form_error_handler, validation_error_handler
from app.routers import auth, me, oauth

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs every request URL at INFO; keep provider calls out of the logs.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await async_engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Hypertube API",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    # Short-lived signed cookie, only used by Authlib to keep the OAuth state
    # between /login and /callback. User sessions use their own cookie.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key.get_secret_value(),
        session_cookie="hypertube_oauth",
        max_age=600,
        same_site="lax",
        https_only=settings.cookie_secure,
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(FormError, form_error_handler)

    for module in (auth, oauth, me):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
