"""Command line: extract -> decide -> build -> write -> verify -> summary. Orchestration only.

Flow: extract crawls the site with Playwright and the snapshot is written to out/extracted.json (or
--replay reads one back); decide asks the model for sections; build applies them; the sitemap is
written as UTF-8 JSON, verified as written, and a summary is printed.
Design: the CLI owns every resource and opens each only for its step (the browser for extract, one
OpenAI client for decide). The exit code is 1 when a check FAILs, so a script or CI can trust a zero exit.
"""

import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.sitemap.build import build
from app.sitemap.decide import DecideStats, Decision, decide
from app.sitemap.extract import browser_fetch, extract
from app.sitemap.limits import CrawlLimits
from app.sitemap.links import normalize
from app.sitemap.models import Sitemap, Snapshot
from app.sitemap.verify import verify


async def extract_site(url: str, limits: CrawlLimits) -> Snapshot:
    """Run extract inside one browser, closed at the end."""
    async with browser_fetch() as fetch:
        return await extract(url, fetch, limits)


async def decide_site(snapshot: Snapshot, limits: CrawlLimits) -> tuple[Decision | None, DecideStats]:
    """Run decide with one OpenAI client, closed at the end."""
    # Settings are read here, not at import: a missing key fails the run, not the import.
    settings = get_settings()
    async with AsyncOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        timeout=settings.openai_timeout_s,
        max_retries=settings.openai_max_retries,
    ) as client:
        return await decide(client, settings.openai_model, snapshot, limits)


def write_json(path: Path, model: BaseModel) -> None:
    """Write a model as UTF-8 JSON with "\\n" line ends, creating the folder."""
    # UTF-8 and "\n" whatever the OS: titles are not ASCII on many sites, and the file must be the same
    # bytes on Windows and Linux. The trailing newline keeps pre-commit's end-of-file-fixer quiet.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def summary(snapshot: Snapshot, sitemap: Sitemap, dropped: Counter[str], stats: DecideStats) -> list[str]:
    """Human-readable lines about the result and the run."""
    path = stats.path if stats.reason is None else f"{stats.path} ({stats.reason})"
    return [
        f"path: {path}",
        f"pages extracted: {len(snapshot.pages)}",
        f"pages kept: {len(sitemap.pages)}",
        f"dropped: {sum(dropped.values())}"
        + "".join(f"\n  {reason}: {n}" for reason, n in dropped.most_common()),
        "sections:",
        *(f"  {name}: {len(urls)}" for name, urls in sitemap.sections.items()),
        f"llm_calls: {stats.llm_calls}",
        f"tool_calls: {stats.tool_calls}",
        f"tokens: {'unknown' if stats.tokens is None else stats.tokens}",
    ]


def main() -> None:
    """Parse the arguments, run the pipeline, write the files and exit 1 when a check fails."""
    # Defaults come from CrawlLimits, so the CLI and the library cannot disagree on them.
    parser = argparse.ArgumentParser(prog="python -m app.sitemap")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=CrawlLimits.max_pages)
    parser.add_argument("--max-depth", type=int, default=CrawlLimits.max_depth)
    parser.add_argument("--out", type=Path, default=Path("sitemap.json"))
    parser.add_argument("--snapshot", type=Path, default=Path("out/extracted.json"), help="where to write it")
    parser.add_argument("--replay", type=Path, help="skip extract and read this snapshot instead")
    args = parser.parse_args()
    # The HTTP client logs every model request at INFO (as "httpx2" under openai 3.x), so it is quieted.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    limits = CrawlLimits(max_pages=args.max_pages, max_depth=args.max_depth)

    # 1. Extract (or replay a saved extract).
    if args.replay:
        snapshot = Snapshot.model_validate_json(args.replay.read_text(encoding="utf-8"))
        if snapshot.site != normalize(args.url):
            parser.error(f"--replay is a snapshot of {snapshot.site}, not {args.url}")
    else:
        snapshot = asyncio.run(extract_site(args.url, limits))
        write_json(args.snapshot, snapshot)
        print(f"wrote {args.snapshot}")
    # 2. Decide, 3. build.
    decision, stats = asyncio.run(decide_site(snapshot, limits))
    sitemap, dropped = build(snapshot, decision)
    # 4. Write, 5. verify the file as written, not the object in memory. Coverage is judged against the
    # home page links extract recorded; no root page means no coverage check (a WARN).
    write_json(args.out, sitemap)
    print(f"wrote {args.out}")
    home_links = snapshot.pages[0].links if snapshot.pages else None
    checks = verify(
        args.out.read_text(encoding="utf-8"), args.url, limits.max_pages, limits.max_depth, home_links
    )
    print("checks:")
    for check in checks:
        print(f"  {check.status} {check.name}: {check.reason}")
    # 6. Summary.
    print("\n".join(summary(snapshot, sitemap, dropped, stats)))
    sys.exit(1 if any(c.status == "FAIL" for c in checks) else 0)


if __name__ == "__main__":
    main()
