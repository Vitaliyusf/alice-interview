# How the agent docs work

`AGENTS.md` is the only file every agent reads every time. It is a map: rules that always apply, the commands,
and pointers. Everything here in `docs/ai/` is read on demand, when a task needs it.

| File | Holds | Changes when |
|---|---|---|
| `PROJECT.md` | architecture, components, data flow, invariants | the architecture changes |
| `TESTING.md` | test lanes and which change needs which | a lane or command changes |
| `DECISIONS.md` | settled decisions with the reason and when to revisit | a decision is made or reversed |
| `GOTCHAS.md` | traps that already cost time | an agent or a person fell into one |
| `TASK_TEMPLATE.md` | the shape of a task file | rarely |
| `tasks/INDEX.md` | active tasks and their status | every task |
| `tasks/<ID>.md` | one task: goal, criteria, scope | while the task is open |
| `tasks/done/` | finished tasks, kept as history | a task is finished |
| `PROMPTS.md` | short prompts for the human | rarely |
| `HANDOFF_TEMPLATE.md` | the shape of `.agent-private/HANDOFF.md` | rarely |

Rules for keeping it healthy:

- One fact lives in one place. If two files say the same thing, delete one and point to the other.
- Fix the wrong sentence. Never add a newer section that "overrides" an older one.
- No version suffixes (`_V2`, `_V3`). Git keeps the history.
- `python scripts/ai/check_context.py` checks sizes, dead paths, unfilled placeholders, path rules, task
  files and that private files are ignored. CI runs it too.
