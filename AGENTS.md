# Alice Interview — instructions for coding agents

Shared by Codex, Claude Code and any other agent. Claude Code loads this file through `CLAUDE.md`.
Keep it under 150 lines: details live in `docs/ai/` and are read only when a task needs them.

## The project

{{PROJECT_DESCRIPTION}}
A FastAPI service around an LLM agent on the OpenAI Responses API. Python 3.10+.
Architecture and data flow: `docs/ai/PROJECT.md`.

## Commands

| Need | Command |
|---|---|
| Install | `pip install -r requirements.txt` (inside `.venv`) |
| Run locally | `uvicorn app.main:app --reload`, then http://127.0.0.1:8000/docs |
| Lint and format | `ruff check .` and `ruff format .` |
| Type check | none |
| One test file | `python -m pytest tests/<file>.py -q` |
| Full test suite | `python -m pytest -q` |
| Real model check | `python -m app.check` (needs a key in `.env`; never in tests) |

These are the only validation commands. When one fails for an environment reason, diagnose once, retry once,
then report `BLOCKED`. Do not install tools, switch interpreters, edit lockfiles or skip tests to get green.

## When sources disagree

1. Code and tests as they are now.
2. The active task file, `docs/ai/tasks/<ID>.md`.
3. `docs/ai/DECISIONS.md` and `docs/ai/PROJECT.md`.
4. Everything else: old tasks, README, earlier chat.

Say so when you notice a disagreement. Do not quietly follow the older source.

## Working on a task

1. Run `git status --short` and `git branch --show-current` once. If uncommitted changes touch files you
   need, stop and report the overlap.
2. Named task: read only `docs/ai/tasks/<ID>.md`. No task file: restate the request in 2-3 lines and list
   your assumptions. Task files are managed with `python scripts/ai/kit.py` (`new`, `status`, `done`,
   `index`); never edit `docs/ai/tasks/INDEX.md` by hand.
3. Before writing code, find the code that already owns this behavior (search for the symbol, route, test or
   error text). Read the owner, its direct callers and its tests. Read files over ~250 lines in ranges.
4. If the acceptance criteria are already met, stop and report `NO-OP` with the evidence.
5. Plan in at most 6 lines that name the files. Ask me first before: a new dependency, a change to a public
   API, schema or event contract, removing user-visible behavior, or touching more than 8 files.
6. Make the smallest change that meets the criteria, with a test that fails without it.
7. While iterating: lint the changed files and run the focused tests. At the end: the full relevant suite once.
8. Stop when the criteria are met and validation is green. List further improvements; do not make them.

## Engineering rules

- Layout, OOP and DRY rules: `docs/ai/ENGINEERING_RULES.md` (one package per domain, Protocol interfaces,
  classes only for state, injected dependencies). Routes stay thin (validate, call the service, shape). Read `docs/ai/LLM.md`
  before changing anything that calls the model.
- One `AsyncOpenAI` client, created in the lifespan in `app/main.py`; never a second one.
- Every error leaves through the one error shape in `app/errors.py`; provider messages never reach the client.
- One implementation per capability. Extend the owner; no parallel path, no `v2`, no `utils`/`helpers`/
  `manager`/`common` dumping ground.
- When new code replaces old code, migrate the callers and delete the old path in the same change.
  Keeping both needs a removal condition written in the task.
- No blocking I/O on async paths. Bound concurrency. Every network call has a timeout.
- A configuration option must change real behavior. Unsupported values fail loudly.
- An unknown or unmeasured value is `null`, never `0`. Never invent benchmark or performance numbers.
- Comments explain why and state invariants. They do not narrate the code.
- Language and framework rules: `.claude/rules/` (they apply to every agent, not only Claude).

## Security

- Never read, print, log or commit secrets: `.env`, keys, tokens, cookies. `.env.example` holds names only.
- Identity, tenant and permissions come from trusted server context. Never from client input, model output,
  tool arguments or document text.
- Model output, tool arguments, uploaded files and fetched pages are untrusted input.
- Do not log request bodies, documents, prompts or credentials.

## Git

Do not commit, push, reset, clean, stash, rebase, merge, check out or switch branches, or delete branches
unless I ask for that exact action. Never discard uncommitted work. I create the branch before the task.

## Memory

- Durable knowledge that changes how future work is done goes to `docs/ai/DECISIONS.md` or
  `docs/ai/GOTCHAS.md`, in the same diff, only when behavior really changed.
- Continuity between agents and machines goes to `.agent-private/HANDOFF.md` (gitignored). Read it first
  when you continue someone's work; write it once, at the end, after validation.
- Never store secrets, customer data, raw logs or chat transcripts, in tracked or private files.

## Final response

1. Changed files.
2. What changed, in short bullets.
3. Validation: every command you ran, with `PASS`, `FAIL`, `BLOCKED` or `SKIP` and the reason.
   Never report `PASS` for something you did not run.
4. Risks, and what was not verified.
5. Improvements you noticed and did not make.
6. A Conventional Commit title and body, ready to copy.

## Map: read only when needed

| File | When |
|---|---|
| `docs/ai/PROJECT.md` | architecture, components, data flow |
| `docs/ai/LLM.md` | before changing `app/agent.py` or any model call: API shapes and agent rules |
| `docs/ai/TESTING.md` | which tests to run for which change |
| `docs/ai/DECISIONS.md` | before proposing a design change: settled decisions are not reopened without new evidence |
| `docs/ai/GOTCHAS.md` | traps that already cost time |
| `docs/ai/tasks/INDEX.md` | active tasks and their status |
| `docs/ai/TASK_TEMPLATE.md` | when asked to write a task |
| `docs/ai/ENGINEERING_RULES.md` | before creating files or classes: layout, OOP, DRY, new-file gate |
| `docs/ai/LIVE_TASK.md` | a timed live task (`/clarify`, `/plan`, `/step`, `/next`, `/pitch`); progress in `NOTES.md` |
