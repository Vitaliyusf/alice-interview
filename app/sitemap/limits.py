"""Every bound on a sitemap run, in one value that callers pass in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlLimits:
    """Budgets for the agent and the fallback crawl, and caps on what the model is shown."""

    max_pages: int = 30
    max_depth: int = 2
    max_turns: int = 60
    max_nudges: int = 2  # times the loop asks a model that stopped early to go on
    timeout_s: float = 300.0
    max_links: int = 60  # links shown per visited page
    max_text: int = 80  # characters of link text shown
    max_title: int = 200  # characters of page title kept
    delay_s: float = 0.3  # pause after each page load, to be polite to the site
