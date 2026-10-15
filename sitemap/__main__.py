import argparse
import asyncio
import logging

from sitemap.crawl import crawl


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m sitemap")
    parser.add_argument("url")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--max-depth", type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(crawl(args.url, args.max_pages, args.max_depth))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
