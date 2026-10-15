# SETUP-01 — Describe the product in the agent docs

Status: todo
Priority: P0
Depends on: none

## Goal
The agent docs say what this service is for, so agents make product-level decisions correctly.

## Acceptance criteria
- [ ] `AGENTS.md` and `docs/ai/PROJECT.md` have no `{{` placeholder left.
- [ ] `docs/ai/PROJECT.md` "Data" and "External services" match what the service really uses.
- [ ] `python scripts/ai/kit.py check --strict` passes.

## Scope
- `AGENTS.md`, `docs/ai/PROJECT.md`. Nothing else.

## Non-goals
- No code changes. No invented facts: ask me what the code does not show.

## Validation
- `python scripts/ai/kit.py check --strict`
