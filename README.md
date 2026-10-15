# Alice Interview

{{PROJECT_DESCRIPTION}}

## Run

```bash
# activate the virtual environment first: .venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate
cp .env.example .env          # then put your OPENAI_API_KEY in .env
python -m app.check           # one real call: checks the key and the model
uvicorn app.main:app --reload # http://127.0.0.1:8000/docs
```

## Test

```bash
python -m pytest -q
ruff check . && ruff format --check .
```

## Working with coding agents

Claude Code and Codex read `AGENTS.md`. Tasks live in `docs/ai/tasks/` and are managed with
`python scripts/ai/kit.py` (`list`, `next`, `new`, `start`, `done`, `doctor`). In Claude Code: `/status`,
`/plan-feature`, `/new-task`, `/task <ID>`, `/review-changes`, `/handoff`.
