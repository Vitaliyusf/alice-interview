"""Decide: the one model step. The model groups the extracted pages into sections and names the ones to drop.

Flow: __main__ calls decide() with the Snapshot from extract; build turns the returned Decision (or None)
into the Sitemap.
Design: the model sees the snapshot as numbered lines and answers by page id through strict Structured
Outputs. Its only tool, get_page, reads the in-memory snapshot, so the model cannot reach the network.
A model error, an invalid or cut-off answer, or the timeout returns no Decision: build then uses the
URL-based sections, so none of those failures aborts the run. __main__ takes the same fallback when
there is no API key.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal, get_args
from urllib.parse import urlsplit

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, ValidationError

from app.sitemap.limits import CrawlLimits
from app.sitemap.models import Snapshot
from app.sitemap.prompts import SYSTEM

log = logging.getLogger(__name__)

DropReason = Literal["login", "legal", "duplicate", "error_page", "not_content", "other"]


class SectionChoice(BaseModel):
    """One section of the answer: a name and the ids placed in it."""

    model_config = ConfigDict(extra="forbid")
    # Not length-checked here: one bad name must not discard the whole answer. build trims, cuts it to
    # MAX_SECTION_NAME and ignores an empty one.
    name: str
    page_ids: list[int]


class DropChoice(BaseModel):
    """A page the model judged not to be content, with the reason."""

    model_config = ConfigDict(extra="forbid")
    id: int
    reason: DropReason


class Decision(BaseModel):
    """The model's answer, validated; build applies it to the snapshot."""

    model_config = ConfigDict(extra="forbid")
    sections: list[SectionChoice]
    dropped: list[DropChoice]


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    # Strict mode needs every property in "required" and no extra properties.
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


# Hand-written to match Decision: Pydantic's own schema carries keywords (lengths, titles) strict mode
# does not need. Decision still validates the answer, since the schema alone is not trusted.
ANSWER_FORMAT = {
    "type": "json_schema",
    "name": "sitemap_decision",
    "strict": True,
    "schema": _object(
        {
            "sections": {
                "type": "array",
                "items": _object(
                    {"name": {"type": "string"}, "page_ids": {"type": "array", "items": {"type": "integer"}}}
                ),
            },
            "dropped": {
                "type": "array",
                "items": _object(
                    {
                        "id": {"type": "integer"},
                        "reason": {"type": "string", "enum": list(get_args(DropReason))},
                    }
                ),
            },
        }
    ),
}

GET_PAGE_SPEC = {
    "type": "function",
    "name": "get_page",
    "description": "Return the h1 and the links of one already-crawled page, by its id.",
    "parameters": _object({"id": {"type": "integer", "description": "A page id from the list."}}),
    "strict": True,
}


class GetPageArgs(BaseModel):
    """Arguments of get_page."""

    model_config = ConfigDict(extra="forbid")
    id: int


@dataclass
class DecideStats:
    """How the decide step went: which path produced the sections and what it cost."""

    path: Literal["llm", "fallback"] = "fallback"
    reason: str | None = None  # why the fallback ran; None on the llm path
    llm_calls: int = 0
    tool_calls: int = 0
    # Input plus output tokens; None once any request's usage is unknown (no usage, or it failed mid-call).
    tokens: int | None = 0


class NoAnswer(Exception):
    """The model ended without a usable final answer."""


def _path(url: str) -> str:
    return urlsplit(url).path or "/"


def _cell(text: str, limit: int) -> str:
    # Page text goes into a "|"-separated line: no separator or line break may come from the page.
    return " ".join(text.replace("|", "/").split())[:limit]


def snapshot_lines(snapshot: Snapshot, limits: CrawlLimits) -> str:
    """The user message: one line per page, id | path | title | depth | parent_id."""
    lines = ["id | path | title | depth | parent_id"]
    for p in snapshot.pages:
        parent = "-" if p.parent_id is None else str(p.parent_id)
        lines.append(f"{p.id} | {_path(p.url)} | {_cell(p.title, limits.max_title)} | {p.depth} | {parent}")
    return "\n".join(lines)


def get_page(snapshot: Snapshot, page_id: int, limits: CrawlLimits) -> dict[str, Any]:
    """The h1 and links of a snapshot page. Reads only the snapshot: no fetch, no network."""
    by_url = {p.url: p.id for p in snapshot.pages}
    page = next((p for p in snapshot.pages if p.id == page_id), None)
    if page is None:
        return {"ok": False, "error": f"unknown page id {page_id}"}
    shown = page.links[: limits.max_links]
    return {
        "ok": True,
        "id": page.id,
        "h1": _cell(page.h1, limits.max_text),
        # A link's id is set when its target was crawled too, so the model can relate pages by id.
        "links": [
            {
                "path": _path(link.url),
                "text": _cell(link.text, limits.max_text),
                "region": link.region,
                "id": by_url.get(link.url),
            }
            for link in shown
        ],
        "links_not_shown": len(page.links) - len(shown),
    }


def run_tool(snapshot: Snapshot, name: str, arguments: str, limits: CrawlLimits) -> dict[str, Any]:
    """Run one tool call. Never raises: failures go back to the model as {"ok": false}."""
    if name != "get_page":
        return {"ok": False, "error": f"unknown tool {name}"}
    # Tool arguments are untrusted model output: validated before use.
    try:
        args = GetPageArgs.model_validate_json(arguments)
    except ValidationError as exc:
        errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        return {"ok": False, "error": "invalid arguments", "details": errors}
    return get_page(snapshot, args.id, limits)


def _count_tokens(stats: DecideStats, response: Any) -> None:
    usage = getattr(response, "usage", None)
    if usage is None or stats.tokens is None:
        stats.tokens = None
    else:
        stats.tokens += usage.input_tokens + usage.output_tokens


async def _ask(
    client: AsyncOpenAI, model: str, snapshot: Snapshot, limits: CrawlLimits, stats: DecideStats
) -> Decision:
    items: list[Any] = [{"role": "user", "content": snapshot_lines(snapshot, limits)}]
    # Every request with calls spends at least one call of the budget until it is used; after that the
    # tools are switched off, so the model answers within max_tool_calls + 2 requests.
    for _ in range(limits.max_tool_calls + 2):
        tools_left = limits.max_tool_calls - stats.tool_calls
        response = await client.responses.create(
            model=model,
            instructions=SYSTEM,
            input=items,
            tools=[GET_PAGE_SPEC],
            # "none" keeps the tool spec (the history holds tool calls) but forbids new calls.
            tool_choice="auto" if tools_left > 0 else "none",
            text={"format": ANSWER_FORMAT},
        )
        stats.llm_calls += 1
        _count_tokens(stats, response)
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if response.status != "completed":
                raise NoAnswer(f"reply {response.status}")
            # Raises ValidationError on invalid JSON or on a shape Decision rejects.
            return Decision.model_validate_json(response.output_text)
        items += response.output
        # Every call gets an output, as the API needs; calls beyond the cap are refused, not run.
        for call in calls:
            if stats.tool_calls < limits.max_tool_calls:
                stats.tool_calls += 1
                result = run_tool(snapshot, call.name, call.arguments, limits)
            else:
                result = {"ok": False, "error": "tool call limit reached: answer now"}
            items.append(
                {"type": "function_call_output", "call_id": call.call_id, "output": json.dumps(result)}
            )
    raise NoAnswer("no answer within the request limit")


async def decide(
    client: AsyncOpenAI, model: str, snapshot: Snapshot, limits: CrawlLimits
) -> tuple[Decision | None, DecideStats]:
    """Ask the model for sections. Returns (None, stats) on any model failure; never raises for one."""
    stats = DecideStats()
    if not snapshot.pages:
        stats.reason = "no pages extracted"
        return None, stats
    try:
        decision = await asyncio.wait_for(_ask(client, model, snapshot, limits, stats), limits.timeout_s)
    except OpenAIError as exc:
        # The class name only: provider messages can carry request details and stay out of the output.
        stats.reason = f"api_error:{type(exc).__name__}"
        stats.tokens = None  # the failed request may have used tokens nobody reported
    except asyncio.TimeoutError:
        stats.reason = "timeout"
        stats.tokens = None
    except ValidationError:
        stats.reason = "invalid answer"
    except NoAnswer as exc:
        stats.reason = str(exc)
    else:
        stats.path = "llm"
        return decision, stats
    log.warning("decide fell back to URL sections: %s", stats.reason)
    return None, stats
