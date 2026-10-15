"""What one agent run has seen and recorded, and the guardrails every tool call goes through."""

import asyncio
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError

from app.sitemap.crawl import Fetch, candidates
from app.sitemap.limits import CrawlLimits
from app.sitemap.links import is_excluded, normalize, same_host, section_of, top_menu
from app.sitemap.models import Page, Sitemap

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    """How a run went: which path produced the sitemap, why the agent stopped, and what it asked for."""

    path: Literal["agent", "fallback"] = "agent"
    status: str = "not_started"
    turns: int = 0
    tool_calls: Counter[str] = field(default_factory=Counter)
    refused: Counter[str] = field(default_factory=Counter)  # "tool: reason" -> count


def _section_key(section: str) -> str:
    return section.strip().lower()


def _is_under(url: str, prefix: str) -> bool:
    path, base = urlsplit(url).path, urlsplit(prefix).path
    return bool(base) and path.startswith(base + "/")


class Session:
    """What the agent has seen and recorded. Depth and parent come from the first page that listed a URL.

    The model never fetches: every page-level limit is enforced here, in code. Refusals are returned as
    {"ok": false, "reason": ...}, never raised, so the model can read them and choose again.
    """

    def __init__(self, root: str, fetch: Fetch, limits: CrawlLimits) -> None:
        self.root = normalize(root)
        self.fetch = fetch
        self.limits = limits
        self.listed: dict[str, tuple[int, str | None]] = {self.root: (0, None)}
        self.visited: dict[str, tuple[str, int, str | None]] = {}  # url -> (title, depth, parent)
        self.attempted: set[str] = set()
        self.sections: dict[str, str] = {}  # url -> section, in the order the model added them
        self.stats = RunStats()
        # Breadth first: the home page's top-level links, each visited or skipped before going deeper.
        self.top: dict[str, str] = {}
        self.skipped: set[str] = set()
        # Per-section cap, so one large section cannot eat the whole budget.
        self.section_cap = max(3, limits.max_pages // 5)
        self.predicted: dict[str, str | None] = {}  # visited url -> section guessed at visit time

    def pending(self) -> list[str]:
        """Listed URLs the model could still visit."""
        return [
            u for u, (d, _) in self.listed.items() if u not in self.attempted and d <= self.limits.max_depth
        ]

    def top_pending(self) -> list[str]:
        """Top-level links that are neither visited nor skipped yet."""
        return [u for u in self.top if u not in self.attempted and u not in self.skipped]

    def section_for(self, url: str, parent: str | None) -> str | None:
        """Section key a URL will most likely land in: its parent's, else that of the deepest added page
        whose path contains it. None for a page that may start a new section."""
        if parent and parent != self.root and parent in self.sections:
            return _section_key(self.sections[parent])
        owners = [u for u in self.sections if u != self.root and _is_under(url, u)]
        if owners:
            return _section_key(self.sections[max(owners, key=len)])
        return None

    def section_count(self, key: str) -> int:
        """Visited pages in a section: added under it, or guessed into it and not added elsewhere."""
        return sum(
            1
            for u in self.visited
            if (_section_key(self.sections[u]) if u in self.sections else self.predicted.get(u)) == key
        )

    def sitemap(self) -> Sitemap:
        """The sitemap of the recorded pages."""
        # Keep visited pages even without add_page: missing content costs more than noise.
        sections = self.sections or {url: section_of(url) for url in self.visited}
        pages = []
        for url, section in sections.items():
            title, depth, parent = self.visited[url]
            pages.append(Page(url=url, title=title, depth=depth, parent=parent, section=section))
        return Sitemap.build(self.root, pages)

    async def visit_page(self, raw_url: str) -> dict[str, Any]:
        """Load a page if every guardrail allows it, and list its candidate links."""
        limits = self.limits
        url = normalize(raw_url)
        if not same_host(url, self.root):
            return {"ok": False, "reason": "outside the site"}
        if is_excluded(url):
            return {"ok": False, "reason": "excluded url"}
        if url in self.attempted:
            return {"ok": False, "reason": "already visited"}
        if url not in self.listed:
            return {"ok": False, "reason": "not linked from a visited page"}
        depth, parent = self.listed[url]
        if depth > limits.max_depth:
            return {"ok": False, "reason": f"deeper than max depth {limits.max_depth}"}
        if url != self.root and url not in self.top and (left := self.top_pending()):
            return {"ok": False, "reason": "cover top sections first", "visit_or_skip": left}
        section = self.section_for(url, parent)
        if section is not None and self.section_count(section) >= self.section_cap:
            return {"ok": False, "reason": "section budget used", "section": section, "cap": self.section_cap}
        if len(self.visited) >= limits.max_pages:
            return {"ok": False, "reason": f"page budget of {limits.max_pages} used"}

        self.attempted.add(url)
        try:
            title, links = await self.fetch(url)
        except PlaywrightError as exc:
            log.warning("load failed %s: %s", url, type(exc).__name__)
            return {"ok": False, "reason": "page failed to load"}
        finally:
            await asyncio.sleep(limits.delay_s)
        # Page text is untrusted: titles and link texts are capped before the model sees them.
        self.visited[url] = (title[: limits.max_title], depth, parent)
        self.predicted[url] = section
        if url == self.root:
            self.top = top_menu(self.root, links)

        found = candidates(url, links, self.root, self.attempted)
        # Every candidate is listed (it can be visited later); only max_links are shown, top-level ones
        # first: on a big sidebar the top sections sit far down the page and would be cut off.
        for link in found:
            self.listed.setdefault(link.url, (depth + 1, url))
        shown = sorted(found, key=lambda lnk: lnk.url not in self.top)[: limits.max_links]
        return {
            "ok": True,
            "url": url,
            "title": title[: limits.max_title],
            "depth": depth,
            "pages_left": limits.max_pages - len(self.visited),
            "top_sections_left": len(self.top_pending()),
            "links": [
                {
                    "url": lnk.url,
                    "text": lnk.text[: limits.max_text],
                    "region": lnk.region,
                    "top": lnk.url in self.top,
                }
                for lnk in shown
            ],
            "links_not_shown": len(found) - len(shown),
        }

    def add_page(self, raw_url: str, section: str) -> dict[str, Any]:
        """Record a visited page under a section, unless that section is full."""
        url = normalize(raw_url)
        if url not in self.visited:
            return {"ok": False, "reason": "not visited: call visit_page first"}
        key = _section_key(section)
        members = sum(1 for u, s in self.sections.items() if u != url and _section_key(s) == key)
        if members >= self.section_cap:
            return {"ok": False, "reason": "section budget used", "section": key, "cap": self.section_cap}
        self.sections[url] = section.strip()
        return {"ok": True}

    def skip_pages(self, raw_urls: list[str]) -> dict[str, Any]:
        """Mark top-level links as not content, so they stop blocking deeper visits."""
        urls = {normalize(u) for u in raw_urls}
        skipped = urls & self.top.keys()
        self.skipped |= skipped
        return {
            "ok": True,
            "skipped": len(skipped),
            "not_top_level": sorted(urls - skipped),
            "top_sections_left": self.top_pending(),
        }
