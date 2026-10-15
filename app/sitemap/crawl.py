"""Page loading with Playwright, link candidates, and the deterministic BFS crawl used as the fallback.

Flow: __main__ opens browser_fetch(); Session.visit_page and crawl() call the Fetch it yields.
Design: a real browser, because many sites build their menus with JavaScript. Callers get a plain Fetch
callable, so tests swap in a dict-backed fake and never start a browser.
"""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urljoin

from playwright.async_api import Browser, async_playwright
from playwright.async_api import Error as PlaywrightError

from app.sitemap.limits import CrawlLimits
from app.sitemap.links import is_excluded, normalize, same_host, section_of
from app.sitemap.models import Link, Page, Region, Sitemap

log = logging.getLogger(__name__)

# Navigation has a deadline: one hanging page must not stall the run.
PAGE_TIMEOUT_MS = 15_000

# Loads one page and returns (title, links). Raises PlaywrightError when the page fails to load.
Fetch = Callable[[str], Awaitable[tuple[str, list[Link]]]]

# Region is the closest nav/header, footer or main ancestor of the anchor. Computed in the page because
# the DOM is there; a header counts as nav because most sites put their top menu in it.
EXTRACT_LINKS_JS = """
() => Array.from(document.querySelectorAll('a[href]')).map(a => {
  const r = a.closest('nav, header, footer, main');
  const tag = r ? r.tagName.toLowerCase() : null;
  const region = tag === 'nav' || tag === 'header' ? 'nav'
    : tag === 'footer' ? 'footer' : tag === 'main' ? 'main' : 'other';
  return {url: a.href, text: (a.innerText || '').trim().slice(0, 200), region};
})
"""


async def load_page(browser: Browser, url: str) -> tuple[str, list[Link]]:
    """Open url in a new tab and return its title and every anchor on it."""
    # A fresh tab per page: no state leaks from one page to the next.
    page = await browser.new_page()
    try:
        # domcontentloaded, not networkidle: server-rendered and deferred-script menus are in the DOM by
        # then, and widgets that never go idle cannot hold the load. A menu that an async script renders
        # later is missed: the price of a fast, bounded load.
        await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        title = await page.title()
        raw = await page.evaluate(EXTRACT_LINKS_JS)
        return title, [Link(**item) for item in raw]
    finally:
        # Closed even when the load fails, so a long run does not pile up open tabs.
        await page.close()


@asynccontextmanager
async def browser_fetch() -> AsyncIterator[Fetch]:
    """One headless Chromium for the whole run, exposed as a Fetch; closed on exit."""
    # One browser, many tabs: starting Chromium per page would cost more than loading the page.
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            yield lambda url: load_page(browser, url)
        finally:
            await browser.close()


def candidates(page_url: str, links: list[Link], root: str, seen: set[str]) -> list[Link]:
    """Unseen, same-host, non-excluded links with normalized URLs; the first occurrence of a URL wins."""
    out: dict[str, Link] = {}
    for link in links:
        # Relative hrefs resolve against the page they are on, then get the one canonical spelling.
        target = normalize(urljoin(page_url, link.url))
        # Guards 1-3 of visit_page, applied early so the model is not shown links that can never be
        # visited. Shown links can still be refused by the other guards (depth, top first, cap, budget).
        if target in seen or target in out or not same_host(target, root) or is_excluded(target):
            continue
        # First occurrence wins: its region and text are where the link appears first on the page.
        out[target] = link.model_copy(update={"url": target})
    return list(out.values())


async def crawl(
    root: str,
    fetch: Fetch,
    limits: CrawlLimits,
    regions: frozenset[Region] = frozenset({"nav", "main", "footer", "other"}),
) -> Sitemap:
    """BFS that follows every candidate link in `regions`. Sections come from the URL path."""
    # The fallback when the agent produced nothing: no model, so no judgment, only rules and the budget.
    root = normalize(root)
    seen = {root}
    # Breadth first: with a page budget, every top section is reached before any deep page.
    queue: deque[tuple[str, int, str | None]] = deque([(root, 0, None)])
    pages: list[Page] = []

    while queue and len(pages) < limits.max_pages:
        url, depth, parent = queue.popleft()
        try:
            title, links = await fetch(url)
        except PlaywrightError as exc:  # includes timeouts; a broken page must not stop the crawl
            log.warning("skip %s: %s", url, type(exc).__name__)
            continue
        pages.append(Page(url=url, title=title, depth=depth, parent=parent, section=section_of(url)))

        # Links are queued only below max depth; marking them seen on queueing keeps each URL queued once.
        if depth < limits.max_depth:
            for link in candidates(url, links, root, seen):
                if link.region in regions:
                    seen.add(link.url)
                    queue.append((link.url, depth + 1, url))
        await asyncio.sleep(limits.delay_s)

    return Sitemap.build(root, pages)
