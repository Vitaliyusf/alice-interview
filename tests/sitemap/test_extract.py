"""extract() with a dict-backed fake browser: no Playwright, no network."""

import asyncio

from playwright.async_api import Error as PlaywrightError

from app.sitemap.extract import Loaded, extract, page_links
from app.sitemap.limits import CrawlLimits
from app.sitemap.models import Link

ROOT = "https://site.test"

SITE = {
    ROOT: [
        Link(url="/learn/", text="Learn", region="nav"),
        Link(url="/reference#top", text="Reference", region="main"),
        Link(url="/privacy", text="Privacy", region="footer"),
        Link(url="/sidebar", text="Side", region="other"),
        Link(url="/login", text="Log in", region="nav"),
        Link(url="/brochure.pdf", text="PDF", region="main"),
        Link(url="https://evil.test/x", text="Elsewhere", region="main"),
        Link(url="/learn?ref=main", text="Learn again", region="main"),
    ],
    f"{ROOT}/learn": [Link(url="/learn/basics", text="Basics", region="main")],
    f"{ROOT}/reference": [],
    f"{ROOT}/learn/basics": [Link(url="/learn/basics/deep", text="Deep", region="main")],
    f"{ROOT}/learn/basics/deep": [],
    f"{ROOT}/privacy": [],
    f"{ROOT}/sidebar": [],
}


class FakeBrowser:
    """Serves SITE and records every URL it was asked to load."""

    def __init__(self, broken: set[str] = frozenset()) -> None:
        self.fetched: list[str] = []
        self.broken = broken

    async def __call__(self, url: str) -> Loaded:
        self.fetched.append(url)
        if url in self.broken:
            raise PlaywrightError("net::ERR_FAILED")
        return Loaded(f"title {url}", f"h1 {url}", SITE[url])


def run(browser: FakeBrowser, **limits: object):
    return asyncio.run(extract(ROOT + "/", browser, CrawlLimits(delay_s=0, **limits)))


def test_follows_nav_and_main_only_and_records_footer_links():
    browser = FakeBrowser()

    snapshot = run(browser, max_depth=1)

    assert browser.fetched == [ROOT, f"{ROOT}/learn", f"{ROOT}/reference"]
    # Footer and other links are on the root's record, normalized, but were never loaded.
    root_links = {(link.url, link.region) for link in snapshot.pages[0].links}
    assert (f"{ROOT}/privacy", "footer") in root_links
    assert (f"{ROOT}/sidebar", "other") in root_links


def test_never_loads_excluded_or_other_host_urls_and_loads_each_url_once():
    browser = FakeBrowser()

    snapshot = run(browser)

    assert len(browser.fetched) == len(set(browser.fetched))
    assert not {f"{ROOT}/login", f"{ROOT}/brochure.pdf", "https://evil.test/x"} & set(browser.fetched)
    # Excluded and other-host links are not even recorded: they are never content of this site.
    recorded = {link.url for p in snapshot.pages for link in p.links}
    assert not {f"{ROOT}/login", f"{ROOT}/brochure.pdf", "https://evil.test/x"} & recorded


def test_respects_max_depth_and_records_depth_and_parent_ids():
    browser = FakeBrowser()

    snapshot = run(browser, max_depth=2)

    assert f"{ROOT}/learn/basics/deep" not in browser.fetched
    assert [(p.id, p.url, p.depth, p.parent_id) for p in snapshot.pages] == [
        (0, ROOT, 0, None),
        (1, f"{ROOT}/learn", 1, 0),
        (2, f"{ROOT}/reference", 1, 0),
        (3, f"{ROOT}/learn/basics", 2, 1),
    ]
    assert snapshot.pages[1].h1 == f"h1 {ROOT}/learn"


def test_stops_at_the_page_budget():
    browser = FakeBrowser()

    snapshot = run(browser, max_pages=2)

    assert [p.url for p in snapshot.pages] == [ROOT, f"{ROOT}/learn"]
    assert browser.fetched == [ROOT, f"{ROOT}/learn"]


def test_a_url_also_in_the_menu_is_followed_even_when_first_seen_outside_it():
    links = [
        Link(url="/a", text="Logo", region="other"),
        Link(url="/a", text="A", region="nav"),
        Link(url="/a", text="A again", region="footer"),
    ]

    assert page_links(ROOT, links, ROOT) == [Link(url=f"{ROOT}/a", text="A", region="nav")]


def test_an_unparseable_href_is_skipped_not_fatal():
    links = [Link(url="http://[bad", text="x", region="main"), Link(url="/fine", text="fine", region="main")]

    assert [link.url for link in page_links(ROOT, links, ROOT)] == [f"{ROOT}/fine"]


def test_a_page_that_fails_to_load_is_skipped_and_not_counted():
    browser = FakeBrowser(broken={f"{ROOT}/learn"})

    snapshot = run(browser, max_pages=2)

    assert [p.url for p in snapshot.pages] == [ROOT, f"{ROOT}/reference"]
    assert [p.id for p in snapshot.pages] == [0, 1]


def test_home_top_menu_is_crawled_before_dropdown_links():
    # A header dropdown lists deep links before the top-level menu items, as on python.org.
    site = {
        ROOT: [
            Link(url="/a/one", text="A one", region="nav"),
            Link(url="/a/two", text="A two", region="nav"),
            Link(url="/a", text="A", region="nav"),
            Link(url="/b", text="B", region="nav"),
        ],
    }

    async def fetch(url: str) -> Loaded:
        return Loaded(url, "", site.get(url, []))

    snapshot = asyncio.run(extract(ROOT, fetch, CrawlLimits(max_pages=3, delay_s=0)))

    assert [p.url for p in snapshot.pages] == [ROOT, f"{ROOT}/a", f"{ROOT}/b"]
