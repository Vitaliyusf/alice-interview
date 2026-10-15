"""Pure URL rules for the crawler. No I/O."""

import re
from urllib.parse import urlsplit, urlunsplit

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
    # www. and the bare domain are the same site.
    return _host(url) == _host(root)


def section_of(url: str) -> str:
    """Section from the URL alone: the first path segment, or "home" for the root."""
    segments = [s for s in urlsplit(url).path.split("/") if s]
    return segments[0] if segments else "home"


def is_excluded(url: str) -> bool:
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
