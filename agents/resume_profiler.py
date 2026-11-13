"""Resume Profiler: turns a raw resume into a compact structured profile (runs once per resume)."""
from agents.base import parse_json, run_claude

SYSTEM = "You extract structured candidate profiles from resumes. Use only facts in the resume."

PROMPT = """<resume>
{resume}
</resume>

Return:
{{
  "headline": "one line: current/most recent title, function, seniority",
  "years_experience": 0,
  "seniority": "IC | manager | senior manager | director | VP+",
  "functions": ["e.g. product marketing"],
  "domains": ["industries / markets / product categories"],
  "skills": ["hard and functional skills, max 20"],
  "tools": ["software / platforms named"],
  "achievements": [{{"what": "short", "metric": "number if stated, else empty", "where": "company"}}],
  "employers": ["company names, most recent first"],
  "education": ["degree, school"]
}}
Max 12 achievements, strongest first. Keep each field short."""


def run(api_key: str, resume: str) -> tuple[dict, dict]:
    text, usage = run_claude(api_key, "resume_profiler", SYSTEM, PROMPT.format(resume=resume))
    return parse_json(text, "Resume Profiler"), usage
