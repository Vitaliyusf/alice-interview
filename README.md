# Alice Interview: sitemap builder

Builds a sitemap of a website's real content sections. An LLM agent on the OpenAI Responses API decides
which pages to visit and how to group them into sections; the code loads every page with Playwright and
enforces every limit (same site, depth, page budget, per-section cap, top sections first). The result is
written as UTF-8 JSON and then checked as written. If the agent fails before visiting any page, a
deterministic breadth-first crawl of nav and main links produces the sitemap instead.
A sample output is in [examples/fastapi_sitemap.json](examples/fastapi_sitemap.json).

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
python -m app.sitemap https://fastapi.tiangolo.com --max-pages 30 --max-depth 2 --out sitemap.json
```

It prints a summary of the run and the checks on the written file, and exits 1 if a check fails.

## Test

```bash
python -m pytest -q
```

No key, browser or network needed: the model and the site are faked.

## Layout

| Module | Responsibility |
|---|---|
| `app/config.py` | settings from `.env` and the environment |
| `app/check.py` | one real model call to check the key and the model name |
| `app/sitemap/__main__.py` | CLI: arguments, run, write the file, verify it, print the summary |
| `app/sitemap/service.py` | `build_sitemap()`: the agent under a timeout, the crawl as fallback |
| `app/sitemap/agent.py` | the model loop and the nudges |
| `app/sitemap/prompts.py` | the system prompt, the task message and the nudge text |
| `app/sitemap/tools.py` | tool specs, argument models and dispatch |
| `app/sitemap/session.py` | run state, the guardrails behind each tool, run stats |
| `app/sitemap/limits.py` | `CrawlLimits`: every budget and cap, passed in |
| `app/sitemap/crawl.py` | Playwright page loader and the deterministic BFS crawl |
| `app/sitemap/links.py` | URL rules: normalize, same site, excluded, section from path |
| `app/sitemap/models.py` | `Link`, `Page`, `Sitemap` |
| `app/sitemap/verify.py` | checks on the written file |
