"""Breadth-first crawl of one site with Playwright."""

import asyncio
import logging
from collections import deque
from urllib.parse import urljoin, urlsplit

from playwright.async_api import Browser, async_playwright
from playwright.async_api import Error as PlaywrightError

from sitemap.links import is_excluded, normalize, same_host
from sitemap.models import Link, Page, Sitemap

log = logging.getLogger(__name__)

PAGE_TIMEOUT_MS = 15_000
DELAY_S = 0.3

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


def section_of(url: str) -> str:
    segments = [s for s in urlsplit(url).path.split("/") if s]
    return segments[0] if segments else "home"


async def _fetch(browser: Browser, url: str) -> tuple[str, list[Link]]:
    page = await browser.new_page()
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
        title = await page.title()
        raw = await page.evaluate(EXTRACT_LINKS_JS)
        return title, [Link(**item) for item in raw]
    finally:
        await page.close()


async def crawl(root: str, max_pages: int = 30, max_depth: int = 2) -> Sitemap:
    root = normalize(root)
    seen = {root}
    queue: deque[tuple[str, int, str | None]] = deque([(root, 0, None)])
    pages: list[Page] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            while queue and len(pages) < max_pages:
                url, depth, parent = queue.popleft()
                try:
                    title, links = await _fetch(browser, url)
                except PlaywrightError as exc:  # includes timeouts; a broken page must not stop the crawl
                    log.warning("skip %s: %s", url, type(exc).__name__)
                    continue
                pages.append(Page(url=url, title=title, depth=depth, parent=parent, section=section_of(url)))

                if depth < max_depth:
                    for link in links:
                        target = normalize(urljoin(url, link.url))
                        if target in seen or not same_host(target, root) or is_excluded(target):
                            continue
                        seen.add(target)
                        queue.append((target, depth + 1, url))
                await asyncio.sleep(DELAY_S)
        finally:
            await browser.close()

    sections: dict[str, list[str]] = {}
    for page in pages:
        sections.setdefault(page.section, []).append(page.url)
    return Sitemap(site=root, pages=pages, sections=sections)
