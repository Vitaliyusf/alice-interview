"""Pure URL rules for the crawler. No I/O."""

import re
from urllib.parse import urlsplit, urlunsplit

EXCLUDED_SCHEMES = {"mailto", "tel", "javascript"}
FILE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip")
AUTH_SEGMENTS = {"login", "signin", "signup", "register", "account", "logout"}
LANGUAGE_PREFIX = re.compile(r"^/(es|fr|de|ja|zh|it|pt|ru|ko|nl|pl|tr|ar)(-[a-z]{2})?(/|$)", re.I)
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
