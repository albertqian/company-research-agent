"""Company Research Agent: Streamlit UI."""
import hashlib
import hmac
from pathlib import Path

import streamlit as st

import config
from agent import (AgentError, add_usage, analyze_company, cost_of, match_roles,
                   role_prep, suggest_companies)
from job_boards import fetch_jobs, has_job_board
from news import fetch_news
from resume_parser import parse_resume

st.set_page_config(page_title="Company Research Agent", page_icon="🔎", layout="wide")

SAMPLE_RESUME = Path(__file__).parent / "samples" / "sample_resume.docx"


# ---------- Password gate ----------
def check_password() -> bool:
    if st.session_state.get("authed"):
        return True
    st.title("🔎 Company Research Agent")
    pw = st.text_input("Password", type="password")
    if st.button("Enter"):
        if pw and hmac.compare_digest(pw, st.secrets.get("APP_PASSWORD", "")):
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password.")
    return False


if not check_password():
    st.stop()

API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    st.error("ANTHROPIC_API_KEY is missing from Streamlit secrets.")
    st.stop()

for k, v in {"results": {}, "role_preps": {}, "suggestions": None, "session_cost": 0.0}.items():
    st.session_state.setdefault(k, v)


# ---------- Sidebar: resume ----------
with st.sidebar:
    st.header("Resume")
    upload = st.file_uploader("Upload .docx or .pdf", type=["docx", "pdf"])
    try:
        if upload:
            resume_text = parse_resume(upload.getvalue(), upload.name)
            st.caption(f"Using: {upload.name}")
        elif SAMPLE_RESUME.exists():
            resume_text = parse_resume(SAMPLE_RESUME.read_bytes(), SAMPLE_RESUME.name)
            st.caption("Using: sample resume")
        else:
            resume_text = ""
    except Exception as e:  # noqa: BLE001 - show any parse failure to the user
        st.error(f"Could not read resume: {e}")
        resume_text = ""
    if resume_text:
        with st.expander("Preview resume text"):
            st.text(resume_text[:3000])
    st.divider()
    st.caption(f"Model: `{config.MODEL}`")
    spend_slot = st.empty()

if not resume_text.strip():
    st.warning("Upload a resume to start.")
    st.stop()

resume_hash = hashlib.sha256(resume_text.encode()).hexdigest()[:12]


def usage_line(usage: dict) -> str:
    return (f"Run cost (est.): ${cost_of(usage):.3f} · {usage['input_tokens']:,} in / "
            f"{usage['output_tokens']:,} out tokens · {usage['searches']} searches")


# ---------- Role prep ----------
def render_role_prep(company: str, role: dict) -> None:
    key = f"{resume_hash}:{role['id']}"
    if st.button("Prep for this role", key=f"prep_{key}"):
        with st.spinner("Building role prep…"):
            try:
                data, usage = role_prep(API_KEY, resume_text, company, role)
                st.session_state.role_preps[key] = (data, usage)
                st.session_state.session_cost += cost_of(usage)
            except AgentError as e:
                st.error(str(e))
    if key not in st.session_state.role_preps:
        return
    data, usage = st.session_state.role_preps[key]
    icons = {"strong": "✅", "partial": "🟡", "gap": "❌"}
    st.markdown("**Requirements vs. resume**")
    for r in data.get("requirement_map", []):
        st.markdown(f"{icons.get(r.get('strength'), '•')} **{r.get('requirement', '')}**: {r.get('evidence', '')}")
    if data.get("gap_plan"):
        st.markdown("**Handling gaps**")
        for g in data["gap_plan"]:
            st.markdown(f"- {g}")
    st.markdown("**Role-specific questions**")
    for q in data.get("questions", []):
        with st.expander(q.get("question", "")):
            st.write(q.get("how_to_answer", ""))
    if data.get("pitch"):
        st.markdown("**Your 60-second pitch**")
        st.info(data["pitch"])
    st.caption(usage_line(usage))


# ---------- Company analysis ----------
def render_analysis(company: str, d: dict, roles: list[dict], usage: dict,
                    roles_label: str = "Best-fit roles") -> None:
    st.subheader(d.get("company", company))
    if d.get("website"):
        st.caption(d["website"])

    names = ["Fit score"] + ([roles_label] if roles else []) + \
            ["Interview prep", "Product news", "Product overview"]
    tabs = dict(zip(names, st.tabs(names)))

    with tabs["Fit score"]:
        st.metric("Overall fit", f"{d['fit_total']} / 100")
        labels = {"skills": "Skills match", "domain": "Domain match", "experience": "Years of experience"}
        for col, (key, label) in zip(st.columns(3), labels.items()):
            part = d.get("fit", {}).get(key, {})
            col.metric(f"{label} ({int(config.FIT_WEIGHTS[key] * 100)}%)", f"{part.get('score', 0)}")
            col.caption(part.get("reason", ""))

    if roles:
        with tabs[roles_label]:
            for r in roles:
                with st.container(border=True):
                    title = f"[{r['title']}]({r['url']})" if r["url"].startswith("http") else r["title"]
                    meta = " · ".join(x for x in (r["location"], f"match {r['match']}" if r.get("match") else "") if x)
                    st.markdown(f"**{title}**" + (f" · {meta}" if meta else ""))
                    if r.get("reason"):
                        st.caption(r["reason"])
                    render_role_prep(company, r)

    with tabs["Interview prep"]:
        prep = d.get("interview_prep", {})
        st.markdown("#### Talking points")
        for t in prep.get("talking_points", []):
            st.markdown(f"- {t}")
        st.markdown("#### Likely questions")
        for q in prep.get("questions", []):
            with st.expander(q.get("question", "")):
                st.write(q.get("how_to_answer", ""))
        st.markdown("#### Questions to ask them")
        for q in prep.get("questions_to_ask_them", []):
            st.markdown(f"- {q}")

    with tabs["Product news"]:
        st.caption(f"Most important product news, last {config.NEWS_WINDOW_DAYS} days.")
        if not d.get("news"):
            st.info("No product news in this window.")
        for n in d.get("news", []):
            st.markdown(f"**{n['date']}** · [{n['headline']}]({n['url']})")
            st.caption(n.get("why_it_matters", ""))

    with tabs["Product overview"]:
        po = d.get("product_overview", {})
        st.write(po.get("summary", ""))
        for p in po.get("products", []):
            st.markdown(f"- **{p.get('name', '')}**: {p.get('what_it_does', '')}")
        if po.get("customers"):
            st.markdown(f"**Customers:** {po['customers']}")
        if po.get("competitors"):
            st.markdown(f"**Competitors:** {', '.join(po['competitors'])}")

    st.caption(usage_line(usage))


def run_analysis(company: str, slug: str | None) -> None:
    key = f"{resume_hash}:{company.lower()}:{slug or ''}"
    if key not in st.session_state.results:
        with st.spinner(f"Researching {company}…"):
            jobs, _ = fetch_jobs(company, slug)
            news = fetch_news(company)
            try:
                roles, u1 = match_roles(API_KEY, resume_text, company, jobs)
                roles = [{**r, "id": r["url"]} for r in roles]
                data, u2 = analyze_company(API_KEY, resume_text, company, roles, news)
            except AgentError as e:
                st.error(str(e))
                return
        usage = add_usage(u1, u2)
        st.session_state.results[key] = (data, roles, usage)
        st.session_state.session_cost += cost_of(usage)
    data, roles, usage = st.session_state.results[key]
    render_analysis(company, data, roles, usage)


def run_pasted(company: str, title: str, url: str, jd: str) -> None:
    jd_hash = hashlib.sha256(jd.encode()).hexdigest()[:12]
    key = f"{resume_hash}:paste:{jd_hash}"
    role = {"id": f"paste:{jd_hash}", "title": title or "Pasted role", "location": "",
            "url": url, "description": jd, "source": "Pasted", "match": None, "reason": ""}
    if key not in st.session_state.results:
        with st.spinner(f"Analyzing {title or 'role'} at {company}…"):
            news = fetch_news(company)
            try:
                data, usage = analyze_company(API_KEY, resume_text, company, [role], news)
            except AgentError as e:
                st.error(str(e))
                return
        st.session_state.results[key] = (data, [role], usage)
        st.session_state.session_cost += cost_of(usage)
    data, roles, usage = st.session_state.results[key]
    render_analysis(company, data, roles, usage, roles_label="Your role")


# ---------- Main ----------
st.title("🔎 Company Research Agent")
tab_search, tab_paste, tab_suggest = st.tabs(["Search a company", "Paste a job description", "Suggest companies"])

with tab_search:
    with st.form("search"):
        c1, c2 = st.columns([3, 2])
        company = c1.text_input("Company name", placeholder="e.g. Gong")
        slug = c2.text_input(
            "Job board slug (optional)",
            help="The name in the company's Greenhouse/Lever/Ashby URL, e.g. 'gong' "
                 "from boards.greenhouse.io/gong. Leave blank to auto-detect.",
        )
        go = st.form_submit_button("Research")
    if go and company.strip():
        st.session_state.active_company = (company.strip(), slug.strip() or None)
    if st.session_state.get("active_company"):
        run_analysis(*st.session_state.active_company)

with tab_paste:
    st.caption("For roles on Workday or other career sites (e.g. Salesforce). "
               "The fit score is measured against this exact posting.")
    with st.form("paste"):
        p1, p2 = st.columns(2)
        p_company = p1.text_input("Company name", placeholder="e.g. Salesforce")
        p_title = p2.text_input("Job title", placeholder="e.g. Director, Product Marketing")
        p_url = st.text_input("Job posting link (optional)")
        p_jd = st.text_area("Job description", height=300, placeholder="Paste the full job description here")
        go_p = st.form_submit_button("Analyze this role")
    if go_p:
        if not p_company.strip() or len(p_jd.strip()) < 200:
            st.warning("Add the company name and the full job description (at least a few paragraphs).")
        else:
            st.session_state.active_paste = (p_company.strip(), p_title.strip(), p_url.strip(), p_jd.strip())
    if st.session_state.get("active_paste"):
        run_pasted(*st.session_state.active_paste)

with tab_suggest:
    with st.form("suggest"):
        focus = st.text_input("Preferences (optional)", placeholder="e.g. remote, Series B+, AI/analytics, LA area")
        go_s = st.form_submit_button("Suggest companies")
    if go_s:
        with st.spinner("Finding companies…"):
            try:
                data, usage = suggest_companies(API_KEY, resume_text, focus)
            except AgentError as e:
                st.error(str(e))
            else:
                boards = has_job_board([c.get("name", "") for c in data.get("companies", [])])
                for c in data.get("companies", []):
                    c["job_board"] = boards.get(c.get("name", ""), False)
                data["companies"].sort(key=lambda c: not c["job_board"])
                st.session_state.suggestions = (data, usage)
                st.session_state.session_cost += cost_of(usage)
    if st.session_state.suggestions:
        data, usage = st.session_state.suggestions
        st.caption(data.get("candidate_summary", ""))
        for i, c in enumerate(data.get("companies", [])):
            with st.container(border=True):
                badge = " · 🟢 job board found" if c.get("job_board") else ""
                st.markdown(f"**{c.get('name', '')}** · {c.get('website', '')}{badge}")
                st.write(c.get("why_fit", ""))
                st.caption(f"Target role: {c.get('likely_role', '')}")
                st.button(
                    f"Research {c.get('name', '')}", key=f"sug_{i}",
                    on_click=lambda name=c.get("name", ""): st.session_state.update(
                        active_company=(name, None), picked=name),
                )
        if st.session_state.get("picked"):
            st.success(f"Researching {st.session_state.picked}: open the **Search a company** tab.")
        st.caption(usage_line(usage))

spend_slot.caption(f"Session spend (est.): **${st.session_state.session_cost:.3f}**")
