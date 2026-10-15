---
name: clarify
description: Start of a live timed task. Reads the task and data, writes a restatement, findings and clarifying questions to NOTES.md. Use when the user runs /clarify.
disable-model-invocation: true
argument-hint: "[task file path, or paste the task text]"
---

Task: $ARGUMENTS. If it is a path, read it. If it is text, save it under "## Task" in NOTES.md.
If empty, use "## Task" from NOTES.md or TASK.md.

1. Read docs/ai/LIVE_TASK.md and AGENTS.md. Follow "Never read answer files".
2. Read the data and code the task points to. Write no code.
3. Write under "## Clarify" in NOTES.md and show it, in this shape:

**🔁 What I understood** — one sentence in English to say aloud: "So X comes in, Y happens, Z goes out. Right?"

**🔎 Data findings** — table: | Finding | What it means for the design |, 3-6 rows.

**❓ Questions for the interviewer** — at most 4, in English, each a proposal: "I'll assume ___ — OK?"
Use the lenses in LIVE_TASK.md; skip any whose answer would not change what is built.
Under each: why I ask, and the default if there is no answer.

**👉 Next** — "Paste the interviewer's answers: /plan <answers>". If no answers come, /plan uses the defaults.
