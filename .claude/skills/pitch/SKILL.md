---
name: pitch
description: Prepare the final 5-minute presentation and likely follow-up answers from NOTES.md, code and results. Use when the user runs /pitch.
disable-model-invocation: true
---

Read NOTES.md, docs/ai/LIVE_TASK.md and the code. Show the last eval or demo results if they exist;
do not rerun anything unless asked. Write no code.

Reply with short lines to read aloud, in English:
**1. What I built** — one sentence.
**2. Flow** — 30 seconds.
**3. Decisions** — three, each "I chose X over Y because Z".
**4. Demo** — the order to show: a normal case, an attack or edge case, a failure/fallback, with the exact commands.
**5. Results** — N/M, why the misses happened, how I would fix them.
**6. What I'd add** — three items.
**7. Likely follow-ups** — five likely follow-ups ("add a second provider", "add a tool", "how do you test the agent",
"what if the model is down", "how would you scale this"), each with a two-line answer tied to this code.
