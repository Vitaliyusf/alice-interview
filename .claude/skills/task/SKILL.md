---
name: task
description: Implement one task from docs/ai/tasks by its ID, test first, following AGENTS.md. Use when the user runs /task with a task ID.
disable-model-invocation: true
argument-hint: "<task-id>"
---

Implement task $ARGUMENTS.

1. Read `docs/ai/tasks/$ARGUMENTS.md` only. If it does not exist, stop and say so. If it still has `{{`
   placeholders, stop and suggest `/new-task fill $ARGUMENTS`. If its status is `todo`, run
   `python scripts/ai/kit.py status $ARGUMENTS active`.
2. If `.agent-private/HANDOFF.md` mentions this task, read it and check the current diff before editing.
3. Follow "Working on a task" in AGENTS.md, including its stop conditions.
4. Test first: for each acceptance criterion write or extend a test, run it, and show that it fails for the
   right reason. Criteria that cannot be tested (docs, config) are listed as such. Then implement until the
   tests pass.
5. Before the final response, ask the `reviewer` subagent to review the diff for this task ID. Fix the
   findings that are real and inside the task; list the rest.
6. Finish with the "Final response" format of AGENTS.md, and a last line:
   `after merge: python scripts/ai/kit.py done $ARGUMENTS`. Do not commit.
