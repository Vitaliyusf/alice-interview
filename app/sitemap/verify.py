"""Checks on a written sitemap file. FAIL means the sitemap is wrong; WARN means it may be incomplete."""

from collections import Counter
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.sitemap.links import is_excluded, normalize, same_host, top_menu
from app.sitemap.models import Link, Sitemap

MAX_LISTED = 10  # offending URLs shown per check


@dataclass(frozen=True)
class Check:
    """One check result, with the offending URLs or a short reason."""

    name: str
    status: Literal["PASS", "FAIL", "WARN"]
    reason: str


def _check(name: str, bad: list[str], ok_reason: str) -> Check:
    if not bad:
        return Check(name, "PASS", ok_reason)
    shown = ", ".join(bad[:MAX_LISTED]) + (
        f" (+{len(bad) - MAX_LISTED} more)" if len(bad) > MAX_LISTED else ""
    )
    return Check(name, "FAIL", f"{len(bad)}: {shown}")


def verify(raw: str, root: str, max_pages: int, max_depth: int, home_links: list[Link] | None) -> list[Check]:
    """Check the file text against the limits and, when home_links is given, the live top menu."""
    try:
        sitemap = Sitemap.model_validate_json(raw)
    except ValidationError as exc:
        return [Check("parses", "FAIL", f"not a Sitemap: {exc.error_count()} validation errors")]
    root = normalize(root)
    pages = sitemap.pages
    urls = [p.url for p in pages]
    in_sitemap = set(urls)
    listed = Counter(url for members in sitemap.sections.values() for url in members)

    checks = [
        Check("parses", "PASS", f"{len(pages)} pages"),
        _check(
            "same site",
            [u for u in urls if not same_host(u, root)]
            + ([] if same_host(sitemap.site, root) else [sitemap.site]),
            f"all on {urlsplit(root).netloc}",
        ),
        _check("no duplicates", [u for u, n in Counter(urls).items() if n > 1], "every url once"),
        _check(
            "depth",
            [f"{p.url} (depth {p.depth})" for p in pages if p.depth > max_depth],
            f"all <= {max_depth}",
        ),
        _check(
            "page count", [f"{len(pages)} > {max_pages}"] if len(pages) > max_pages else [], f"<= {max_pages}"
        ),
        _check(
            "parents",
            [p.url for p in pages if p.url != root and p.parent not in in_sitemap],
            "every non-root page has its parent in the sitemap",
        ),
        _check(
            "sections",
            [u for u in urls if listed[u] != 1]
            + [p.url for p in pages if p.url not in sitemap.sections.get(p.section, [])]
            + [u for u in listed if u not in in_sitemap],
            "every page in exactly one section, matching its own",
        ),
        _check("no excluded urls", [u for u in urls if is_excluded(u)], "none"),
    ]

    if home_links is None:
        checks.append(Check("coverage", "WARN", "home page could not be loaded"))
    else:
        menu = top_menu(root, home_links)
        missing = [f"{text} ({url})" for url, text in menu.items() if url not in in_sitemap]
        covered = len(menu) - len(missing)
        if missing:
            # A WARN, not a FAIL: some top menu items (About, Sponsors) are skipped on purpose.
            checks.append(
                Check(
                    "coverage", "WARN", f"{covered}/{len(menu)} top menu items; missing: {', '.join(missing)}"
                )
            )
        else:
            checks.append(Check("coverage", "PASS", f"{covered}/{len(menu)} top menu items"))
    return checks
