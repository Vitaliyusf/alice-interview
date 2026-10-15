"""The data shapes of a sitemap run: a scraped link, the extracted snapshot, and the sitemap file.

Flow: extract creates Links and the Snapshot; decide and build read the Snapshot; build creates Pages and
the Sitemap that __main__ writes and verify reads.
Design: Pydantic models, so both files (out/extracted.json and the sitemap) are validated when written
and again when read back (replay, verify).
"""

from typing import Literal

from pydantic import BaseModel

# Where an anchor sits on the page: nav links are site structure, footer links are mostly legal noise.
Region = Literal["nav", "main", "footer", "other"]


class Link(BaseModel):
    """An anchor found on a page; `region` is the part of the page it sits in."""

    url: str
    text: str
    region: Region


class ExtractedPage(BaseModel):
    """A page as extract loaded it: what it shows and where the crawl found it."""

    id: int
    url: str
    title: str
    h1: str
    depth: int
    # The page that first linked to it; None for the root.
    parent_id: int | None
    # Same-site, non-excluded links, normalized, one per URL. Footer and other links are here too:
    # recorded, not followed.
    links: list[Link]


class Snapshot(BaseModel):
    """Everything extract saw: the input of decide and build, and the file a run can be replayed from."""

    site: str
    pages: list[ExtractedPage]


class Page(BaseModel):
    """A page in the sitemap, with the page that first linked to it as its parent."""

    url: str
    title: str
    depth: int
    parent: str | None
    section: str


class Sitemap(BaseModel):
    """The written file: every page, and the page URLs of each section."""

    site: str
    pages: list[Page]
    sections: dict[str, list[str]]

    @classmethod
    def build(cls, site: str, pages: list[Page]) -> "Sitemap":
        """Group the pages by their own section, in page order."""
        # Sections are derived from the pages, never kept separately, so the two cannot disagree.
        sections: dict[str, list[str]] = {}
        for page in pages:
            sections.setdefault(page.section, []).append(page.url)
        return cls(site=site, pages=pages, sections=sections)
