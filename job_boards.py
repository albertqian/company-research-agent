"""Pull open roles from public Greenhouse, Lever, and Ashby job-board APIs.

These APIs are free and need no key. If a company does not use one of them,
the agent falls back to web search for open roles.
"""
import re

import requests

TIMEOUT = 10


def _slug_candidates(company: str, override: str | None) -> list[str]:
    if override:
        return [override.strip().lower()]
    base = company.lower().strip()
    base = re.sub(r"\b(inc|llc|corp|corporation|co|ltd)\.?$", "", base).strip()
    joined = re.sub(r"[^a-z0-9]", "", base)
    hyphen = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    out = []
    for s in (joined, hyphen):
        if s and s not in out:
            out.append(s)
    return out


def _greenhouse(slug: str) -> list[dict]:
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    return [
        {"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
         "url": j.get("absolute_url", ""), "source": "Greenhouse"}
        for j in r.json().get("jobs", [])
    ]


def _lever(slug: str) -> list[dict]:
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=TIMEOUT)
    if r.status_code != 200 or not isinstance(r.json(), list):
        return []
    return [
        {"title": j.get("text", ""), "location": (j.get("categories") or {}).get("location", ""),
         "url": j.get("hostedUrl", ""), "source": "Lever"}
        for j in r.json()
    ]


def _ashby(slug: str) -> list[dict]:
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    return [
        {"title": j.get("title", ""), "location": j.get("location", ""),
         "url": j.get("jobUrl", ""), "source": "Ashby"}
        for j in r.json().get("jobs", [])
    ]


def fetch_jobs(company: str, slug_override: str | None = None) -> tuple[list[dict], str | None]:
    """Return (jobs, source_label). Empty list if no supported job board found."""
    for slug in _slug_candidates(company, slug_override):
        for fn in (_greenhouse, _lever, _ashby):
            try:
                jobs = fn(slug)
            except (requests.RequestException, ValueError):
                continue
            if jobs:
                return jobs, f"{jobs[0]['source']} ({slug})"
    return [], None
