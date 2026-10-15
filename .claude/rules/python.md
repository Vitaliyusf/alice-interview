---
paths:
  - "**/*.py"
---
# Python

- Type hints on new and touched code: `dict[str, T]`, `X | None`.
- Pydantic at the edges (requests, responses, config). Plain functions for pure logic; classes only for state,
  lifecycle or resources. No "manager" class around stateless functions.
- No network or database connection at import time. Clients are created once (app lifespan) and injected.
- Async code: no `time.sleep`, no sync HTTP or DB driver on the request path; offload with
  `asyncio.to_thread` or use the async client. Bound `gather` with a semaphore.
- Catch specific exceptions. Never swallow `asyncio.CancelledError`.
