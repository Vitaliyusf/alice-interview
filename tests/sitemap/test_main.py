"""The CLI's decide step without an API key: no client is created, no network."""

import asyncio

from pydantic import BaseModel

from app.sitemap import __main__ as cli
from app.sitemap.build import build
from app.sitemap.limits import CrawlLimits
from tests.sitemap.conftest import ROOT, make_snapshot


class NeedsKey(BaseModel):
    openai_api_key: str


def test_missing_api_key_falls_back_to_url_sections(monkeypatch):
    # get_settings raises pydantic's ValidationError when the key is missing, as Settings does.
    monkeypatch.setattr(cli, "get_settings", lambda: NeedsKey.model_validate({}))

    decision, stats = asyncio.run(cli.decide_site(make_snapshot(), CrawlLimits()))
    sitemap, _ = build(make_snapshot(), decision)

    assert decision is None
    assert (stats.path, stats.reason, stats.llm_calls) == ("fallback", "no api key", 0)
    assert sitemap.sections["downloads"] == [f"{ROOT}/downloads", f"{ROOT}/downloads/windows"]
