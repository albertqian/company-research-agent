"""Role Matcher: picks only strong-fit postings from a company's free job board (no search)."""
import config
from agents.base import new_usage, parse_json, profile_text, run_claude

SYSTEM = "You match candidates to job openings. Be strict: right function AND right seniority."

PROMPT = """<profile>{profile}</profile>

Open roles at {company} (index | title | location):
{titles}

Score only roles this candidate is a strong, realistic fit for (0-100). Return at most {max_n}.
Return an empty list if none fit well.
{{"matches": [{{"index": 0, "score": 0, "reason": "one line"}}]}}"""


def run(api_key: str, profile: dict, company: str, jobs: list[dict]) -> tuple[list[dict], dict]:
    if not jobs:
        return [], new_usage()
    jobs = jobs[: config.MAX_JOB_TITLES]
    titles = "\n".join(f"{i} | {j['title']} | {j['location']}" for i, j in enumerate(jobs))
    text, usage = run_claude(
        api_key, "role_matcher", SYSTEM,
        PROMPT.format(profile=profile_text(profile), company=company, titles=titles,
                      max_n=config.ROLE_MAX_SHOWN),
    )
    picked = []
    for m in parse_json(text, "Role Matcher").get("matches", []):
        try:
            idx, score = int(m["index"]), int(m["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(jobs) and score >= config.ROLE_MIN_MATCH:
            picked.append({**jobs[idx], "id": jobs[idx]["url"], "match": score, "reason": m.get("reason", "")})
    picked.sort(key=lambda r: r["match"], reverse=True)
    return picked[: config.ROLE_MAX_SHOWN], usage
