"""What one agent run has seen and recorded, and the guardrails every tool call goes through.

Flow: service creates one Session per run; tools.run_tool and service.top_up call its methods; it calls
the Fetch from crawl and the URL rules from links, and builds the final Sitemap.
Design: all state and every page-level rule live here, in code, behind three methods. The model can only
ask; a refusal comes back as data it can read, so a wrong call costs a turn and cannot break a limit.
"""

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
from app.sitemap.models import Page, Region, Sitemap

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    """How a run went: which path produced the sitemap, why the agent stopped, and what it asked for."""

    path: Literal["agent", "fallback"] = "agent"
    status: str = "not_started"
    turns: int = 0
    tool_calls: Counter[str] = field(default_factory=Counter)
    refused: Counter[str] = field(default_factory=Counter)  # "tool: reason" -> count
    top_up: int | None = None  # pages the deterministic top-up visited; None when it did not run


def _section_key(section: str) -> str:
    # One spelling per section: "Learn", "learn " and "LEARN" are the same section.
    return section.strip().lower()


def _is_under(url: str, prefix: str) -> bool:
    # Path prefix on a segment boundary: /docs/a is under /docs, /docs-old is not.
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
        # Only listed URLs can be visited; the root is listed from the start.
        self.listed: dict[str, tuple[int, str | None]] = {self.root: (0, None)}
        self.regions: dict[str, Region] = {}  # listed url -> region of the link that first listed it
        self.visited: dict[str, tuple[str, int, str | None]] = {}  # url -> (title, depth, parent)
        # Every URL whose load was started, failed ones too: a failed page is not retried.
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

    def unvisited(self, depth: int, regions: frozenset[Region]) -> list[str]:
        """Listed URLs at depth, first linked from one of regions or top-level, neither attempted nor skipped.

        Listing order, with top-level links first: visit_page refuses other pages until those are covered.
        """
        # Top-level links count whatever region they were first listed from: one left out would block
        # every other visit through the "cover top sections first" guard.
        urls = [
            u
            for u, (d, _) in self.listed.items()
            if d == depth
            and u not in self.attempted
            and u not in self.skipped
            and (u in self.top or self.regions.get(u) in regions)
        ]
        return sorted(urls, key=lambda u: u not in self.top)

    def section_for(self, url: str, parent: str | None) -> str | None:
        """Section key a URL will most likely land in: its parent's, else that of the deepest added page
        whose path contains it. None for a page that may start a new section."""
        # The cap is checked before the load, when the model has not named the page yet: so we guess.
        if parent and parent != self.root and parent in self.sections:
            return _section_key(self.sections[parent])
        owners = [u for u in self.sections if u != self.root and _is_under(url, u)]
        if owners:
            return _section_key(self.sections[max(owners, key=len)])
        return None

    def section_count(self, key: str) -> int:
        """Visited pages in a section: added under it, or guessed into it and not added elsewhere."""
        # Counts visits, not only adds: otherwise a model could fill a section by never calling add_page.
        return sum(
            1
            for u in self.visited
            if (_section_key(self.sections[u]) if u in self.sections else self.predicted.get(u)) == key
        )

    def sitemap(self) -> Sitemap:
        """Every visited page, in visit order, under the model's section or else the one from its URL."""
        pages = []
        # Keep visited pages even without add_page: missing content costs more than noise.
        for url, (title, depth, parent) in self.visited.items():
            # The model's name when it gave one: grouping is its judgment. Else the first path segment.
            section = self.sections[url] if url in self.sections else section_of(url)
            # One key per section, so "Learn" from the model and "learn" from the URL are one section.
            pages.append(
                Page(url=url, title=title, depth=depth, parent=parent, section=_section_key(section))
            )
        return Sitemap.build(self.root, pages)

    async def visit_page(self, raw_url: str) -> dict[str, Any]:
        """Load a page if every guardrail allows it, and list its candidate links."""
        limits = self.limits
        url = normalize(raw_url)
        # 1. Same site only: the model cannot send the crawler to another host.
        if not same_host(url, self.root):
            return {"ok": False, "reason": "outside the site"}
        # 2. No files, auth, language copies, tags or pagination: not content, and some have side effects.
        if is_excluded(url):
            return {"ok": False, "reason": "excluded url"}
        # 3. Each URL loads once, failed ones too: repeats cannot burn the budget.
        if url in self.attempted:
            return {"ok": False, "reason": "already visited"}
        # 4. Only URLs linked from a visited page: the model cannot invent URLs, and text in a page
        #    cannot add a URL that is not a real link on it.
        if url not in self.listed:
            return {"ok": False, "reason": "not linked from a visited page"}
        depth, parent = self.listed[url]
        # 5. Depth comes from the link graph, not from the model: no page deeper than max_depth.
        if depth > limits.max_depth:
            return {"ok": False, "reason": f"deeper than max depth {limits.max_depth}"}
        # 6. Breadth first: every top section is visited or skipped before any other page, so the budget
        #    covers all sections instead of going deep into the first one.
        if url != self.root and url not in self.top and (left := self.top_pending()):
            return {"ok": False, "reason": "cover top sections first", "visit_or_skip": left}
        # 7. Section cap, so one large section does not eat the budget meant for the others. It only
        #    applies when the section can be guessed from pages the model added (section_for); a page
        #    with no added owner is not capped, and the written sitemap can exceed the cap.
        section = self.section_for(url, parent)
        if section is not None and self.section_count(section) >= self.section_cap:
            return {"ok": False, "reason": "section budget used", "section": section, "cap": self.section_cap}
        # 8. Page budget: at most max_pages pages are recorded. Failed loads do not count.
        if len(self.visited) >= limits.max_pages:
            return {"ok": False, "reason": f"page budget of {limits.max_pages} used"}

        # Marked before the load, so a page that fails is not retried by a later call.
        self.attempted.add(url)
        try:
            title, links = await self.fetch(url)
        except PlaywrightError as exc:
            # A broken page is the site's problem, not the run's: the model is told and moves on.
            log.warning("load failed %s: %s", url, type(exc).__name__)
            return {"ok": False, "reason": "page failed to load"}
        finally:
            # Polite to the site after every load attempt, failed ones too.
            await asyncio.sleep(limits.delay_s)
        # Page text is untrusted: titles and link texts are capped before the model sees them.
        self.visited[url] = (title[: limits.max_title], depth, parent)
        self.predicted[url] = section
        # The home page defines the top sections that guard 6 waits for.
        if url == self.root:
            self.top = top_menu(self.root, links)

        found = candidates(url, links, self.root, self.attempted)
        # Every candidate is listed (it can be visited later); only max_links are shown, top-level ones
        # first: on a big sidebar the top sections sit far down the page and would be cut off.
        for link in found:
            # The first page that lists a URL fixes its depth, parent and region.
            if link.url not in self.listed:
                self.listed[link.url] = (depth + 1, url)
                self.regions[link.url] = link.region
        shown = sorted(found, key=lambda lnk: lnk.url not in self.top)[: limits.max_links]
        # pages_left and top_sections_left let the model plan without counting for itself.
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
        # Only pages the code loaded: the model cannot add a page it never saw, or invent a title.
        if url not in self.visited:
            return {"ok": False, "reason": "not visited: call visit_page first"}
        # The cap again, on the name the model chose: renaming a page into a full section is refused.
        # The page itself (u != url) does not count, so re-adding a page can move it between sections.
        key = _section_key(section)
        members = sum(1 for u, s in self.sections.items() if u != url and _section_key(s) == key)
        if members >= self.section_cap:
            return {"ok": False, "reason": "section budget used", "section": key, "cap": self.section_cap}
        self.sections[url] = section.strip()
        return {"ok": True}

    def skip_pages(self, raw_urls: list[str]) -> dict[str, Any]:
        """Mark top-level links as not content, so they stop blocking deeper visits."""
        # Only top-level links can be skipped. A skip releases guard 6, and the top-up leaves the link alone.
        urls = {normalize(u) for u in raw_urls}
        skipped = urls & self.top.keys()
        self.skipped |= skipped
        # The model learns which URLs did not count and what still blocks deeper visits.
        return {
            "ok": True,
            "skipped": len(skipped),
            "not_top_level": sorted(urls - skipped),
            "top_sections_left": self.top_pending(),
        }
