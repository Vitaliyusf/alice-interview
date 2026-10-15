# Testing

| Lane | Command | Run it when |
|---|---|---|
| Lint | `ruff check .` and `ruff format --check .` | always |
| One file | `python -m pytest tests/<file>.py -q` | while iterating |
| Full | `python -m pytest -q` | once, at the end of a task |
| Real model | `python -m app.check` | after changing the key, the model name or the client setup |

## Rules
- No test calls the real API. Anything that calls the model uses `FakeOpenAI` from `tests/conftest.py`.
- Async code is called with `asyncio.run(...)`; pytest-asyncio is not installed.
- CI is the clean-environment authority. Locally: focused while iterating, the full suite once.
- `python -m app.check` needs a real key in `.env`; it is a manual check, never part of the suite.
