"""Fit Scorer: skills / domain / experience scores; the weighted total is computed in code."""
import json

import config
from agents.base import parse_json, profile_text, run_claude

SYSTEM = "You score candidate-company fit with a strict rubric. Ground every score in the inputs."

PROMPT = """<profile>{profile}</profile>

<company name="{company}">{product}</company>

{roles_block}

Score 0-100:
- skills: profile skills vs skills the roles need
- domain: profile domains/markets vs the company's market and product category
- experience: profile years and seniority vs years/seniority required
{basis}

Return:
{{
  "skills":     {{"score": 0, "reason": "one line"}},
  "domain":     {{"score": 0, "reason": "one line"}},
  "experience": {{"score": 0, "reason": "one line"}},
  "gaps": ["specific gaps the candidate should prepare to address, max 4"]
}}"""


def roles_block(roles: list[dict]) -> str:
    if not roles:
        return "No job descriptions available."
    return "<job_descriptions>\n" + "\n\n".join(
        f"### {r['title']} {('(' + r['location'] + ')') if r.get('location') else ''}\n"
        f"{r['description'][: config.JD_CHARS]}"
        for r in roles
    ) + "\n</job_descriptions>"


def total(fit: dict) -> int:
    score = 0.0
    for key, weight in config.FIT_WEIGHTS.items():
        try:
            score += max(0.0, min(100.0, float(fit.get(key, {}).get("score", 0)))) * weight
        except (TypeError, ValueError):
            pass
    return round(score)


def run(api_key: str, profile: dict, company: str, product: dict, roles: list[dict]) -> tuple[dict, dict]:
    basis = ("Score against the job descriptions above." if roles
             else "No postings given: score against the roles this candidate would target at this company.")
    text, usage = run_claude(
        api_key, "fit_scorer", SYSTEM,
        PROMPT.format(profile=profile_text(profile), company=company,
                      product=json.dumps(product, ensure_ascii=False), roles_block=roles_block(roles),
                      basis=basis),
    )
    fit = parse_json(text, "Fit Scorer")
    fit["total"] = total(fit)
    return fit, usage
