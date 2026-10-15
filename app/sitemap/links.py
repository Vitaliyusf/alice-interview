"""URL rules shared by extract, build and the checks: pure functions, no I/O.

Flow: extract calls these before any page load; build uses section_of for pages the model did not place;
verify calls the same rules on the written file.
Design: one set of rules for producing and for checking the sitemap, so the checks cannot drift from the
crawler. The exclusion rules are unit-tested on literal URLs.
"""

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.sitemap.models import Link

# Not web pages: nothing to load.
EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
# Downloads, not pages: loading them wastes budget and they have no links to follow.
FILE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip")
# Auth pages are not content, and some have side effects (logout).
AUTH_SEGMENTS = {"login", "signin", "signup", "register", "account", "logout"}
# Translated copies of the same pages: they would fill the budget with duplicates. Any 2-letter first
# segment matches, so a real /ai or /go section is excluded too: a known trade-off.
# First segment only: 2 letters (hi, uk) optionally with a region or script (pt-br, zh-hant).
LANGUAGE_PREFIX = re.compile(r"^/[a-z]{2}([-_][a-z]{2,4})?(/|$)", re.I)
# Archive pages (/page/2): endless lists of the same content.
PAGINATION = re.compile(r"/page/\d+(/|$)")


def normalize(url: str) -> str:
    """Drop fragment and query, lowercase the host, strip the trailing slash."""
    # One spelling per page, so "/a/", "/a#x" and "/a?ref=nav" are not visited three times.
    # The path keeps its case: on many servers /Docs and /docs are different pages.
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _host(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    return host.removeprefix("www.")


def same_host(url: str, root: str) -> bool:
    """True when url is on the same site as root; www. and the bare domain are one site."""
    # Subdomains (blog.example.com) are other sites: the sitemap is of one host.
    return _host(url) == _host(root)


def section_of(url: str) -> str:
    """Section from the URL alone: the first path segment, or "home" for the root."""
    # The fallback name when the model did not name a page: on most sites the first segment is the section.
    segments = [s for s in urlsplit(url).path.split("/") if s]
    return segments[0] if segments else "home"


def is_excluded(url: str) -> bool:
    """True for URLs that are never content: other schemes, files, auth, language copies, tags, paging."""
    parts = urlsplit(url)
    if parts.scheme.lower() in EXCLUDED_SCHEMES:
        return True
    # Case-insensitive: /Brochure.PDF and /LOGIN are the same traps.
    path = parts.path.lower()
    if path.endswith(FILE_EXTENSIONS):
        return True
    # Whole segments, so /accounting is kept and /account/settings is not.
    if AUTH_SEGMENTS & set(path.split("/")):
        return True
    if LANGUAGE_PREFIX.match(path):
        return True
    # Tag pages and pagination only list pages that are reachable anyway.
    return "/tag/" in path or bool(PAGINATION.search(path))


def top_menu(root: str, home_links: list[Link]) -> dict[str, str]:
    """Home page <nav> links to top-level paths (one segment) on the same site: url -> link text."""
    # The site's own list of sections: verify judges coverage against it.
    menu: dict[str, str] = {}
    for link in home_links:
        url = normalize(urljoin(root, link.url))
        segments = [s for s in urlsplit(url).path.split("/") if s]
        if link.region == "nav" and len(segments) == 1 and same_host(url, root) and not is_excluded(url):
            # The first link text wins; an icon-only link falls back to its path segment.
            menu.setdefault(url, link.text.strip() or segments[0])
    return menu
