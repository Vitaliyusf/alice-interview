---
name: next
description: Where am I and what do I do now. Reads NOTES.md and git, answers in a few lines. Use when the user runs /next or says they are stuck.
disable-model-invocation: true
---

Read NOTES.md and run `git status --short` and `git log --oneline -5`. Write no code.

Reply in English, at most 8 lines:
**📍 Where you are** — which section of NOTES.md is done, which step of the plan, are tests green.
**👉 Now** — the single next command to run, exactly as it should be typed.
**⚠️ Watch out** — one risk if there is one (uncommitted work, failing test, time).
If NOTES.md does not exist: "Start with /clarify <task>".
