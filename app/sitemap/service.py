"""Build a sitemap: the agent under a timeout, and the deterministic crawl when it produced nothing."""

import asyncio
import logging

from openai import AsyncOpenAI, OpenAIError

from app.sitemap.agent import run_agent
from app.sitemap.crawl import Fetch, crawl
from app.sitemap.limits import CrawlLimits
from app.sitemap.models import Sitemap
from app.sitemap.session import RunStats, Session

log = logging.getLogger(__name__)


async def build_sitemap(
    root: str, client: AsyncOpenAI, model: str, fetch: Fetch, limits: CrawlLimits
) -> tuple[Sitemap, RunStats]:
    """Return the sitemap of root and how the run went. Never fails on a model error or a timeout."""
    session = Session(root, fetch, limits)
    stats = session.stats
    try:
        stats.status = await asyncio.wait_for(run_agent(client, model, session), limits.timeout_s)
    except OpenAIError as exc:
        stats.status = f"api_error:{type(exc).__name__}"
    except asyncio.TimeoutError:
        stats.status = "timeout"

    # Pages the agent visited before an error or the timeout are real: they beat a fresh blind crawl.
    if session.visited:
        log.info(
            "path=agent status=%s visited=%d added=%d",
            stats.status,
            len(session.visited),
            len(session.sections),
        )
        return session.sitemap(), stats
    stats.path = "fallback"
    log.warning(
        "path=fallback agent_status=%s pages=0: deterministic crawl of nav and main links", stats.status
    )
    return await crawl(root, fetch, limits, frozenset({"nav", "main"})), stats
