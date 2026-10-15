import argparse
import asyncio
import logging

from openai import AsyncOpenAI

from app.config import get_settings
from sitemap.agent import build_sitemap
from sitemap.crawl import browser_fetch
from sitemap.models import Sitemap


async def run(url: str, max_pages: int, max_depth: int) -> Sitemap:
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
        return await build_sitemap(url, client, settings.openai_model, fetch, max_pages, max_depth)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m sitemap")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    result = asyncio.run(run(args.url, args.max_pages, args.max_depth))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
