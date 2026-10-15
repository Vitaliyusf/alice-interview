"""Every bound on a sitemap run, in one frozen value that callers pass in.

Flow: __main__ builds it from the CLI arguments; service, Session, agent and crawl read it.
Design: one frozen object instead of module constants, so a test sets its own limits without
monkeypatching, and nothing can change a limit in the middle of a run.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrawlLimits:
    """Budgets for the agent and the fallback crawl, and caps on what the model is shown."""

    # Room for every top section of a typical docs site plus some of its main child pages.
    max_pages: int = 30
    # Home -> section -> child page: the levels that show a site's structure; deeper pages are detail.
    max_depth: int = 2
    # Safety net: twice the default page budget, so a run of about one visit per turn has room for
    # add/skip turns and refusals, and a model that loops is still stopped.
    max_turns: int = 60
    # Models tend to stop early. Two reminders give it a second chance without pushing forever a
    # model that has a real reason to stop.
    max_nudges: int = 2
    # Wall-clock bound on the agent, so a stuck run ends. The pages already visited are kept. The value
    # is a chosen bound, not a measured run time.
    timeout_s: float = 300.0
    # Links shown per page: a big sidebar must not flood the context. Top-level links are sorted
    # first, so they survive the cut.
    max_links: int = 60
    # Characters of link text shown: enough to recognize a page, and it bounds the untrusted text
    # that reaches the model.
    max_text: int = 80
    # Characters of page title kept: a real title stays whole, a junk one is cut.
    max_title: int = 200
    # Pause after each page load, to be polite to the site.
    delay_s: float = 0.3
