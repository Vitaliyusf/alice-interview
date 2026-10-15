from typing import Literal

from pydantic import BaseModel

Region = Literal["nav", "main", "footer", "other"]


class Link(BaseModel):
    url: str
    text: str
    region: Region


class Page(BaseModel):
    url: str
    title: str
    depth: int
    parent: str | None
    section: str


class Sitemap(BaseModel):
    site: str
    pages: list[Page]
    sections: dict[str, list[str]]

    @classmethod
    def build(cls, site: str, pages: list[Page]) -> "Sitemap":
        sections: dict[str, list[str]] = {}
        for page in pages:
            sections.setdefault(page.section, []).append(page.url)
        return cls(site=site, pages=pages, sections=sections)
