"""Page loading with Playwright, link candidates, and the deterministic BFS crawl (the agent's fallback)."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from urllib.parse import urljoin

from playwright.async_api import Browser, async_playwright
from playwright.async_api import Error as PlaywrightError

from sitemap.links import is_excluded, normalize, same_host, section_of
from sitemap.models import Link, Page, Region, Sitemap

log = logging.getLogger(__name__)

PAGE_TIMEOUT_MS = 15_000
DELAY_S = 0.3

# Loads one page and returns (title, links). Raises PlaywrightError when the page fails to load.
Fetch = Callable[[str], Awaitable[tuple[str, list[Link]]]]

# Region is the closest nav/header, footer or main ancestor of the anchor.
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
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        title = await page.title()
        raw = await page.evaluate(EXTRACT_LINKS_JS)
        return title, [Link(**item) for item in raw]
    finally:
        await page.close()


@asynccontextmanager
async def browser_fetch() -> AsyncIterator[Fetch]:
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
        target = normalize(urljoin(page_url, link.url))
        if target in seen or target in out or not same_host(target, root) or is_excluded(target):
            continue
        out[target] = link.model_copy(update={"url": target})
    return list(out.values())


async def crawl(
    root: str,
    fetch: Fetch,
    regions: frozenset[Region] = frozenset({"nav", "main", "footer", "other"}),
    max_pages: int = 30,
    max_depth: int = 2,
    delay_s: float = DELAY_S,
) -> Sitemap:
    """BFS that follows every candidate link in `regions`. Sections come from the URL path."""
    root = normalize(root)
    seen = {root}
    queue: deque[tuple[str, int, str | None]] = deque([(root, 0, None)])
    pages: list[Page] = []

    while queue and len(pages) < max_pages:
        url, depth, parent = queue.popleft()
        try:
            title, links = await fetch(url)
        except PlaywrightError as exc:  # includes timeouts; a broken page must not stop the crawl
            log.warning("skip %s: %s", url, type(exc).__name__)
            continue
        pages.append(Page(url=url, title=title, depth=depth, parent=parent, section=section_of(url)))

        if depth < max_depth:
            for link in candidates(url, links, root, seen):
                if link.region in regions:
                    seen.add(link.url)
                    queue.append((link.url, depth + 1, url))
        await asyncio.sleep(delay_s)

    return Sitemap.build(root, pages)
