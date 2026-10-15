---
name: step
description: Build one numbered step of the plan in NOTES.md, brief first, then code and tests, then a clear report. Use when the user runs /step with a step number, optionally followed by extra instructions.
disable-model-invocation: true
argument-hint: "<step number> [extra instructions]"
---

Step: $ARGUMENTS. Build only that step of "## Plan" in NOTES.md.

1. Read NOTES.md, docs/ai/LIVE_TASK.md, AGENTS.md, the docs AGENTS.md maps to this kind of change,
   .claude/rules that match the files, and the code earlier steps created. Never read answer files.
2. Show a brief and wait for "go" (the user may answer with changes):
   **📝 Step N brief** — files and signatures · decisions (with source) · tests I will write ·
   what I will not touch · anything I plan to add that was not asked, and why.
3. After "go": build it. Apply every practice in LIVE_TASK.md that fits this step. Tests need no network.
   Run lint and `python -m pytest -q`; fix until green. If the step calls a real external service,
   make one call on one sample only.
4. Do not touch files outside the step. No new dependencies without asking.
   Conflicts with project docs: follow LIVE_TASK.md.
5. Append one line to "## Log" in NOTES.md: step, result, commit.
6. Reply with the report format from LIVE_TASK.md, in full, every section present.
7. Ask "Commit?" with the proposed message. Commit only after yes.
