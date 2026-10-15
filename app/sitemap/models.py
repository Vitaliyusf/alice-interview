"""The data shapes of a sitemap run: a scraped link, a recorded page and the sitemap file.

Flow: crawl creates Links; Session and crawl create Pages; Sitemap is what __main__ writes and verify reads.
Design: Pydantic models, so the file is validated when written and parsed and validated again by
verify when read back.
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
