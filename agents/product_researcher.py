"""Product Researcher: product overview for a company (the only sub-agent that uses paid search)."""
from datetime import date

import config
from agents.base import parse_json, run_claude

SYSTEM = "You are a product analyst. Be factual; never invent products or customers."

PROMPT = """Write a product overview of **{company}**. Today is {today}.
Use web search at most once, only if you are not confident about current products.

Return:
{{
  "company": "official name",
  "website": "url",
  "summary": "2-3 sentences: what they sell and to whom",
  "products": [{{"name": "", "what_it_does": "one line"}}],
  "customers": "who buys (segments, notable customers if known)",
  "competitors": ["max 5"],
  "positioning": "one line: how they differentiate"
}}
Max 6 products."""


def run(api_key: str, company: str) -> tuple[dict, dict]:
    text, usage = run_claude(
        api_key, "product_researcher", SYSTEM,
        PROMPT.format(company=company, today=date.today().isoformat()),
        max_searches=config.PRODUCT_MAX_SEARCHES,
    )
    return parse_json(text, "Product Researcher"), usage
