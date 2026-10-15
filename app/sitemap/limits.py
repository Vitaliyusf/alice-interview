"""Every bound on a sitemap run, in one frozen value that callers pass in.

Flow: __main__ builds it from the CLI arguments; extract and decide read it.
Design: one frozen object instead of module constants, so a test sets its own limits without
monkeypatching, and nothing can change a limit in the middle of a run.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlLimits:
    """Budgets for the crawl and the model step, and caps on the page text the model is shown."""

    # Room for every top section of a typical docs site plus some of its main child pages.
    max_pages: int = 30
    # Home -> section -> child page: the levels that show a site's structure; deeper pages are detail.
    max_depth: int = 2
    # get_page calls the model may make before it must answer. Most pages are clear from path and title;
    # the tool is for the few that are not.
    max_tool_calls: int = 10
    # Wall-clock bound on the whole model step; on expiry the URL-based fallback runs. A chosen bound,
    # not a measured run time.
    timeout_s: float = 120.0
    # Links get_page returns per page: a big sidebar must not flood the context.
    max_links: int = 60
    # Characters of link text and h1 shown to the model: enough to recognize a page, and it bounds the
    # untrusted text that reaches the model.
    max_text: int = 80
    # Characters of page title kept: a real title stays whole, a junk one is cut.
    max_title: int = 200
    # Pause after each page load, to be polite to the site.
    delay_s: float = 0.3
