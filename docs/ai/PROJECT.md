# Project context

## What it is
{{PROJECT_DESCRIPTION}}

## Components
| Component | Path | Responsibility |
|---|---|---|
| App factory | `app/main.py` | `create_app()`, lifespan: one `AsyncOpenAI` client for the whole app |
| Settings | `app/config.py` | pydantic-settings, reads `.env` (which wins over the machine environment) |
| Dependencies | `app/deps.py` | `ClientDep`, `SettingsDep`; tests replace them with `dependency_overrides` |
| API models | `app/schemas.py` | request and response contracts, validation limits |
| Model logic | `app/agent.py` | everything that talks to the model: tools, `run_tool`, the loop |
| Routes | `app/routes/` | thin: validate, call `app.agent`, shape the reply |
| Errors | `app/errors.py` | one error shape; OpenAI errors become 502 / 503 / 504 |
| Middleware | `app/middleware.py` | plain ASGI: request id, one log line per request, clean 500, sees client disconnects |
| Logging | `app/observability.py` | `logging.getLogger("app.<module>")`, request id on every line |
| Key check | `app/check.py` | `python -m app.check`: one real call to verify key and model |

## Main flow
1. `POST /v1/ask` -> `app/routes/ask.py` validates `AskRequest`.
2. It calls `app.agent`, which calls the model through the shared client.
3. The reply is shaped into `AskResponse`; OpenAI errors go to the handlers in `app/errors.py`.

## Data
None yet: the service keeps no data. Update this section when it starts to.

## External services and limits
- OpenAI, through `AsyncOpenAI`: timeout `OPENAI_TIMEOUT_S` (30 s), `OPENAI_MAX_RETRIES` (2). One stuck call can
  take about 90 s; an agent loop multiplies that by its steps.
