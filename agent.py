"""Claude calls: role matching, company analysis, role prep, suggestions."""
import json
import re
from datetime import date

import anthropic

import config


class AgentError(Exception):
    pass


def new_usage() -> dict:
    return {"input_tokens": 0, "output_tokens": 0, "searches": 0}


def add_usage(a: dict, b: dict) -> dict:
    return {k: a[k] + b[k] for k in a}


def cost_of(usage: dict) -> float:
    return (
        usage["input_tokens"] / 1e6 * config.PRICE_INPUT_PER_M
        + usage["output_tokens"] / 1e6 * config.PRICE_OUTPUT_PER_M
        + usage["searches"] * config.PRICE_PER_SEARCH
    )


def _run(api_key: str, system: str, prompt: str, max_searches: int = 0) -> tuple[str, dict]:
    """Call Claude (with web search only if max_searches > 0). Returns (text, usage)."""
    client = anthropic.Anthropic(api_key=api_key, max_retries=3)
    messages = [{"role": "user", "content": prompt}]
    kwargs = {}
    if max_searches > 0:
        kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    usage = new_usage()

    for _ in range(4):  # pause_turn continuations
        try:
            resp = client.messages.create(
                model=config.MODEL, max_tokens=config.MAX_OUTPUT_TOKENS,
                system=system, messages=messages, **kwargs,
            )
        except anthropic.APIError as e:
            raise AgentError(f"Claude API error: {e}") from e

        usage["input_tokens"] += resp.usage.input_tokens or 0
        usage["output_tokens"] += resp.usage.output_tokens or 0
        stu = getattr(resp.usage, "server_tool_use", None)
        if stu is not None:
            usage["searches"] += getattr(stu, "web_search_requests", 0) or 0

        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        return "".join(b.text for b in resp.content if b.type == "text"), usage

    raise AgentError("Claude did not finish. Try again.")


def _json(text: str):
    m = re.search(r"<json>(.*?)</json>", text, re.DOTALL)
    raw = (m.group(1) if m else text).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    starts = [i for i in (raw.find("{"), raw.find("[")) if i != -1]
    if not starts:
        raise AgentError("Claude returned no JSON. Try again.")
    raw = raw[min(starts):]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        end = max(raw.rfind("}"), raw.rfind("]"))
        try:
            return json.loads(raw[: end + 1])
        except json.JSONDecodeError as e:
            raise AgentError(f"Could not read Claude's response: {e}") from e


def _fit_total(fit: dict) -> int:
    total = 0.0
    for key, weight in config.FIT_WEIGHTS.items():
        try:
            score = max(0.0, min(100.0, float(fit.get(key, {}).get("score", 0))))
        except (TypeError, ValueError):
            score = 0.0
        total += score * weight
    return round(total)


JSON_ONLY = "Return ONLY one JSON object wrapped in <json></json> tags, no other prose."


# ---------- 1. Match job-board roles (no search) ----------
MATCH_PROMPT = """Candidate resume:
<resume>
{resume}
</resume>

Open roles at {company} (index | title | location):
{titles}

Pick ONLY roles this candidate is a strong, realistic fit for (right function AND right seniority).
Score each pick 0-100. Return at most {max_n}. Return an empty list if none fit well.
{{"matches": [{{"index": 0, "score": 0, "reason": "one line"}}]}}"""


def match_roles(api_key: str, resume: str, company: str, jobs: list[dict]) -> tuple[list[dict], dict]:
    if not jobs:
        return [], new_usage()
    jobs = jobs[: config.MAX_JOB_TITLES]
    titles = "\n".join(f"{i} | {j['title']} | {j['location']}" for i, j in enumerate(jobs))
    text, usage = _run(
        api_key, f"You match candidates to job openings. Be strict. {JSON_ONLY}",
        MATCH_PROMPT.format(resume=resume, company=company, titles=titles, max_n=config.ROLE_MAX_SHOWN),
    )
    picked = []
    for m in _json(text).get("matches", []):
        try:
            idx, score = int(m["index"]), int(m["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(jobs) and score >= config.ROLE_MIN_MATCH:
            picked.append({**jobs[idx], "match": score, "reason": m.get("reason", "")})
    picked.sort(key=lambda r: r["match"], reverse=True)
    return picked[: config.ROLE_MAX_SHOWN], usage


# ---------- 2. Company analysis (1 search max) ----------
ANALYZE_PROMPT = """Research **{company}** for the job seeker below. Today is {today}.

<resume>
{resume}
</resume>

{roles_block}

<news>
Headlines from the last {days} days (index | date | source | headline):
{news}
</news>

Use web search at most once, only for the product overview if you need it.

Return:
{{
  "company": "official name",
  "website": "url",
  "fit": {{
    "skills":     {{"score": 0-100, "reason": "one line: resume skills vs skills this company's roles need"}},
    "domain":     {{"score": 0-100, "reason": "one line: resume industries/markets vs the company's"}},
    "experience": {{"score": 0-100, "reason": "one line: resume years/seniority vs years required"}}
  }},
  "product_overview": {{
    "summary": "2-3 sentences",
    "products": [{{"name": "", "what_it_does": ""}}],
    "customers": "who buys",
    "competitors": [""]
  }},
  "news": [{{"index": 0, "why_it_matters": "one line for a job seeker"}}],
  "interview_prep": {{
    "talking_points": ["resume achievement mapped to the company's needs"],
    "questions": [{{"question": "", "how_to_answer": "tie to a specific resume item"}}],
    "questions_to_ask_them": [""]
  }}
}}

Rules:
- news: pick at most {news_n} headlines by index, product-centric only (launches, features, product strategy, pricing, AI, partnerships/M&A that change the product). Prefer the last 15 days. Skip stock-price chatter, lists, and duplicates. Empty list if none qualify.
- fit: if job descriptions are given, score against them; otherwise against the roles this candidate would target there.
- interview_prep: 5 talking points, 8 questions, 3 questions to ask them. Use the product overview and chosen news.
- Never invent facts."""


def analyze_company(api_key: str, resume: str, company: str,
                    roles: list[dict], news: list[dict]) -> tuple[dict, dict]:
    if roles:
        roles_block = "<job_descriptions>\n" + "\n\n".join(
            f"### {r['title']} ({r['location']})\n{r['description'][: config.JD_CHARS]}" for r in roles
        ) + "\n</job_descriptions>"
    else:
        roles_block = "No matching job postings were found."
    news_lines = "\n".join(
        f"{i} | {n['date']} | {n['source']} | {n['headline']}" for i, n in enumerate(news)
    ) or "(none)"

    text, usage = _run(
        api_key, f"You are a company research analyst for job seekers. {JSON_ONLY}",
        ANALYZE_PROMPT.format(
            company=company, today=date.today().isoformat(), resume=resume,
            roles_block=roles_block, days=config.NEWS_WINDOW_DAYS, news=news_lines,
            news_n=config.NEWS_MAX_ITEMS,
        ),
        config.MAX_SEARCHES_ANALYZE,
    )
    data = _json(text)
    if not isinstance(data, dict):
        raise AgentError("Unexpected response from Claude.")

    picked = []
    for n in data.get("news", []):
        try:
            idx = int(n["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= idx < len(news):
            picked.append({**news[idx], "why_it_matters": n.get("why_it_matters", "")})
    data["news"] = sorted(picked, key=lambda x: x["date"], reverse=True)[: config.NEWS_MAX_ITEMS]
    data["fit_total"] = _fit_total(data.get("fit", {}))
    return data, usage


# ---------- 3. Role-specific prep (no search) ----------
ROLE_PREP_PROMPT = """Prepare this candidate to interview for the role below at {company}.

<resume>
{resume}
</resume>

<job_description title="{title}">
{jd}
</job_description>

Return:
{{
  "requirement_map": [{{"requirement": "from the JD", "evidence": "matching resume item", "strength": "strong|partial|gap"}}],
  "gap_plan": ["how to address each gap in the interview"],
  "questions": [{{"question": "", "how_to_answer": "tie to a specific resume item"}}],
  "pitch": "60-second 'why me for this role' answer in first person"
}}
6-8 requirements, 8 questions. Never invent resume facts."""


def role_prep(api_key: str, resume: str, company: str, role: dict) -> tuple[dict, dict]:
    text, usage = _run(
        api_key, f"You are an interview coach. {JSON_ONLY}",
        ROLE_PREP_PROMPT.format(company=company, resume=resume, title=role["title"],
                                jd=role["description"][: config.JD_CHARS * 2]),
    )
    return _json(text), usage


# ---------- 4. Suggestions (no search) ----------
SUGGEST_PROMPT = """Suggest 8 companies that fit the candidate below. {focus}

<resume>
{resume}
</resume>

Return:
{{
  "candidate_summary": "one line: function, seniority, domains",
  "companies": [{{"name": "", "website": "", "why_fit": "2 lines tied to resume specifics", "likely_role": ""}}]
}}
Prefer companies where the candidate's domain experience transfers directly and that are actively operating today.
Do not suggest the candidate's current or past employers."""


def suggest_companies(api_key: str, resume: str, focus: str) -> tuple[dict, dict]:
    text, usage = _run(
        api_key, f"You are a career strategist. {JSON_ONLY}",
        SUGGEST_PROMPT.format(focus=f"Preferences: {focus}" if focus.strip() else "", resume=resume),
    )
    data = _json(text)
    if not isinstance(data, dict):
        raise AgentError("Unexpected response from Claude.")
    return data, usage
