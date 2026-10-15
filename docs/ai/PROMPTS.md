# Short prompts

The rules live in the repository, so prompts stay short. In Claude Code the skills do the same job.

| Goal | Claude Code | Codex or any agent |
|---|---|---|
| Where am I | `/status` | `Run python scripts/ai/kit.py list and next, check git status, and tell me the next step.` |
| Split a feature into tasks | `/plan-feature <feature>` | `Break this feature into 2-6 tasks with dependencies; show the plan, wait for my OK, then create them with python scripts/ai/kit.py new: <feature>` |
| Implement a task | `/task AUTH-03` | `Implement AUTH-03. Follow AGENTS.md. Do not commit.` |
| Plan only | `/task AUTH-03` in plan mode | `Plan AUTH-03 only. Do not edit files.` |
| Review before commit | `/review-changes` | `Review the current diff against its task and AGENTS.md. Do not edit.` |
| Write a task | `/new-task <requirement>` | `Create a task for: <requirement>. Use python scripts/ai/kit.py new, then fill the file per docs/ai/TASK_TEMPLATE.md. Do not implement.` |
| End of session | `/handoff` | `Write .agent-private/HANDOFF.md in the format of docs/ai/HANDOFF_TEMPLATE.md.` |
| Continue other agent's work | `Continue from .agent-private/HANDOFF.md. Check the diff first.` | same |
| Diagnose | `Diagnose: <symptom>. Find the owning code and its tests, explain the cause with file:line. Do not edit.` | same |
| Fix failing tests only | `Fix the failing tests of the current task only. Do not widen scope.` | same |
| Record a decision | `Add a decision to docs/ai/DECISIONS.md: <decision and reason>. No code changes.` | same |

Do not paste architecture, Git, test or security rules into prompts: AGENTS.md already has them.

Task bookkeeping is a script, not a prompt: `python scripts/ai/kit.py new | list | next | start | status | done | index | doctor`.
