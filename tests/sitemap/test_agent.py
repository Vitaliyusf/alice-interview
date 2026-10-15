"""The sitemap agent with a scripted fake model and a fake site: no browser, no network."""

import asyncio
import json

from openai import APIConnectionError

from app.sitemap.crawl import crawl
from app.sitemap.limits import CrawlLimits
from app.sitemap.models import Link
from app.sitemap.service import build_sitemap
from tests.conftest import REQUEST

ROOT = "https://site.test"

SITE = {
    ROOT: [
        Link(url="/learn", text="Learn", region="nav"),
        Link(url="/reference", text="Reference", region="main"),
        Link(url="/privacy", text="Privacy", region="footer"),
        Link(url="https://evil.test/x", text="Elsewhere", region="main"),
    ],
    f"{ROOT}/learn": [Link(url="/learn/basics", text="Basics", region="main")],
    f"{ROOT}/reference": [],
    f"{ROOT}/privacy": [],
    f"{ROOT}/learn/basics": [],
}


async def fake_fetch(url):
    return f"title {url}", SITE[url]


def run_with_stats(fake_openai, max_pages=30, fetch=fake_fetch, max_nudges=0):
    # No nudges by default: scripts below end with a plain answer; the nudge has its own test.
    limits = CrawlLimits(max_pages=max_pages, max_nudges=max_nudges, delay_s=0)
    return asyncio.run(build_sitemap(ROOT, fake_openai, "m", fetch, limits))


def run(fake_openai, max_pages=30, fetch=fake_fetch, max_nudges=0):
    return run_with_stats(fake_openai, max_pages, fetch, max_nudges)[0]


def tool_outputs(request):
    return [
        json.loads(item["output"]) for item in request["input"] if isinstance(item, dict) and "output" in item
    ]


def test_agent_records_added_pages_with_depth_parent_and_section(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT + "/"}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_call(
        ("add_page", {"url": ROOT, "section": "home"}),
        ("add_page", {"url": f"{ROOT}/learn", "section": "Learn"}),
    )
    fake_openai.will_say("done")

    sitemap = run(fake_openai)

    assert [(p.url, p.depth, p.parent, p.section) for p in sitemap.pages] == [
        (ROOT, 0, None, "home"),
        (f"{ROOT}/learn", 1, ROOT, "learn"),  # the model's "Learn", one key per section
        (f"{ROOT}/reference", 1, ROOT, "reference"),  # by the top-up
    ]
    assert sitemap.sections == {
        "home": [ROOT],
        "learn": [f"{ROOT}/learn"],
        "reference": [f"{ROOT}/reference"],
    }
    root_visit = tool_outputs(fake_openai.requests[1])[0]
    assert [link["url"] for link in root_visit["links"]] == [
        f"{ROOT}/learn",
        f"{ROOT}/reference",
        f"{ROOT}/privacy",
    ]
    assert "tools" in fake_openai.requests[0]


def test_visit_outside_the_site_is_refused_and_not_fetched(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": "https://evil.test/x"}))
    fake_openai.will_call(("add_page", {"url": ROOT, "section": "home"}))
    fake_openai.will_say("done")

    run(fake_openai)

    assert tool_outputs(fake_openai.requests[2])[-1] == {"ok": False, "reason": "outside the site"}


def test_visit_over_the_page_budget_is_refused(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_call(("add_page", {"url": ROOT, "section": "home"}))
    fake_openai.will_say("done")

    sitemap = run(fake_openai, max_pages=1)

    assert tool_outputs(fake_openai.requests[2])[-1] == {"ok": False, "reason": "page budget of 1 used"}
    assert [p.url for p in sitemap.pages] == [ROOT]


def test_add_page_of_an_unvisited_url_is_refused(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("add_page", {"url": f"{ROOT}/reference", "section": "Reference"}))
    fake_openai.will_call(("add_page", {"url": ROOT, "section": "home"}))
    fake_openai.will_say("done")

    sitemap = run(fake_openai)

    assert tool_outputs(fake_openai.requests[2])[-1] == {
        "ok": False,
        "reason": "not visited: call visit_page first",
    }
    assert [p.url for p in sitemap.pages] == [ROOT, f"{ROOT}/learn", f"{ROOT}/reference"]  # top-up


def test_visit_of_an_unlisted_url_is_refused(fake_openai):
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn/basics"}))
    fake_openai.will_raise(APIConnectionError(request=REQUEST))  # ends the run; the fallback follows

    run(fake_openai)

    assert tool_outputs(fake_openai.requests[1])[-1] == {
        "ok": False,
        "reason": "not linked from a visited page",
    }


def test_visited_pages_are_kept_by_url_section_when_the_agent_never_adds(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_say("done")

    sitemap, stats = run_with_stats(fake_openai)

    assert stats.path == "agent"
    assert [(p.url, p.section) for p in sitemap.pages] == [
        (ROOT, "home"),
        (f"{ROOT}/learn", "learn"),
        (f"{ROOT}/reference", "reference"),  # by the top-up
    ]


def test_visited_pages_the_model_did_not_add_are_kept_next_to_added_ones(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_call(("add_page", {"url": ROOT, "section": "Start"}))
    fake_openai.will_say("done")

    sitemap = run(fake_openai, max_pages=2)  # budget used: nothing left for the top-up

    assert [(p.url, p.section) for p in sitemap.pages] == [(ROOT, "start"), (f"{ROOT}/learn", "learn")]


def test_model_section_and_url_section_that_differ_only_in_case_are_one_section(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_call(("add_page", {"url": f"{ROOT}/learn", "section": "Learn"}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn/basics"}))  # never added
    fake_openai.will_say("done")

    sitemap = run(fake_openai, max_pages=3)  # budget used: nothing left for the top-up

    assert sitemap.sections == {"home": [ROOT], "learn": [f"{ROOT}/learn", f"{ROOT}/learn/basics"]}


def test_top_up_visits_the_nav_and_main_links_the_model_left_except_skipped_ones(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(
        ("skip_pages", {"urls": [f"{ROOT}/learn"]}), ("add_page", {"url": ROOT, "section": "home"})
    )
    fake_openai.will_say("done")

    sitemap, stats = run_with_stats(fake_openai)

    # /learn was skipped, /privacy is a footer link, evil.test is another site: only /reference is left.
    assert [(p.url, p.depth, p.parent, p.section) for p in sitemap.pages] == [
        (ROOT, 0, None, "home"),
        (f"{ROOT}/reference", 1, ROOT, "reference"),
    ]
    assert stats.top_up == 1
    assert stats.tool_calls == {"visit_page": 1, "skip_pages": 1, "add_page": 1}  # not model calls


def test_top_up_stops_at_the_page_budget(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_say("done")

    sitemap, stats = run_with_stats(fake_openai, max_pages=2)

    assert [p.url for p in sitemap.pages] == [ROOT, f"{ROOT}/learn"]
    assert stats.top_up == 1


async def banner_fetch(url):
    # /guide comes before the nav links; /docs is first listed from a banner outside nav and main.
    home = [
        Link(url="/guide", text="Guide", region="main"),
        Link(url="/docs", text="Docs", region="other"),
        Link(url="/docs", text="Docs", region="nav"),
    ]
    return f"title {url}", home if url == ROOT else []


def test_top_up_visits_top_level_links_first_whatever_region_listed_them(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_say("done")

    sitemap, stats = run_with_stats(fake_openai, fetch=banner_fetch)

    assert [p.url for p in sitemap.pages] == [ROOT, f"{ROOT}/docs", f"{ROOT}/guide"]
    assert stats.top_up == 2


def test_no_top_up_when_the_agent_run_fails(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_raise(APIConnectionError(request=REQUEST))

    sitemap, stats = run_with_stats(fake_openai)

    assert (stats.path, stats.top_up) == ("agent", None)
    assert [p.url for p in sitemap.pages] == [ROOT]


def test_stats_count_turns_tool_calls_and_refusals(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}), ("visit_page", {"url": "https://evil.test/x"}))
    fake_openai.will_call(("add_page", {"url": ROOT, "section": "home"}))
    fake_openai.will_say("done")

    _, stats = run_with_stats(fake_openai)

    assert (stats.turns, stats.status) == (3, "done")
    assert stats.tool_calls == {"visit_page": 2, "add_page": 1}
    assert stats.refused == {"visit_page: outside the site": 1}


def test_agent_that_stops_with_budget_and_links_left_is_nudged_to_continue(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_say("done")  # 3 links left unvisited: nudged
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn"}))
    fake_openai.will_say("done")  # nudge used up: the run ends

    sitemap = run(fake_openai, max_nudges=1)

    nudge = fake_openai.requests[2]["input"][-1]
    assert nudge["role"] == "user"
    assert nudge["content"].startswith("29 pages of budget are left and 3 listed links are not visited yet.")
    assert [p.url for p in sitemap.pages] == [ROOT, f"{ROOT}/learn", f"{ROOT}/reference"]  # top-up


def test_api_error_falls_back_to_the_crawl_of_nav_and_main_links(fake_openai):
    fake_openai.will_raise(APIConnectionError(request=REQUEST))

    sitemap, stats = run_with_stats(fake_openai)

    assert stats.path == "fallback"

    assert [(p.url, p.depth, p.section) for p in sitemap.pages] == [
        (ROOT, 0, "home"),
        (f"{ROOT}/learn", 1, "learn"),
        (f"{ROOT}/reference", 1, "reference"),
        (f"{ROOT}/learn/basics", 2, "learn"),
    ]


def test_crawl_with_all_regions_also_follows_footer_links():
    sitemap = asyncio.run(crawl(ROOT, fake_fetch, CrawlLimits(delay_s=0)))
    assert f"{ROOT}/privacy" in [p.url for p in sitemap.pages]


# A site with one big section: /docs has many pages, also linked straight from the home page.
DOCS = [f"/docs/{c}" for c in "abcde"]
BIG = {
    ROOT: [
        Link(url="/docs", text="Docs", region="nav"),
        Link(url="/deploy", text="Deploy", region="nav"),
        Link(url="/about", text="About", region="nav"),
        *(Link(url=d, text=d, region="main") for d in DOCS),
    ],
    f"{ROOT}/docs": [Link(url=d, text=d, region="main") for d in DOCS],
    f"{ROOT}/deploy": [],
    **{ROOT + d: [] for d in DOCS},
}


async def big_fetch(url):
    return f"title {url}", BIG[url]


def test_deeper_pages_are_refused_until_every_top_section_is_visited_or_skipped(fake_openai):
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/docs"}))
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/docs/a"}))
    fake_openai.will_call(
        ("skip_pages", {"urls": [f"{ROOT}/about"]}), ("visit_page", {"url": f"{ROOT}/deploy"})
    )
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/docs/a"}))
    fake_openai.will_say("done")

    _, stats = run_with_stats(fake_openai, fetch=big_fetch)

    root_links = tool_outputs(fake_openai.requests[1])[0]["links"]
    assert [link["url"] for link in root_links if link["top"]] == [
        f"{ROOT}/docs",
        f"{ROOT}/deploy",
        f"{ROOT}/about",
    ]
    assert root_links[0]["top"]  # top-level links are listed first
    assert tool_outputs(fake_openai.requests[3])[-1] == {
        "ok": False,
        "reason": "cover top sections first",
        "visit_or_skip": [f"{ROOT}/deploy", f"{ROOT}/about"],
    }
    assert tool_outputs(fake_openai.requests[5])[-1]["ok"] is True
    assert stats.refused == {"visit_page: cover top sections first": 1}


def test_a_section_over_its_cap_refuses_visits_and_add_page(fake_openai):
    # max_pages=10 -> cap max(3, 10 // 5) = 3
    fake_openai.will_call(("visit_page", {"url": ROOT}))
    fake_openai.will_call(
        ("visit_page", {"url": f"{ROOT}/docs"}),
        ("visit_page", {"url": f"{ROOT}/deploy"}),
        ("skip_pages", {"urls": [f"{ROOT}/about"]}),
    )
    fake_openai.will_call(("add_page", {"url": f"{ROOT}/docs", "section": "Docs"}))
    fake_openai.will_call(*(("visit_page", {"url": f"{ROOT}/docs/{c}"}) for c in "abc"))
    fake_openai.will_call(
        ("add_page", {"url": f"{ROOT}/docs/a", "section": "Docs"}),
        ("add_page", {"url": f"{ROOT}/docs/b", "section": "Docs"}),
        ("add_page", {"url": f"{ROOT}/deploy", "section": "docs "}),  # same section, other spelling
    )
    fake_openai.will_say("done")

    sitemap = run(fake_openai, max_pages=10, fetch=big_fetch)

    visits = tool_outputs(fake_openai.requests[4])[-3:]
    assert [v["ok"] for v in visits] == [True, True, False]
    assert visits[2] == {"ok": False, "reason": "section budget used", "section": "docs", "cap": 3}
    assert tool_outputs(fake_openai.requests[5])[-1] == {
        "ok": False,
        "reason": "section budget used",
        "section": "docs",
        "cap": 3,
    }
    # Visited but not added (the root; /deploy, whose add was refused) are kept under their URL section.
    assert sitemap.sections == {
        "home": [ROOT],
        "docs": [f"{ROOT}/docs", f"{ROOT}/docs/a", f"{ROOT}/docs/b"],
        "deploy": [f"{ROOT}/deploy"],
    }
