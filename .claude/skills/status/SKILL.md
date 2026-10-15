---
name: status
description: Where things stand - open tasks, the current branch and diff, a pending handoff - and the one next step. Use when the user runs /status.
disable-model-invocation: true
---

Read only; change nothing.

1. Run `python scripts/ai/kit.py list`, `python scripts/ai/kit.py next`, `git status --short`,
   `git branch --show-current` and `git log -5 --oneline`.
2. If `.agent-private/HANDOFF.md` exists, read it.
3. Answer in at most 8 lines: the active task and how far it got (from the diff and the handoff, not from
   memory), anything uncommitted that does not belong to it, blocked tasks and what they wait for, and the
   single next step as a command I can copy.
