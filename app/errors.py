"""One error shape for the whole API. Upstream details go to the log, never to the client."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import APIConnectionError, APITimeoutError, OpenAIError, RateLimitError
from starlette.exceptions import HTTPException

from app.observability import log, request_id_var


def error_response(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    body = {"error": {"code": code, "message": message, **extra}, "request_id": request_id_var.get()}
    return JSONResponse(status_code=status, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        # field and problem only: the rejected value is not echoed back
        fields = [{"field": ".".join(map(str, e["loc"])), "problem": e["msg"]} for e in exc.errors()]
        return error_response(422, "invalid_request", "The request is not valid.", fields=fields)

    @app.exception_handler(HTTPException)  # 404, 405, and every `raise HTTPException(...)` in a route
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        response = error_response(exc.status_code, f"http_{exc.status_code}", str(exc.detail))
        response.headers.update(exc.headers or {})
        return response

    # The most specific class wins: APITimeoutError is also an APIConnectionError and an OpenAIError.
    @app.exception_handler(APITimeoutError)
    async def upstream_timeout(request: Request, exc: APITimeoutError) -> JSONResponse:
        log.warning("model call timed out")
        return error_response(504, "upstream_timeout", "The model did not answer in time.")

    @app.exception_handler(RateLimitError)
    async def upstream_rate_limited(request: Request, exc: RateLimitError) -> JSONResponse:
        log.warning("model rate limit: %s", type(exc).__name__)
        return error_response(503, "upstream_rate_limited", "The model is busy. Try again shortly.")

    @app.exception_handler(APIConnectionError)
    async def upstream_unreachable(request: Request, exc: APIConnectionError) -> JSONResponse:
        log.warning("model unreachable: %s", type(exc).__name__)
        return error_response(502, "upstream_unreachable", "Could not reach the model.")

    @app.exception_handler(OpenAIError)
    async def upstream_error(request: Request, exc: OpenAIError) -> JSONResponse:
        log.error("model call failed: %s", type(exc).__name__)  # the class only: messages can echo the key
        return error_response(502, "upstream_error", "The model call failed.")
