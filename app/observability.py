"""Logging with the request id on every line. Use logging.getLogger("app.<module>") anywhere in the code."""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
log = logging.getLogger("app")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s")
    )
    handler.addFilter(_RequestIdFilter())
    logger = logging.getLogger("app")
    logger.handlers = [handler]
    logger.setLevel(level)
