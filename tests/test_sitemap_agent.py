"""The sitemap agent with a scripted fake model and a fake site: no browser, no network."""

import asyncio
import json

from openai import APIConnectionError

from sitemap.agent import build_sitemap
from sitemap.crawl import crawl
from sitemap.models import Link
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


def run(fake_openai, max_pages=30):
    return asyncio.run(build_sitemap(ROOT, fake_openai, "m", fake_fetch, max_pages=max_pages, delay_s=0))


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
        (f"{ROOT}/learn", 1, ROOT, "Learn"),
    ]
    assert sitemap.sections == {"home": [ROOT], "Learn": [f"{ROOT}/learn"]}
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
    assert [p.url for p in sitemap.pages] == [ROOT]


def test_visit_of_an_unlisted_url_is_refused(fake_openai):
    fake_openai.will_call(("visit_page", {"url": f"{ROOT}/learn/basics"}))
    fake_openai.will_raise(APIConnectionError(request=REQUEST))  # ends the run; the fallback follows

    run(fake_openai)

    assert tool_outputs(fake_openai.requests[1])[-1] == {
        "ok": False,
        "reason": "not linked from a visited page",
    }


def test_api_error_falls_back_to_the_crawl_of_nav_and_main_links(fake_openai):
    fake_openai.will_raise(APIConnectionError(request=REQUEST))

    sitemap = run(fake_openai)

    assert [(p.url, p.depth, p.section) for p in sitemap.pages] == [
        (ROOT, 0, "home"),
        (f"{ROOT}/learn", 1, "learn"),
        (f"{ROOT}/reference", 1, "reference"),
        (f"{ROOT}/learn/basics", 2, "learn"),
    ]


def test_crawl_with_all_regions_also_follows_footer_links():
    sitemap = asyncio.run(crawl(ROOT, fake_fetch, delay_s=0))
    assert f"{ROOT}/privacy" in [p.url for p in sitemap.pages]
