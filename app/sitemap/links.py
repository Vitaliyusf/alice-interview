"""URL rules shared by the agent, the crawl and the checks: pure functions, no I/O."""

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.sitemap.models import Link

EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
FILE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip")
AUTH_SEGMENTS = {"login", "signin", "signup", "register", "account", "logout"}
# First segment only: 2 letters (hi, uk) optionally with a region or script (pt-br, zh-hant).
LANGUAGE_PREFIX = re.compile(r"^/[a-z]{2}([-_][a-z]{2,4})?(/|$)", re.I)
PAGINATION = re.compile(r"/page/\d+(/|$)")


def normalize(url: str) -> str:
    """Drop fragment and query, lowercase the host, strip the trailing slash."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _host(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host.removeprefix("www.")


def same_host(url: str, root: str) -> bool:
    """True when url is on the same site as root; www. and the bare domain are one site."""
    return _host(url) == _host(root)


def section_of(url: str) -> str:
    """Section from the URL alone: the first path segment, or "home" for the root."""
    segments = [s for s in urlsplit(url).path.split("/") if s]
    return segments[0] if segments else "home"


def is_excluded(url: str) -> bool:
    """True for URLs that are never content: other schemes, files, auth, language copies, tags, paging."""
    parts = urlsplit(url)
    if parts.scheme.lower() in EXCLUDED_SCHEMES:
        return True
    path = parts.path.lower()
    if path.endswith(FILE_EXTENSIONS):
        return True
    if AUTH_SEGMENTS & set(path.split("/")):
        return True
    if LANGUAGE_PREFIX.match(path):
        return True
    return "/tag/" in path or bool(PAGINATION.search(path))


def top_menu(root: str, home_links: list[Link]) -> dict[str, str]:
    """Home page <nav> links to top-level paths (one segment) on the same site: url -> link text."""
    menu: dict[str, str] = {}
    for link in home_links:
        url = normalize(urljoin(root, link.url))
        segments = [s for s in urlsplit(url).path.split("/") if s]
        if link.region == "nav" and len(segments) == 1 and same_host(url, root) and not is_excluded(url):
            menu.setdefault(url, link.text.strip() or segments[0])
    return menu
