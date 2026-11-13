"""Interview Coach: company-level prep, plus role-specific prep on demand (no search)."""
import json

import config
from agents.base import parse_json, profile_text, run_claude

SYSTEM = "You are an interview coach. Tie every answer to specific profile achievements. Never invent facts."

COMPANY_PROMPT = """Prepare this candidate to interview at **{company}**.

<profile>{profile}</profile>
<product>{product}</product>
<fit>{fit}</fit>
<news>{news}</news>
<target_roles>{roles}</target_roles>

Return:
{{
  "talking_points": ["profile achievement mapped to the company's needs"],
  "questions": [{{"question": "", "how_to_answer": "tie to a specific achievement"}}],
  "gap_answers": [{{"gap": "", "how_to_address": ""}}],
  "questions_to_ask_them": [""]
}}
5 talking points, 8 questions (mix of role, product, and behavioral; reference the news where relevant),
one gap_answer per fit gap, 3 questions to ask them."""

ROLE_PROMPT = """Prepare this candidate for the specific role below at {company}.

<profile>{profile}</profile>
<job_description title="{title}">
{jd}
</job_description>

Return:
{{
  "requirement_map": [{{"requirement": "from the JD", "evidence": "matching profile item", "strength": "strong|partial|gap"}}],
  "gap_plan": ["how to address each gap in the interview"],
  "questions": [{{"question": "", "how_to_answer": "tie to a specific achievement"}}],
  "pitch": "60-second 'why me for this role' answer in first person"
}}
6-8 requirements, 8 questions."""


def run_company(api_key: str, profile: dict, company: str, product: dict, fit: dict,
                news: list[dict], roles: list[dict]) -> tuple[dict, dict]:
    news_lines = [f"{n['date']}: {n['headline']}" for n in news]
    role_titles = [r["title"] for r in roles]
    text, usage = run_claude(
        api_key, "interview_coach", SYSTEM,
        COMPANY_PROMPT.format(
            company=company, profile=profile_text(profile),
            product=json.dumps(product, ensure_ascii=False),
            fit=json.dumps({k: fit.get(k) for k in ("skills", "domain", "experience", "gaps")}, ensure_ascii=False),
            news=json.dumps(news_lines, ensure_ascii=False),
            roles=json.dumps(role_titles, ensure_ascii=False),
        ),
    )
    return parse_json(text, "Interview Coach"), usage


def run_role(api_key: str, profile: dict, company: str, role: dict) -> tuple[dict, dict]:
    text, usage = run_claude(
        api_key, "interview_coach", SYSTEM,
        ROLE_PROMPT.format(company=company, profile=profile_text(profile), title=role["title"],
                           jd=role["description"][: config.JD_CHARS * 2]),
    )
    return parse_json(text, "Interview Coach"), usage
