---
name: plan
description: Build the six-line plan, numbered steps and a spoken pitch from NOTES.md and the interviewer's answers. Use when the user runs /plan.
disable-model-invocation: true
argument-hint: "[interviewer answers, or empty to use defaults]"
---

Answers: $ARGUMENTS. Save them under "## Answers" in NOTES.md (or "defaults used").

1. Read NOTES.md, docs/ai/LIVE_TASK.md, AGENTS.md, and the docs AGENTS.md maps to this kind of work.
   Write no code.
2. Write under "## Plan" in NOTES.md and show it:

**🗺️ Plan** — the six lines from LIVE_TASK.md, in English, each ending "(because: ...)".

**🪜 Steps** — table: | # | What | Done when (test) | ~min |. Use the default build order unless
the task needs another.

**⚖️ Trade-offs** — 2-3 bullets: what I chose, what I gave up.

**⚠️ Conflicts with project docs** — anything in the plan that differs from AGENTS.md or docs/ai, and why
the task wins. "None" if none.

**🗣️ Pitch** — 5-6 English sentences to say aloud, each decision with "because".

**👉 Next** — "Say the pitch out loud, then /step 1".
