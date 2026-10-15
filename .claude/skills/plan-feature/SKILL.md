---
name: plan-feature
description: Break a feature into small, ordered task files with dependencies, after the user approves the plan. Use when the user runs /plan-feature.
disable-model-invocation: true
argument-hint: "<feature description>"
---

Feature: $ARGUMENTS

1. Read AGENTS.md and `docs/ai/PROJECT.md`. Find the code that owns the areas this feature touches.
2. Propose a plan as a table, and wait for my OK before creating anything:
   | # | Title | What it delivers (observable) | Depends on | Size (S/M) |
   - 2 to 6 tasks. Each one is mergeable on its own and leaves the system working.
   - First the task that de-risks the rest (contract, data model, the hardest unknown), last the polish.
   - No task bigger than about a day. No "refactor everything" task: refactoring rides with the task that needs it.
   - Name what the plan deliberately leaves out.
3. After my OK, create each task in order with
   `python scripts/ai/kit.py new <AREA> "<title>" --depends <ids> --priority <P>`, then fill each one as
   `/new-task fill <ID>` describes (owner in the code, acceptance criteria, non-goals, validation).
4. Finish with `python scripts/ai/kit.py index` and `python scripts/ai/kit.py next`. Do not implement anything.
