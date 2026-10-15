"""Sitemap builder: an LLM agent picks the pages, the code fetches them and enforces every limit.

Flow: __main__ (CLI) -> service.build_sitemap -> agent.run_agent -> tools.run_tool -> Session -> crawl.
Design: the model only decides what to visit and how to group it. It never fetches and never enforces a
rule, so every limit holds whatever the model or the page text says.
"""
