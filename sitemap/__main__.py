import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI
from playwright.async_api import Error as PlaywrightError

from app.config import get_settings
from sitemap.agent import RunStats, build_sitemap
from sitemap.crawl import browser_fetch
from sitemap.links import normalize
from sitemap.models import Link, Sitemap
from sitemap.verify import Check, verify


async def run(url: str, max_pages: int, max_depth: int) -> tuple[Sitemap, RunStats, list[Link] | None]:
    settings = get_settings()
    # The CLI is its own process: one client for the whole run, closed at the end.
    async with (
        AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_timeout_s,
            max_retries=settings.openai_max_retries,
        ) as client,
        browser_fetch() as fetch,
    ):
        sitemap, stats = await build_sitemap(url, client, settings.openai_model, fetch, max_pages, max_depth)
        # One extra load of the home page, so coverage is judged against what the site shows now.
        try:
            _, home_links = await fetch(normalize(url))
        except PlaywrightError:
            home_links = None
        return sitemap, stats, home_links


def summary(sitemap: Sitemap, stats: RunStats) -> list[str]:
    depths = Counter(p.depth for p in sitemap.pages)
    lines = [
        f"path: {stats.path} (agent status: {stats.status})",
        f"pages: {len(sitemap.pages)}",
        "pages per depth: " + ", ".join(f"{d}: {n}" for d, n in sorted(depths.items())),
        "sections:",
        *(f"  {name}: {len(urls)}" for name, urls in sitemap.sections.items()),
        f"model turns: {stats.turns}",
        "tool calls: " + (", ".join(f"{k}: {n}" for k, n in stats.tool_calls.items()) or "none"),
        "refused by the code:" + ("" if stats.refused else " none"),
        *(f"  {n} x {reason}" for reason, n in stats.refused.most_common()),
    ]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m sitemap")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("sitemap.json"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    sitemap, stats, home_links = asyncio.run(run(args.url, args.max_pages, args.max_depth))
    args.out.write_text(sitemap.model_dump_json(indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    print("\n".join(summary(sitemap, stats)))

    # Verify the file as written, not the object in memory.
    checks: list[Check] = verify(
        args.out.read_text(encoding="utf-8"), args.url, args.max_pages, args.max_depth, home_links
    )
    print("checks:")
    for check in checks:
        print(f"  {check.status} {check.name}: {check.reason}")
    sys.exit(1 if any(c.status == "FAIL" for c in checks) else 0)


if __name__ == "__main__":
    main()
