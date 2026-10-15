"""Build: apply the model's Decision to the snapshot and produce the Sitemap. Pure code, no I/O.

Flow: __main__ calls build() with the Snapshot from extract and the Decision from decide (None on the
fallback path); the Sitemap it returns is written and then verified.
Design: the model's answer is a suggestion checked here. Ids not in the snapshot are ignored, a page sits
in exactly one section (the first that names it), placing beats dropping, the root and only the root is
"home", and
a page the model neither placed nor dropped gets its section from its URL. So every rule holds whatever
the model said.
"""

from collections import Counter

from app.sitemap.decide import Decision
from app.sitemap.links import section_of
from app.sitemap.models import Page, Sitemap, Snapshot

# A section name is a label in the output, not a place for page text.
MAX_SECTION_NAME = 60


def build(snapshot: Snapshot, decision: Decision | None) -> tuple[Sitemap, Counter[str]]:
    """The sitemap and the count of dropped pages per reason. decision=None: every page by its URL."""
    by_id = {p.id: p for p in snapshot.pages}
    placed: dict[int, str] = {}
    dropped: dict[int, str] = {}
    if decision is not None:
        for section in decision.sections:
            # One spelling per section: "Docs", "docs " and "DOCS" are the same section.
            name = section.name.strip().lower()[:MAX_SECTION_NAME].strip()
            # "home" is reserved for the root (set below); other pages the model put there count as unplaced.
            if not name or name == "home":
                continue
            for page_id in section.page_ids:
                # Unknown ids are ignored; the first section that names a page wins.
                if page_id in by_id and page_id not in placed:
                    placed[page_id] = name
        for drop in decision.dropped:
            # Placing beats dropping: a page the model also put in a section is kept.
            if drop.id in by_id and drop.id not in placed and drop.id not in dropped:
                dropped[drop.id] = drop.reason

    root = snapshot.pages[0].id if snapshot.pages else None
    if root is not None:
        # The root is "home" whatever the model said, and it is never dropped.
        placed[root] = "home"
        dropped.pop(root, None)

    pages: list[Page] = []
    for p in snapshot.pages:
        if p.id in dropped:
            continue
        # A kept page whose parent was dropped hangs from its nearest kept ancestor, so every parent in
        # the file is a page in the file. Its depth stays its link distance from the root. The walk stops
        # on a repeat, so a hand-edited --replay snapshot with a parent cycle cannot loop forever.
        parent_id, walked = p.parent_id, set()
        while parent_id in dropped and parent_id not in walked:
            walked.add(parent_id)
            parent_id = by_id[parent_id].parent_id
        pages.append(
            Page(
                url=p.url,
                title=p.title,
                depth=p.depth,
                # An id that is not a kept page (only possible in an edited snapshot) gives no parent.
                parent=by_id[parent_id].url if parent_id in by_id and parent_id not in dropped else None,
                section=placed.get(p.id) or section_of(p.url).lower(),
            )
        )
    return Sitemap.build(snapshot.site, pages), Counter(dropped.values())
