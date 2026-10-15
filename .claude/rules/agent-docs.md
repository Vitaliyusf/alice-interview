---
paths:
  - "AGENTS.md"
  - "CLAUDE.md"
  - ".claude/**"
  - "docs/ai/**"
---
# Agent instruction files

- AGENTS.md stays under 150 lines, CLAUDE.md under 40. Detail goes to `docs/ai/` or to a path rule.
- Edit the rule that is wrong. Do not add a later section that "supersedes" an earlier one.
- Shared rules go to AGENTS.md; only Claude-specific mechanics go to CLAUDE.md.
- Tasks: create, change status and finish them with `python scripts/ai/kit.py`; `INDEX.md` is generated.
- Run `python scripts/ai/check_context.py` after changing any of these files.
