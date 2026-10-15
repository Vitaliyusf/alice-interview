# Write-up: sitemap builder

## What I built

A CLI that builds a sitemap of a website's content sections as a four-step pipeline:
**extract** (Playwright crawl) -> **decide** (one LLM step) -> **build** (code) -> **verify** (checks on the
written file). Every run saves its crawl to `out/extracted.json`, so a run can be inspected and the model
step replayed on the same input (`--replay`) without loading the site again.

## Where the LLM fits, and why there

The model does one thing: it groups pages into named sections and says which pages are not content.
That is judgment the code cannot make from URLs alone. On python.org, for example, it put
`/download/other` with `/downloads`, and `/success-stories` and `/blogs` with `/psf`.

The model works on a snapshot the code has already crawled, shown as numbered lines
(`id | path | title | depth | parent_id`). It answers by page id through strict Structured Outputs. Its one
tool, `get_page(id)`, reads the snapshot and is capped at 10 calls. The model cannot fetch a URL, invent a
page, or break a limit, because it never touches the crawl. An earlier version had the model drive the
crawl through tools. That needed guards, nudges and a top-up to keep it inside the limits and stop it
quitting early. Moving the model after the crawl removed all of those.

## What is deterministic

- **Crawl:** same host, normalized URLs, excluded URLs (auth, files, language copies, tags, paging),
  each URL loaded once, max depth, max pages, and a delay after each load. Only nav and main links are
  followed, and the home page's top menu goes first in the queue.
- **Build rules:** unknown ids are ignored, and each page is in exactly one section (first wins). The root
  is "home", and placing a page beats dropping it. Unplaced pages get their section from the URL, and a page
  whose parent was dropped hangs from its nearest kept ancestor.
- **Fallback:** a missing API key, a model error, an invalid or cut-off answer, or a timeout gives URL-based sections for
  every page. The summary records which path ran (`llm` or `fallback`).

## How I verified

- **Unit tests** use a fake browser and a fake model, with no network. They cover: extract respects
  depth, budget and excluded URLs, and records footer links without following them. Decide parses ids,
  caps tool calls, and falls back on a model error, invalid JSON, a cut-off reply or a timeout. Build
  ignores invented ids, sends unplaced pages to the URL section, and re-parents children of dropped pages.
  `get_page` reads only the snapshot.
- **Checks on the written file:** after each run, verify checks that the file parses, stays on one host,
  has no duplicates, respects depth and page count, has every parent present, keeps sections consistent
  and contains no excluded URLs. It also checks coverage of the home page's top menu (a WARN, not a FAIL).
- **Real run** on python.org with a 30-page budget: every check passed, path `llm`, 1 model call, 0 tool
  calls, coverage 10 of 10 top menu items. Plain breadth-first had reached only 6 of 10: the header
  dropdowns filled the budget first. Queueing the top menu first fixed that in code.

## What's next

- **Grouping quality.** The sections are plausible, not exact. On the latest run `/about` went under
  "organization" while `/shell` landed in "about", and `/about/help` got its own section.
- **Use the drop reasons.** On this run the model dropped nothing. The prompt and the reason list could be
  tested on a site with real noise, such as a news site with legal pages and login walls.
- **Evaluate grouping.** A small labeled set of sites, so prompt changes are measured, not eyeballed.
