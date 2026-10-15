"""The tools the model may call: their specs, argument models, and the dispatch to the session."""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.sitemap.session import Session

log = logging.getLogger(__name__)


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


TOOL_SPECS = [
    _tool(
        "visit_page",
        "Load a page of the site. Returns its title and up to 60 candidate links, or ok=false with a reason.",
        {
            "url": {
                "type": "string",
                "description": "Absolute URL from a previous visit_page result, or the root.",
            }
        },
    ),
    _tool(
        "add_page",
        "Record a visited page in the sitemap under a short section name.",
        {"url": {"type": "string"}, "section": {"type": "string", "description": "Short section name."}},
    ),
    _tool(
        "skip_pages",
        "Mark top-level links as not content, so they no longer block deeper pages.",
        {"urls": {"type": "array", "items": {"type": "string"}}},
    ),
]


class VisitArgs(BaseModel):
    """Arguments of visit_page."""

    model_config = ConfigDict(extra="forbid")
    url: str


class AddArgs(BaseModel):
    """Arguments of add_page."""

    model_config = ConfigDict(extra="forbid")
    url: str
    section: str = Field(min_length=1, max_length=60)


class SkipArgs(BaseModel):
    """Arguments of skip_pages."""

    model_config = ConfigDict(extra="forbid")
    urls: list[str] = Field(max_length=200)


async def run_tool(session: Session, name: str, arguments: str) -> dict[str, Any]:
    """Run one tool call and count it. Never raises: failures go back to the model as {"ok": false}."""
    session.stats.tool_calls[name] += 1
    result = await _dispatch(session, name, arguments)
    if not result["ok"]:
        session.stats.refused[f"{name}: {result.get('reason') or result.get('error')}"] += 1
    return result


async def _dispatch(session: Session, name: str, arguments: str) -> dict[str, Any]:
    # Tool arguments are untrusted model output: validated here before the session sees them.
    try:
        if name == "visit_page":
            visit = VisitArgs.model_validate_json(arguments)
            return await session.visit_page(visit.url)
        if name == "add_page":
            add = AddArgs.model_validate_json(arguments)
            return session.add_page(add.url, add.section)
        if name == "skip_pages":
            skip = SkipArgs.model_validate_json(arguments)
            return session.skip_pages(skip.urls)
        return {"ok": False, "error": f"unknown tool {name}"}
    except ValidationError as exc:
        errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        return {"ok": False, "error": "invalid arguments", "details": errors}
    except Exception:  # a tool must never take down the loop; details stay in the log
        log.exception("tool %s crashed", name)
        return {"ok": False, "error": "internal error"}
