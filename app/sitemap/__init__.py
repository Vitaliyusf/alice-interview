"""Sitemap builder: Playwright extracts, the LLM decides the sections, the code builds and verifies.

Flow: __main__ -> extract (bounded BFS, no model) -> decide (one model step over the snapshot)
-> build (applies the decision under code rules) -> write -> verify.
Design: the model never fetches and never enforces a rule. It answers by page id over a snapshot the code
already crawled, so every limit holds whatever the model or the page text says.
"""
