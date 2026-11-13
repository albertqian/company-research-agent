"""Main agent: plain Python that decides which sub-agents run, in what order, and in parallel.

Company run order:
  parallel:  Product Researcher | job board fetch -> Role Matcher | news fetch -> News Ranker
  then:      Fit Scorer      (needs product + roles)
  then:      Interview Coach (needs everything)
"""
from concurrent.futures import ThreadPoolExecutor

from agents import (company_scout, fit_scorer, interview_coach, news_ranker,
                    product_researcher, resume_profiler, role_matcher)
from agents.base import AgentError, new_usage
from job_boards import fetch_jobs, has_job_board
from news import fetch_news


def analyze_resume(api_key: str, resume: str, focus: str = "") -> dict:
    """Runs on resume submission: Resume Profiler, then Company Scout, then a free job-board check."""
    profile, u_profile = resume_profiler.run(api_key, resume)
    scout, u_scout = company_scout.run(api_key, profile, focus)
    companies = scout.get("companies", [])
    boards = has_job_board([c.get("name", "") for c in companies])
    for c in companies:
        c["job_board"] = boards.get(c.get("name", ""), False)
    companies.sort(key=lambda c: not c["job_board"])
    return {
        "profile": profile,
        "companies": companies,
        "usages": {"Resume Profiler": u_profile, "Company Scout": u_scout},
    }


def research_company(api_key: str, profile: dict, company: str,
                     slug: str | None = None, pasted_role: dict | None = None) -> dict:
    """Full company prep. If pasted_role is given, the job board is skipped and that role is used."""
    usages: dict[str, dict] = {}
    warnings: list[str] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_product = pool.submit(product_researcher.run, api_key, company)
        f_news_raw = pool.submit(fetch_news, company)
        f_jobs = None if pasted_role else pool.submit(fetch_jobs, company, slug)

        # Role Matcher (or the pasted role)
        if pasted_role:
            roles, roles_source = [pasted_role], "Pasted job description"
            f_match = None
        else:
            jobs, roles_source = f_jobs.result()
            f_match = pool.submit(role_matcher.run, api_key, profile, company, jobs)

        # News Ranker
        f_rank = pool.submit(news_ranker.run, api_key, company, f_news_raw.result())

        product, usages["Product Researcher"] = f_product.result()

        if f_match:
            try:
                roles, usages["Role Matcher"] = f_match.result()
            except AgentError as e:
                roles, usages["Role Matcher"] = [], new_usage()
                warnings.append(str(e))

        try:
            news, usages["News Ranker"] = f_rank.result()
        except AgentError as e:
            news, usages["News Ranker"] = [], new_usage()
            warnings.append(str(e))

    fit, usages["Fit Scorer"] = fit_scorer.run(api_key, profile, company, product, roles)
    prep, usages["Interview Coach"] = interview_coach.run_company(
        api_key, profile, company, product, fit, news, roles
    )

    return {
        "company": product.get("company") or company,
        "website": product.get("website", ""),
        "product": product,
        "roles": roles,
        "roles_source": roles_source,
        "news": news,
        "fit": fit,
        "prep": prep,
        "usages": usages,
        "warnings": warnings,
    }


def prep_for_role(api_key: str, profile: dict, company: str, role: dict) -> tuple[dict, dict]:
    data, usage = interview_coach.run_role(api_key, profile, company, role)
    return data, {"Interview Coach (role)": usage}
