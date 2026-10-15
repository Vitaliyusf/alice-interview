"""The model loop: the model decides what to visit and how to group it; the session does the rest."""

import json
import logging
from typing import Any, Literal

from openai import AsyncOpenAI

from app.sitemap.prompts import SYSTEM, nudge, task
from app.sitemap.session import Session
from app.sitemap.tools import TOOL_SPECS, run_tool

log = logging.getLogger(__name__)

AgentStatus = Literal["done", "turn_limit"]


async def run_agent(client: AsyncOpenAI, model: str, session: Session) -> AgentStatus:
    """Run tool-calling turns until the model stops. Raises OpenAIError: the caller picks the fallback."""
    limits = session.limits
    items: list[Any] = [
        {
            "role": "user",
            "content": task(session.root, limits.max_pages, limits.max_depth, session.section_cap),
        }
    ]
    nudges = 0
    for turn in range(1, limits.max_turns + 1):
        session.stats.turns = turn
        response = await client.responses.create(
            model=model, instructions=SYSTEM, input=items, tools=TOOL_SPECS
        )
        calls = [item for item in response.output if item.type == "function_call"]
        items += response.output
        if not calls:
            pages_left = limits.max_pages - len(session.visited)
            pending = len(session.pending())
            # Models tend to stop after a handful of pages; a bounded nudge spends the budget on content.
            if pages_left > 0 and pending and nudges < limits.max_nudges:
                nudges += 1
                log.info(
                    "agent stopped early pages_left=%d pending=%d: nudge %d", pages_left, pending, nudges
                )
                items.append({"role": "user", "content": nudge(pages_left, pending)})
                continue
            log.info("agent finished turn=%d status=%s", turn, response.status)
            return "done"
        for call in calls:
            result = await run_tool(session, call.name, call.arguments)
            items.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)}
            )
    log.warning("agent hit the turn limit of %d", limits.max_turns)
    return "turn_limit"
