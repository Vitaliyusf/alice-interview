---
name: review-changes
description: Review the current changes against the active task and AGENTS.md through the independent reviewer subagent, without editing. Use when the user runs /review-changes.
disable-model-invocation: true
argument-hint: "[task-id]"
---

Delegate this review to the `reviewer` subagent. It starts with a fresh context, so the review is not done by
the agent that wrote the code. Pass it only: the task ID ($ARGUMENTS, if given) and that the scope is the
current uncommitted changes. Do not pass your own explanation of the change.

Show me its report as it is. Then say which findings you agree with and why, and fix nothing until I ask.
