"""Claude calls: company analysis and company suggestions."""
import json
import re
from datetime import date, datetime, timedelta

import anthropic

import config


class AgentError(Exception):
    pass


def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


def _run(api_key: str, system: str, prompt: str, max_searches: int) -> tuple[str, dict]:
    """Run Claude with web search; handle pause_turn; return (text, usage)."""
    client = _client(api_key)
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    usage = {"input_tokens": 0, "output_tokens": 0, "searches": 0}

    for _ in range(5):  # pause_turn continuations
        try:
            resp = client.messages.create(
                model=config.MODEL,
                max_tokens=config.MAX_OUTPUT_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
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
        text = "".join(b.text for b in resp.content if b.type == "text")
        return text, usage

    raise AgentError("Claude did not finish after several continuation rounds.")


def _extract_json(text: str):
    m = re.search(r"<json>(.*?)</json>", text, re.DOTALL)
    raw = m.group(1) if m else text
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start = min([i for i in (raw.find("{"), raw.find("[")) if i != -1], default=-1)
    if start == -1:
        raise AgentError("Claude returned no JSON. Try running again.")
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError:
        end = max(raw.rfind("}"), raw.rfind("]"))
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError as e:
            raise AgentError(f"Could not parse Claude's JSON: {e}") from e


def cost_of(usage: dict) -> float:
    return (
        usage["input_tokens"] / 1e6 * config.PRICE_INPUT_PER_M
        + usage["output_tokens"] / 1e6 * config.PRICE_OUTPUT_PER_M
        + usage["searches"] * config.PRICE_PER_SEARCH
    )


def _filter_news(items: list[dict]) -> list[dict]:
    cutoff = date.today() - timedelta(days=config.NEWS_WINDOW_DAYS)
    kept = []
    for it in items:
        try:
            d = datetime.strptime(str(it.get("date", ""))[:10], "%Y-%m-%d").date()
        except ValueError:
            continue  # undated items are dropped: we can't prove they are within the window
        if d >= cutoff:
            kept.append(it)
    return sorted(kept, key=lambda x: x["date"], reverse=True)


def _fit_total(fit: dict) -> int:
    total = 0.0
    for key, weight in config.FIT_WEIGHTS.items():
        score = fit.get(key, {}).get("score", 0)
        try:
            score = max(0, min(100, float(score)))
        except (TypeError, ValueError):
            score = 0
        total += score * weight
    return round(total)


ANALYZE_SYSTEM = """You are a company research analyst for job seekers. Today is {today}.
Use web search to research the company. Be factual; never invent roles, news, dates, or URLs.
Return ONLY one JSON object wrapped in <json></json> tags, no other prose."""

ANALYZE_PROMPT = """Research **{company}** for the job seeker whose resume is below.

<resume>
{resume}
</resume>

{jobs_block}

Return this JSON:
{{
  "company": "official name",
  "website": "url",
  "fit": {{
    "skills":     {{"score": 0-100, "reason": "one line: overlap between resume skills and skills the company's roles need"}},
    "domain":     {{"score": 0-100, "reason": "one line: overlap between resume industries/markets and the company's"}},
    "experience": {{"score": 0-100, "reason": "one line: resume years/seniority vs years required by the relevant roles"}}
  }},
  "open_roles": [
    {{"title": "", "location": "", "url": "", "why_qualified": "one line", "gaps": "one line or empty"}}
  ],
  "roles_note": "one line on how complete the role list is",
  "interview_prep": {{
    "talking_points": ["resume achievement mapped to the company's needs"],
    "questions": [{{"question": "", "how_to_answer": "tie to a specific resume item"}}],
    "questions_to_ask_them": [""]
  }},
  "news": [
    {{"date": "YYYY-MM-DD", "headline": "", "url": "", "why_it_matters": "one line for a job seeker"}}
  ],
  "product_overview": {{
    "summary": "2-3 sentences",
    "products": [{{"name": "", "what_it_does": ""}}],
    "customers": "who buys",
    "competitors": [""]
  }}
}}

Rules:
- open_roles: only roles the candidate realistically qualifies for (up to 8). {roles_rule}
- news: everything relevant to a job seeker published on or after {cutoff} (funding, layoffs, leadership changes, launches, M&A, earnings, hiring). Exact publication date required. Up to 10.
- interview_prep: 5-8 talking points, 8-10 questions, 3-5 questions to ask them.
- Scores must be grounded in the resume and the roles found."""


def analyze_company(api_key: str, resume: str, company: str, ats_jobs: list[dict]) -> tuple[dict, dict]:
    today = date.today()
    cutoff = today - timedelta(days=config.NEWS_WINDOW_DAYS)
    if ats_jobs:
        listing = "\n".join(
            f"- {j['title']} | {j['location']} | {j['url']}" for j in ats_jobs[: config.MAX_ATS_JOBS]
        )
        jobs_block = f"<job_board_listings>\nLive listings from the company's job board:\n{listing}\n</job_board_listings>"
        roles_rule = "Choose ONLY from <job_board_listings>; copy title, location, and url exactly."
    else:
        jobs_block = "No job-board listings were found."
        roles_rule = "Use web search for current openings (careers page, LinkedIn). Include only roles with a working URL."

    text, usage = _run(
        api_key,
        ANALYZE_SYSTEM.format(today=today.isoformat()),
        ANALYZE_PROMPT.format(
            company=company, resume=resume, jobs_block=jobs_block,
            roles_rule=roles_rule, cutoff=cutoff.isoformat(),
        ),
        config.MAX_SEARCHES_ANALYZE,
    )
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise AgentError("Unexpected response shape from Claude.")
    data["fit_total"] = _fit_total(data.get("fit", {}))
    data["news"] = _filter_news(data.get("news", []))
    return data, usage


SUGGEST_SYSTEM = """You are a career strategist. Today is {today}.
Use web search to confirm each company is active and hiring in the candidate's function.
Return ONLY one JSON object wrapped in <json></json> tags, no other prose."""

SUGGEST_PROMPT = """Suggest {n} companies that fit the candidate below. {focus}

<resume>
{resume}
</resume>

Return:
{{
  "candidate_summary": "one line: function, seniority, domains",
  "companies": [
    {{"name": "", "website": "", "why_fit": "2 lines tied to resume specifics", "likely_role": "role title to target"}}
  ]
}}
Prefer companies where the candidate's domain experience transfers directly. Do not suggest the candidate's current or past employers."""


def suggest_companies(api_key: str, resume: str, focus: str, n: int = 6) -> tuple[dict, dict]:
    focus_line = f"Preferences: {focus}" if focus.strip() else ""
    text, usage = _run(
        api_key,
        SUGGEST_SYSTEM.format(today=date.today().isoformat()),
        SUGGEST_PROMPT.format(n=n, focus=focus_line, resume=resume),
        config.MAX_SEARCHES_SUGGEST,
    )
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise AgentError("Unexpected response shape from Claude.")
    return data, usage
