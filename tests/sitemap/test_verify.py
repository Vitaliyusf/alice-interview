"""verify() on hand-made sitemaps: no browser, no network."""

from app.sitemap.models import Link, Page, Sitemap
from app.sitemap.verify import verify

ROOT = "https://site.test"


def page(path, depth, parent, section):
    return Page(
        url=ROOT + path,
        title=path,
        depth=depth,
        parent=None if parent is None else ROOT + parent,
        section=section,
    )


GOOD = [
    page("", 0, None, "home"),
    page("/learn", 1, "", "Learn"),
    page("/learn/basics", 2, "/learn", "Learn"),
]

HOME = [
    Link(url="/learn", text="Learn", region="nav"),
    Link(url="/reference/", text="Reference", region="nav"),
    Link(url="/learn/basics", text="Basics", region="nav"),  # not top level
    Link(url="/blog", text="Blog", region="footer"),  # not in <nav>
    Link(url="/es", text="Español", region="nav"),  # excluded
]


def statuses(pages, home=HOME, max_pages=30, raw=None):
    raw = raw or Sitemap.build(ROOT, pages).model_dump_json()
    return {c.name: (c.status, c.reason) for c in verify(raw, ROOT, max_pages, 2, home)}


def failed(result):
    return {name for name, (status, _) in result.items() if status == "FAIL"}


def test_good_sitemap_passes_every_check_and_reports_missing_top_menu_items():
    result = statuses(GOOD)
    assert failed(result) == set()
    status, reason = result["coverage"]
    assert status == "WARN"
    assert reason == f"1/2 top menu items; missing: Reference ({ROOT}/reference)"


def test_unparsable_file_fails_parse_only():
    assert statuses([], raw='{"site": 1}') == {"parses": ("FAIL", "not a Sitemap: 3 validation errors")}


def test_other_host_duplicate_too_deep_and_excluded_urls_fail():
    bad = [
        *GOOD,
        Page(url="https://evil.test/x", title="x", depth=1, parent=ROOT, section="Learn"),
        page("/learn", 1, "", "Learn"),
        page("/learn/basics/deep", 3, "/learn/basics", "Learn"),
        page("/fr/docs", 1, "", "Learn"),
    ]
    assert failed(statuses(bad)) >= {"same site", "no duplicates", "depth", "no excluded urls", "sections"}


def test_too_many_pages_fails():
    assert failed(statuses(GOOD, max_pages=2)) == {"page count"}


def test_page_whose_parent_is_not_in_the_sitemap_fails():
    result = statuses([GOOD[0], GOOD[2]])
    assert failed(result) == {"parents"}
    assert ROOT + "/learn/basics" in result["parents"][1]


def test_page_listed_under_another_section_fails():
    sitemap = Sitemap.build(ROOT, GOOD)
    sitemap.sections = {"home": [ROOT, ROOT + "/learn"], "Learn": [ROOT + "/learn/basics"]}
    assert failed(statuses(GOOD, raw=sitemap.model_dump_json())) == {"sections"}


def test_coverage_is_a_warning_when_home_page_did_not_load():
    assert statuses(GOOD, home=None)["coverage"] == ("WARN", "home page could not be loaded")
