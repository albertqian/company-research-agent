"""News Ranker: picks the most important product news from free headlines (no search)."""
import config
from agents.base import new_usage, parse_json, run_claude

SYSTEM = "You rank company news for job seekers preparing to interview."

PROMPT = """Headlines about {company} from the last {days} days (index | date | source | headline):
{news}

Pick at most {n} headlines that are product-centric: launches, features, product strategy, pricing,
AI, partnerships or M&A that change the product. Prefer the last 15 days.
Skip stock-price chatter, listicles, and duplicates. Empty list if none qualify.
{{"picks": [{{"index": 0, "why_it_matters": "one line for a job seeker"}}]}}"""


def run(api_key: str, company: str, headlines: list[dict]) -> tuple[list[dict], dict]:
    if not headlines:
        return [], new_usage()
    lines = "\n".join(
        f"{i} | {n['date']} | {n['source']} | {n['headline']}" for i, n in enumerate(headlines)
    )
    text, usage = run_claude(
        api_key, "news_ranker", SYSTEM,
        PROMPT.format(company=company, days=config.NEWS_WINDOW_DAYS, news=lines, n=config.NEWS_MAX_ITEMS),
    )
    picked = []
    for p in parse_json(text, "News Ranker").get("picks", []):
        try:
            idx = int(p["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(headlines):
            picked.append({**headlines[idx], "why_it_matters": p.get("why_it_matters", "")})
    picked.sort(key=lambda x: x["date"], reverse=True)
    return picked[: config.NEWS_MAX_ITEMS], usage
