"""Free job postings from public Greenhouse, Lever, and Ashby job-board APIs.

No API key needed. If a company is not on one of these boards, no roles are shown.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor

import requests

TIMEOUT = 10


def _clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug_candidates(company: str, override: str | None = None) -> list[str]:
    if override:
        return [override.strip().lower()]
    base = company.lower().strip()
    base = re.sub(r"\b(inc|llc|corp|corporation|co|ltd)\.?$", "", base).strip()
    out = []
    for s in (re.sub(r"[^a-z0-9]", "", base), re.sub(r"[^a-z0-9]+", "-", base).strip("-")):
        if s and s not in out:
            out.append(s)
    return out


def _greenhouse(slug: str) -> list[dict]:
    r = requests.get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", timeout=TIMEOUT
    )
    if r.status_code != 200:
        return []
    return [
        {"title": j.get("title", ""), "location": (j.get("location") or {}).get("name", ""),
         "url": j.get("absolute_url", ""), "description": _clean(j.get("content", "")),
         "source": "Greenhouse"}
        for j in r.json().get("jobs", [])
    ]


def _lever(slug: str) -> list[dict]:
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", timeout=TIMEOUT)
    if r.status_code != 200 or not isinstance(r.json(), list):
        return []
    out = []
    for j in r.json():
        lists = " ".join(
            f"{li.get('text', '')}: {_clean(li.get('content', ''))}" for li in j.get("lists", [])
        )
        out.append({
            "title": j.get("text", ""), "location": (j.get("categories") or {}).get("location", ""),
            "url": j.get("hostedUrl", ""),
            "description": _clean(j.get("descriptionPlain", "")) + " " + lists,
            "source": "Lever",
        })
    return out


def _ashby(slug: str) -> list[dict]:
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    return [
        {"title": j.get("title", ""), "location": j.get("location", ""),
         "url": j.get("jobUrl", ""),
         "description": _clean(j.get("descriptionPlain") or j.get("descriptionHtml", "")),
         "source": "Ashby"}
        for j in r.json().get("jobs", [])
    ]


def fetch_jobs(company: str, slug_override: str | None = None) -> tuple[list[dict], str | None]:
    """Return (jobs, source_label). Empty list if no supported job board is found."""
    for slug in slug_candidates(company, slug_override):
        for fn in (_greenhouse, _lever, _ashby):
            try:
                jobs = fn(slug)
            except (requests.RequestException, ValueError):
                continue
            if jobs:
                return jobs, f"{jobs[0]['source']} ({slug})"
    return [], None


def has_job_board(companies: list[str]) -> dict[str, bool]:
    """Check several companies in parallel; True if a supported job board has postings."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = pool.map(lambda c: bool(fetch_jobs(c)[0]), companies)
    return dict(zip(companies, results))
