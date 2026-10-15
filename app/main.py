"""Application factory. Run with:  uvicorn app.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.middleware import RequestContextMiddleware
from app.observability import log, setup_logging
from app.routes import ask, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: load settings and open one OpenAI client. Shutdown: close it."""
    try:
        settings: Settings = app.state.settings or get_settings()
    except ValidationError as exc:  # fail fast, with a message that says what to fix
        fields = ", ".join(
            str(error["loc"][0]).upper() if error["loc"] else "SETTINGS" for error in exc.errors()
        )
        raise RuntimeError(
            f"Bad configuration: {fields}. Copy .env.example to .env and fill it in."
        ) from None
    app.state.settings = settings
    setup_logging(settings.log_level)
    app.state.openai = AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_s,  # the SDK default is 10 minutes
        max_retries=settings.openai_max_retries,  # the SDK retries 408, 409, 429, 5xx and connection errors
    )
    log.info("started model=%s timeout=%ss", settings.openai_model, settings.openai_timeout_s)
    yield
    await app.state.openai.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Tests pass their own Settings. Without one, they are read from .env when the app starts."""
    app = FastAPI(title="Agent API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(ask.router, prefix="/v1")
    return app


app = create_app()
