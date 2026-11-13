"""Company Scout: suggests target companies from the candidate profile (no search)."""
import config
from agents.base import parse_json, profile_text, run_claude

SYSTEM = "You are a career strategist who knows the B2B and tech company landscape."

PROMPT = """Suggest {n} companies that fit this candidate. {focus}

<profile>{profile}</profile>

Return:
{{
  "companies": [{{"name": "", "website": "", "why_fit": "2 lines tied to profile specifics", "likely_role": ""}}]
}}
Prefer companies where the candidate's domain experience transfers directly and that are actively operating today.
Do not suggest any company in the profile's employers list."""


def run(api_key: str, profile: dict, focus: str = "") -> tuple[dict, dict]:
    text, usage = run_claude(
        api_key, "company_scout", SYSTEM,
        PROMPT.format(n=config.SUGGESTION_COUNT, profile=profile_text(profile),
                      focus=f"Preferences: {focus}" if focus.strip() else ""),
    )
    return parse_json(text, "Company Scout"), usage
