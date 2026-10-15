"""build() on a hand-made snapshot and decision: pure code, no model."""

from app.sitemap.build import build
from app.sitemap.decide import Decision
from tests.sitemap.conftest import ROOT, make_snapshot


def decision(sections: list[tuple[str, list[int]]], dropped: list[tuple[int, str]] = ()) -> Decision:
    return Decision.model_validate(
        {
            "sections": [{"name": n, "page_ids": ids} for n, ids in sections],
            "dropped": [{"id": i, "reason": r} for i, r in dropped],
        }
    )


def test_places_pages_by_id_and_lowercases_section_names():
    answer = decision([("home", [0]), ("Downloads", [1, 4]), ("Docs ", [2])], [(3, "login")])

    sitemap, dropped = build(make_snapshot(), answer)

    assert sitemap.sections == {
        "home": [ROOT],
        "downloads": [f"{ROOT}/downloads", f"{ROOT}/downloads/windows"],
        "docs": [f"{ROOT}/docs"],
    }
    assert dropped == {"login": 1}


def test_invented_ids_are_ignored():
    answer = decision([("home", [0, 99]), ("downloads", [1, 4, -1]), ("docs", [2, 3])], [(42, "other")])

    sitemap, dropped = build(make_snapshot(), answer)

    assert [p.url for p in sitemap.pages] == [p.url for p in make_snapshot().pages]
    assert dropped == {}


def test_a_page_named_twice_stays_in_the_first_section_and_placing_beats_dropping():
    answer = decision([("downloads", [1, 2]), ("docs", [2])], [(1, "not_content")])

    sitemap, dropped = build(make_snapshot(), answer)

    # /downloads/windows is unplaced: "downloads" from its URL.
    assert sitemap.sections["downloads"] == [f"{ROOT}/downloads", f"{ROOT}/docs", f"{ROOT}/downloads/windows"]
    assert "docs" not in sitemap.sections
    assert dropped == {}


def test_unplaced_page_gets_its_section_from_the_url():
    answer = decision([("home", [0]), ("docs", [2])])

    sitemap, _ = build(make_snapshot(), answer)

    by_url = {p.url: p.section for p in sitemap.pages}
    assert by_url[f"{ROOT}/downloads"] == "downloads"
    assert by_url[f"{ROOT}/downloads/windows"] == "downloads"
    assert by_url[f"{ROOT}/login-help"] == "login-help"


def test_long_names_are_cut_and_empty_names_or_non_root_home_count_as_unplaced():
    answer = decision([("D" * 100, [1]), ("  ", [2]), ("Home", [4])])

    sitemap, _ = build(make_snapshot(), answer)

    by_url = {p.url: p.section for p in sitemap.pages}
    assert by_url[f"{ROOT}/downloads"] == "d" * 60
    assert by_url[f"{ROOT}/docs"] == "docs"
    assert by_url[f"{ROOT}/downloads/windows"] == "downloads"
    assert sitemap.sections["home"] == [ROOT]


def test_root_is_home_and_never_dropped():
    answer = decision([("start", [0])], [(0, "other")])

    sitemap, dropped = build(make_snapshot(), answer)

    assert sitemap.pages[0].url == ROOT
    assert sitemap.pages[0].section == "home"
    assert dropped == {}


def test_child_of_a_dropped_page_hangs_from_the_nearest_kept_ancestor():
    answer = decision([("home", [0]), ("windows", [4])], [(1, "duplicate")])

    sitemap, _ = build(make_snapshot(), answer)

    windows = next(p for p in sitemap.pages if p.url.endswith("/windows"))
    assert windows.parent == ROOT
    assert windows.depth == 2
    assert f"{ROOT}/downloads" not in [p.url for p in sitemap.pages]


def test_no_decision_is_the_fallback_every_page_by_url():
    sitemap, dropped = build(make_snapshot(), None)

    assert sitemap.sections == {
        "home": [ROOT],
        "downloads": [f"{ROOT}/downloads", f"{ROOT}/downloads/windows"],
        "docs": [f"{ROOT}/docs"],
        "login-help": [f"{ROOT}/login-help"],
    }
    assert dropped == {}
