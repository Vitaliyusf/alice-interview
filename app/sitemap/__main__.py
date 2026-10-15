"""Command line: build a sitemap, write it as UTF-8 JSON, verify the written file and print a summary.

Flow: main parses the arguments into CrawlLimits, run opens the OpenAI client and the browser and calls
service.build_sitemap, then main writes the file and runs verify on it.
Design: the CLI owns every resource (one client, one browser) and closes them; the exit code is 1 when a
check FAILs, so a script or CI can trust a zero exit.
"""

import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI
from playwright.async_api import Error as PlaywrightError

from app.config import get_settings
from app.sitemap.crawl import browser_fetch
from app.sitemap.limits import CrawlLimits
from app.sitemap.links import normalize
from app.sitemap.models import Link, Sitemap
from app.sitemap.service import build_sitemap
from app.sitemap.session import RunStats
from app.sitemap.verify import Check, verify


async def run(url: str, limits: CrawlLimits) -> tuple[Sitemap, RunStats, list[Link] | None]:
    """Build the sitemap and reload the home page; home links are None when that reload fails."""
    # Settings are read here, not at import: a missing key fails the run, not the import.
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
        sitemap, stats = await build_sitemap(url, client, settings.openai_model, fetch, limits)
        # One extra load of the home page, so coverage is judged against what the site shows now.
        try:
            _, home_links = await fetch(normalize(url))
        except PlaywrightError:
            # No home page, no coverage check: verify reports a WARN instead of guessing.
            home_links = None
        return sitemap, stats, home_links


def summary(sitemap: Sitemap, stats: RunStats) -> list[str]:
    """Human-readable lines about the result and the run."""
    # Enough to judge a run without opening the file: which path, how deep, which sections, and what
    # the code refused the model.
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
        f"top-up visited: {'not run' if stats.top_up is None else stats.top_up}",
    ]
    return lines


def main() -> None:
    """Parse the arguments, run, write the file and exit 1 when a check fails."""
    # Defaults come from CrawlLimits, so the CLI and the library cannot disagree on them.
    parser = argparse.ArgumentParser(prog="python -m app.sitemap")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=CrawlLimits.max_pages)
    parser.add_argument("--max-depth", type=int, default=CrawlLimits.max_depth)
    parser.add_argument("--out", type=Path, default=Path("sitemap.json"))
    args = parser.parse_args()
    # INFO shows the agent's progress; httpx would log every model request at INFO, so it is quieted.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    limits = CrawlLimits(max_pages=args.max_pages, max_depth=args.max_depth)

    sitemap, stats, home_links = asyncio.run(run(args.url, limits))
    # UTF-8 and "\n" whatever the OS: titles are not ASCII on many sites, and the file must be the same
    # bytes on Windows and Linux. The trailing newline keeps pre-commit's end-of-file-fixer quiet.
    args.out.write_text(sitemap.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    print("\n".join(summary(sitemap, stats)))

    # Verify the file as written, not the object in memory.
    checks: list[Check] = verify(
        args.out.read_text(encoding="utf-8"), args.url, limits.max_pages, limits.max_depth, home_links
    )
    print("checks:")
    for check in checks:
        print(f"  {check.status} {check.name}: {check.reason}")
    sys.exit(1 if any(c.status == "FAIL" for c in checks) else 0)


if __name__ == "__main__":
    main()
