"""Build a sitemap: the agent under a timeout, a deterministic top-up, and the crawl as fallback.

Flow: __main__ calls build_sitemap; it creates the Session, runs agent.run_agent, then top_up, and
calls crawl.crawl only when the agent visited nothing.
Design: a model error or a timeout never ends the run without a sitemap. Each stage degrades to the
next: model judgment first, then code-only recall on what the model left, then a plain crawl.
"""

import asyncio
import logging

from openai import AsyncOpenAI, OpenAIError

from app.sitemap.agent import run_agent
from app.sitemap.crawl import Fetch, crawl
from app.sitemap.limits import CrawlLimits
from app.sitemap.models import Region, Sitemap
from app.sitemap.session import RunStats, Session

log = logging.getLogger(__name__)

# Content lives in nav and main; footer and "other" links are mostly legal, social and ads.
CONTENT_REGIONS: frozenset[Region] = frozenset({"nav", "main"})


async def top_up(session: Session) -> int:
    """Visit the depth 1 nav and main links the model left, until the budget is used. Returns the count."""
    visited = 0
    # Depth 1 only: those are the sections; a missed section costs more than a missed child page.
    for url in session.unvisited(depth=1, regions=CONTENT_REGIONS):
        if len(session.visited) >= session.limits.max_pages:
            break
        # Through visit_page, not a raw fetch: the top-up passes the same guards as the model. Unlike
        # run_tool there is no catch-all: an unexpected fetch error ends the run loudly.
        result = await session.visit_page(url)
        visited += result["ok"]
    return visited


async def build_sitemap(
    root: str, client: AsyncOpenAI, model: str, fetch: Fetch, limits: CrawlLimits
) -> tuple[Sitemap, RunStats]:
    """Return the sitemap of root and how the run went. Never fails on a model error or a timeout."""
    session = Session(root, fetch, limits)
    stats = session.stats
    # Stage 1, the agent: a model error or the timeout ends it, but never the run.
    try:
        stats.status = await asyncio.wait_for(run_agent(client, model, session), limits.timeout_s)
    except OpenAIError as exc:
        # The class name only: provider messages can carry request details and stay out of the output.
        stats.status = f"api_error:{type(exc).__name__}"
    except asyncio.TimeoutError:
        stats.status = "timeout"
    else:
        # Stage 2, the top-up, only when the agent returned (done or turn_limit), not after an error or
        # the timeout. Models stop early even after nudges, and missing real content is the costliest
        # error, so the budget the model left is spent on depth 1 nav and main links it neither visited
        # nor skipped. It runs outside timeout_s; each navigation has its own deadline.
        stats.top_up = await top_up(session)
        log.info("top-up visited=%d", stats.top_up)

    # Pages the agent visited before an error or the timeout are real: they beat a fresh blind crawl.
    if session.visited:
        log.info(
            "path=agent status=%s visited=%d added=%d",
            stats.status,
            len(session.visited),
            len(session.sections),
        )
        return session.sitemap(), stats
    # Stage 3, the fallback: nothing was visited, so a deterministic crawl of nav and main links.
    stats.path = "fallback"
    log.warning(
        "path=fallback agent_status=%s pages=0: deterministic crawl of nav and main links", stats.status
    )
    return await crawl(root, fetch, limits, CONTENT_REGIONS), stats
