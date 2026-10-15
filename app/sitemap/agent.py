"""The model loop: the model decides what to visit and how to group it; the session does the rest.

Flow: service.build_sitemap calls run_agent under a timeout; each turn sends one Responses API request
and passes the function calls to tools.run_tool.
Design: a plain bounded loop in our code, no agent framework: every stop condition (no more calls, turn
limit, nudge limit) is visible here, and an API error propagates so the service can pick the fallback.
"""

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
    # The whole conversation is resent each turn (previous_response_id is not used): the history is ours.
    items: list[Any] = [
        {
            "role": "user",
            "content": task(session.root, limits.max_pages, limits.max_depth, session.section_cap),
        }
    ]
    nudges = 0
    # max_turns is a safety net, not a plan: a normal run ends well before it, and it stops a model that
    # loops on refused calls from spending tokens until the timeout.
    for turn in range(1, limits.max_turns + 1):
        session.stats.turns = turn
        # Send: the instructions and tools go with every request.
        response = await client.responses.create(
            model=model, instructions=SYSTEM, input=items, tools=TOOL_SPECS
        )
        calls = [item for item in response.output if item.type == "function_call"]
        items += response.output
        if not calls:
            # Nudge: the model stopped with budget and unvisited links left. max_nudges bounds it, so a
            # model that really has nothing left to add is not pushed in a loop.
            pages_left = limits.max_pages - len(session.visited)
            pending = len(session.pending())
            if pages_left > 0 and pending and nudges < limits.max_nudges:
                nudges += 1
                log.info(
                    "agent stopped early pages_left=%d pending=%d: nudge %d", pages_left, pending, nudges
                )
                items.append({"role": "user", "content": nudge(pages_left, pending)})
                continue
            # Stop: no tool calls and no reason (or no nudges left) to push on.
            log.info("agent finished turn=%d status=%s", turn, response.status)
            return "done"
        # Run tools: in the order the model asked, each result paired with its call_id, as the API needs.
        for call in calls:
            result = await run_tool(session, call.name, call.arguments)
            items.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)}
            )
    log.warning("agent hit the turn limit of %d", limits.max_turns)
    return "turn_limit"
