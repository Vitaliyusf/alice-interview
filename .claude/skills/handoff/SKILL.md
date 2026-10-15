---
name: handoff
description: Write the end-of-session handoff to .agent-private/HANDOFF.md so another agent or machine can continue. Use when the user runs /handoff.
disable-model-invocation: true
---

Write `.agent-private/HANDOFF.md`, replacing its content, in the format of `docs/ai/HANDOFF_TEMPLATE.md`.

- Check first that `.agent-private/` is ignored by git (`git check-ignore -q .agent-private/`). If not, stop.
- Base it on the real state: `git status --short`, `git diff --stat`, the tests you actually ran.
- Repo-relative paths only. No secrets, tokens, customer data, raw logs or chat transcript.
- At most 40 lines. Facts and next steps, not a story.
