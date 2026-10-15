# Alice Interview: sitemap builder

Builds a sitemap of a website's content sections in a pipeline with one model step:

```
main -> extract (Playwright, no LLM) -> decide (LLM) -> build (code) -> write -> verify
```

1. **extract** crawls the site breadth-first with Playwright: same host, normalized URLs, excluded URLs
   skipped, each URL loaded once, within `--max-depth` and `--max-pages`, with a delay after each load.
   It follows nav and main links only, the home page's top menu first; footer and other links are
   recorded, not followed. It stores each
   page's id, URL, title, h1, depth, parent id and links in `out/extracted.json`.
2. **decide** sends the snapshot to the model as one line per page (`id | path | title | depth | parent_id`).
   The model answers with strict Structured Outputs, by page id only:
   `{"sections": [{"name": "downloads", "page_ids": [3, 7]}], "dropped": [{"id": 9, "reason": "login"}]}`.
   It may call `get_page(id)` up to 10 times to see a page's h1 and links; that tool reads the snapshot,
   never the network.
3. **build** applies the answer under code rules: unknown ids are ignored, each page lands in exactly one
   section (the first that names it), the root is `home`, and pages the model neither placed nor dropped
   get their section from the URL. A missing API key, a model error, an invalid answer or a timeout means
   no answer: every page then gets its section from the URL (path `fallback`), and the run goes on.
4. The sitemap is written as UTF-8 JSON and **verify** checks the file as written. The exit code is 1
   when a check FAILs.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env               # then put your OPENAI_API_KEY in .env
python -m app.check                # optional: one real call checks the key and the model
```

## Run

```bash
python -m app.sitemap https://www.python.org --max-pages 30 --out examples/python_sitemap.json
```

Output of that run (the result is in [examples/python_sitemap.json](examples/python_sitemap.json)):

```
wrote out\extracted.json
wrote examples\python_sitemap.json
checks:
  PASS parses: 30 pages
  PASS same site: all on www.python.org
  PASS no duplicates: every url once
  PASS depth: all <= 2
  PASS page count: <= 30
  PASS parents: every non-root page has its parent in the sitemap
  PASS sections: every page in exactly one section, matching its own
  PASS no excluded urls: none
  PASS coverage: 10/10 top menu items
path: llm
pages extracted: 30
pages kept: 30
dropped: 0
sections:
  home: 1
  organization: 4
  jobs: 1
  community: 5
  downloads: 9
  docs: 4
  events: 1
  about: 4
  help: 1
llm_calls: 1
tool_calls: 0
tokens: 1137
```

python.org's header menus put about 60 depth 1 links on the home page. extract therefore queues the home
page's top-level menu items first, so all of them fit in the 30-page budget.

To re-run decide and build on a saved crawl without opening a browser:

```bash
python -m app.sitemap https://www.python.org --replay out/extracted.json --out sitemap.json
```

## Test

```bash
python -m pytest -q
```

No key, browser or network needed: the browser and the model are faked.

## Layout

| Module | Responsibility |
|---|---|
| `app/config.py` | settings from `.env` and the environment |
| `app/check.py` | one real model call to check the key and the model name |
| `app/sitemap/__main__.py` | CLI: runs the pipeline, writes both files, verifies, prints the summary |
| `app/sitemap/extract.py` | Playwright loader and the bounded breadth-first crawl |
| `app/sitemap/decide.py` | the model step: snapshot lines, `get_page` tool, answer schema, fallback |
| `app/sitemap/prompts.py` | the system prompt of the model step |
| `app/sitemap/build.py` | applies the model's answer to the snapshot and produces the `Sitemap` |
| `app/sitemap/limits.py` | `CrawlLimits`: every budget and cap, passed in |
| `app/sitemap/links.py` | URL rules: normalize, same site, excluded, section from path |
| `app/sitemap/models.py` | `Link`, `ExtractedPage`, `Snapshot`, `Page`, `Sitemap` |
| `app/sitemap/verify.py` | checks on the written file |
