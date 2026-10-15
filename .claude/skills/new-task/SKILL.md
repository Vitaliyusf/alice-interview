---
name: new-task
description: Turn a requirement into a filled task file in docs/ai/tasks, or fill an existing skeleton ("fill <ID>"), without implementing it. Use when the user runs /new-task.
disable-model-invocation: true
argument-hint: "<requirement> | fill <ID>"
---

Input: $ARGUMENTS

1. If the input is `fill <ID>`, work on `docs/ai/tasks/<ID>.md`. Otherwise create the skeleton with
   `python scripts/ai/kit.py new <AREA> "<short title>" [--priority P0-P3] [--depends ID,ID]`. Pick AREA from
   the existing task ids (`python scripts/ai/kit.py list --all`) or from the part of the code it touches.
2. Find the code that owns this behavior today (symbol, route, test, error text). If the behavior already
   exists, say so, delete the new file, run `python scripts/ai/kit.py index`, and stop.
3. If the requirement leaves the outcome unclear, ask me at most 3 short questions before writing. Do not ask
   what the code can answer.
4. Fill every section of the template. Acceptance criteria are checkable by a test or a command; 2 to 6 of them.
   Non-goals name only the realistic scope traps. Validation names the exact commands from docs/ai/TESTING.md.
5. If it would take more than about a day or touch more than about 8 files, stop and propose a split
   (`/plan-feature`) instead of writing one big task.
6. At most 80 lines, no `{{` left. Run `python scripts/ai/kit.py index`. Do not implement anything.
7. End with the task id and one line: `python scripts/ai/kit.py start <ID>`.
