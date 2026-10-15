"""One middleware: an id for every request, one log line per request, a clean 500 when our code crashes.

Written as plain ASGI on purpose. The shorter @app.middleware("http") form hides a client disconnect from the
route (request.is_disconnected() stays False), and that is needed to stop an agent run nobody is waiting for.
"""

import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import error_response
from app.observability import log, request_id_var

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = (
            incoming if _SAFE_ID.fullmatch(incoming) else uuid.uuid4().hex[:12]
        )  # never trust a header as is
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 0  # 0 in the log means no response was sent, for example the client left

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:  # a bug in our code: the traceback goes to the log, the client gets no details
            log.exception("unhandled error")
            if status:  # the response already started, it is too late to send another one
                raise
            await error_response(500, "internal_error", "Internal error.")(scope, receive, send_with_id)
        finally:
            # never log bodies or headers here: they can hold user data and credentials
            elapsed_ms = (time.perf_counter() - started) * 1000
            log.info("%s %s status=%d ms=%d", scope["method"], scope["path"], status, elapsed_ms)
            request_id_var.reset(token)
