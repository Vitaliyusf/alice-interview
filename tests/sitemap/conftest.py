"""A small hand-made snapshot shared by the decide and build tests."""

from app.sitemap.models import ExtractedPage, Link, Snapshot

ROOT = "https://site.test"


def page(
    page_id: int, path: str, depth: int, parent_id: int | None, links: list[Link] | None = None
) -> ExtractedPage:
    return ExtractedPage(
        id=page_id,
        url=ROOT + path,
        title=f"Title {path or '/'}",
        h1=f"H1 {path or '/'}",
        depth=depth,
        parent_id=parent_id,
        links=links or [],
    )


def make_snapshot() -> Snapshot:
    """home -> /downloads -> /downloads/windows, home -> /docs, home -> /login."""
    return Snapshot(
        site=ROOT,
        pages=[
            page(
                0,
                "",
                0,
                None,
                [
                    Link(url=f"{ROOT}/downloads", text="Downloads", region="nav"),
                    Link(url=f"{ROOT}/docs", text="Docs", region="nav"),
                    Link(url=f"{ROOT}/blog", text="Blog", region="footer"),
                ],
            ),
            page(1, "/downloads", 1, 0),
            page(2, "/docs", 1, 0),
            page(3, "/login-help", 1, 0),
            page(4, "/downloads/windows", 2, 1),
        ],
    )
