"""Extract: a bounded breadth-first crawl with Playwright that records what each page shows. No model.

Flow: __main__ opens browser_fetch() and calls extract(); the Snapshot it returns is written to
out/extracted.json and is the only input of decide and build.
Design: every crawl rule is code: same host, one normalized URL per page, no excluded URLs, each URL
loaded at most once, max_depth, max_pages, a delay after each load. Only nav and main links are followed;
footer and other links are recorded on the page and not followed. Callers pass a Fetch, so tests use a
dict-backed fake and never start a browser.
"""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import NamedTuple
from urllib.parse import urljoin

from playwright.async_api import BrowserContext, async_playwright
from playwright.async_api import Error as PlaywrightError

from app.sitemap.limits import CrawlLimits
from app.sitemap.links import is_excluded, normalize, same_host, top_menu
from app.sitemap.models import ExtractedPage, Link, Region, Snapshot

log = logging.getLogger(__name__)

# Navigation has a deadline: one hanging page must not stall the run.
PAGE_TIMEOUT_MS = 15_000

# Content structure lives in nav and main; footer and "other" links are mostly legal, social and ads.
FOLLOWED: frozenset[Region] = frozenset({"nav", "main"})


class Loaded(NamedTuple):
    """What one page load returns."""

    title: str
    h1: str
    links: list[Link]


# Loads one page. Raises PlaywrightError when the page fails to load.
Fetch = Callable[[str], Awaitable[Loaded]]

# Region: footer when the anchor is anywhere inside a <footer> (so a <footer><nav> legal menu is not
# followed), else its closest nav/header or main ancestor. Computed in the page because the DOM is there;
# a header counts as nav because most sites put their top menu in it.
EXTRACT_JS = """
() => ({
  h1: ((document.querySelector('h1') || {}).innerText || '').trim(),
  links: Array.from(document.querySelectorAll('a[href]')).map(a => {
    const r = a.closest('nav, header, main');
    const tag = r ? r.tagName.toLowerCase() : null;
    const region = a.closest('footer') ? 'footer'
      : tag === 'nav' || tag === 'header' ? 'nav' : tag === 'main' ? 'main' : 'other';
    return {url: a.href, text: (a.innerText || '').trim().slice(0, 200), region};
  }),
})
"""


async def load_page(context: BrowserContext, url: str) -> Loaded:
    """Open url in a new tab of the run's one context and return its title, h1 and every anchor."""
    page = await context.new_page()
    try:
        # domcontentloaded, not networkidle: server-rendered and deferred-script menus are in the DOM by
        # then, and widgets that never go idle cannot hold the load. A menu that an async script renders
        # later is missed: the price of a fast, bounded load.
        await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        title = await page.title()
        raw = await page.evaluate(EXTRACT_JS)
        return Loaded(title, raw["h1"], [Link(**item) for item in raw["links"]])
    finally:
        # Closed even when the load fails, so a long run does not pile up open tabs.
        await page.close()


@asynccontextmanager
async def browser_fetch() -> AsyncIterator[Fetch]:
    """One headless Chromium and one browser context for the whole run, exposed as a Fetch."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            context = await browser.new_context()
            yield lambda url: load_page(context, url)
        finally:
            # Closing the browser closes its context and tabs.
            await browser.close()


def page_links(page_url: str, links: list[Link], root: str) -> list[Link]:
    """Same-host, non-excluded links with normalized URLs, one per URL.

    The first occurrence of a URL wins, except that a later nav or main copy replaces a footer or other
    one: a URL that is also in the menu is followed.
    """
    out: dict[str, Link] = {}
    for link in links:
        try:
            # Relative hrefs resolve against the page they are on, then get the one canonical spelling.
            target = normalize(urljoin(page_url, link.url))
        except ValueError:  # an unparseable href (page text) must not stop the crawl
            continue
        if not same_host(target, root) or is_excluded(target):
            continue
        if target in out and (out[target].region in FOLLOWED or link.region not in FOLLOWED):
            continue
        out[target] = link.model_copy(update={"url": target})
    return list(out.values())


async def extract(root: str, fetch: Fetch, limits: CrawlLimits) -> Snapshot:
    """Breadth-first crawl from root that follows nav and main links, within the limits."""
    root = normalize(root)
    seen = {root}
    # Breadth first: with a page budget, every top section is reached before any deep page.
    queue: deque[tuple[str, int, int | None]] = deque([(root, 0, None)])
    pages: list[ExtractedPage] = []

    while queue and len(pages) < limits.max_pages:
        url, depth, parent_id = queue.popleft()
        try:
            loaded = await fetch(url)
        except PlaywrightError as exc:  # includes timeouts; a broken page must not stop the crawl
            log.warning("skip %s: %s", url, type(exc).__name__)
            continue
        finally:
            # Polite to the site after every load attempt, failed ones too.
            await asyncio.sleep(limits.delay_s)
        links = page_links(url, loaded.links, root)
        # Ids are dense and in load order, so the root (the first load) is id 0.
        page_id = len(pages)
        pages.append(
            ExtractedPage(
                id=page_id,
                url=url,
                title=loaded.title[: limits.max_title],
                h1=loaded.h1[: limits.max_text],
                depth=depth,
                parent_id=parent_id,
                links=links,
            )
        )
        # Links are queued only below max depth; marking them seen on queueing keeps each URL queued once.
        if depth < limits.max_depth:
            if page_id == 0:
                # The home page's top menu goes to the front of the queue (stable sort, menu order kept):
                # big header dropdowns would otherwise fill the budget before the last menu items.
                menu = top_menu(root, links)
                links = sorted(links, key=lambda link: link.url not in menu)
            for link in links:
                if link.region in FOLLOWED and link.url not in seen:
                    seen.add(link.url)
                    queue.append((link.url, depth + 1, page_id))

    return Snapshot(site=root, pages=pages)
