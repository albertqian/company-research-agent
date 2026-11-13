"""Job Search Prep Agent: Streamlit UI on top of the orchestrator and its sub-agents."""
import hashlib
import hmac
from pathlib import Path

import streamlit as st

import config
from agents import resume_profiler
from agents.base import AgentError, add_usage, cost_of
from orchestrator import analyze_resume, prep_for_role, research_company
from resume_parser import parse_resume

st.set_page_config(page_title="Job Search Prep Agent", page_icon="🔎", layout="wide")

SAMPLE_RESUME = Path(__file__).parent / "samples" / "sample_resume.docx"


# ---------- Password gate ----------
def check_password() -> bool:
    if st.session_state.get("authed"):
        return True
    st.title("🔎 Job Search Prep Agent")
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

for k, v in {"analyses": {}, "profiles": {}, "results": {}, "role_preps": {}, "session_cost": 0.0}.items():
    st.session_state.setdefault(k, v)


def charge(usages: dict) -> None:
    st.session_state.session_cost += cost_of(add_usage(*usages.values()))


def cost_breakdown(usages: dict) -> None:
    total = add_usage(*usages.values())
    with st.expander(f"Run cost (est.): ${cost_of(total):.3f} · {total['searches']} searches"):
        for name, u in usages.items():
            st.caption(f"**{name}**: ${cost_of(u):.4f} · {u['input_tokens']:,} in / "
                       f"{u['output_tokens']:,} out · {u['searches']} searches")


# ---------- Sidebar: resume submission ----------
with st.sidebar:
    st.header("1. Resume")
    upload = st.file_uploader("Upload .docx or .pdf", type=["docx", "pdf"])
    try:
        if upload:
            resume_text, resume_label = parse_resume(upload.getvalue(), upload.name), upload.name
        elif SAMPLE_RESUME.exists():
            resume_text, resume_label = parse_resume(SAMPLE_RESUME.read_bytes(), SAMPLE_RESUME.name), "sample resume"
        else:
            resume_text, resume_label = "", ""
    except Exception as e:  # noqa: BLE001 - show any parse failure to the user
        st.error(f"Could not read resume: {e}")
        resume_text, resume_label = "", ""
    if resume_label:
        st.caption(f"Using: {resume_label}")
    focus = st.text_input("Preferences (optional)", placeholder="e.g. remote, AI/analytics, Series B+")
    analyze_clicked = st.button("Analyze resume", type="primary", use_container_width=True,
                                disabled=not resume_text.strip())
    st.divider()
    st.caption(f"Default model: `{config.DEFAULT_MODEL}`")
    spend_slot = st.empty()

if not resume_text.strip():
    st.title("🔎 Job Search Prep Agent")
    st.warning("Upload a resume to start.")
    st.stop()

resume_hash = hashlib.sha256(resume_text.encode()).hexdigest()[:12]

if analyze_clicked:
    with st.spinner("Resume Profiler and Company Scout are working…"):
        try:
            analysis = analyze_resume(API_KEY, resume_text, focus)
        except AgentError as e:
            st.error(str(e))
        else:
            st.session_state.analyses[resume_hash] = analysis
            st.session_state.profiles[resume_hash] = analysis["profile"]
            charge(analysis["usages"])


def get_profile() -> dict | None:
    """Profile for the current resume; runs only the Resume Profiler if needed."""
    if resume_hash not in st.session_state.profiles:
        with st.spinner("Resume Profiler is reading the resume…"):
            try:
                profile, usage = resume_profiler.run(API_KEY, resume_text)
            except AgentError as e:
                st.error(str(e))
                return None
        st.session_state.profiles[resume_hash] = profile
        charge({"Resume Profiler": usage})
    return st.session_state.profiles[resume_hash]


# ---------- Rendering ----------
def render_profile(analysis: dict) -> None:
    p = analysis["profile"]
    st.subheader(p.get("headline", "Candidate profile"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Years of experience", p.get("years_experience", "-"))
    c2.metric("Seniority", p.get("seniority", "-"))
    c3.metric("Domains", len(p.get("domains", [])))
    st.markdown("**Domains:** " + ", ".join(p.get("domains", [])))
    st.markdown("**Skills:** " + ", ".join(p.get("skills", [])))
    with st.expander("Top achievements"):
        for a in p.get("achievements", []):
            metric = f" ({a['metric']})" if a.get("metric") else ""
            st.markdown(f"- {a.get('what', '')}{metric} · {a.get('where', '')}")

    st.markdown("### Suggested companies")
    for i, c in enumerate(analysis["companies"]):
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
        st.success(f"Researching {st.session_state.picked}: open the **Research a company** tab.")
    cost_breakdown(analysis["usages"])


def render_role_prep(profile: dict, company: str, role: dict) -> None:
    key = f"{resume_hash}:{role['id']}"
    if st.button("Prep for this role", key=f"prep_{key}"):
        with st.spinner("Interview Coach is building role prep…"):
            try:
                data, usages = prep_for_role(API_KEY, profile, company, role)
            except AgentError as e:
                st.error(str(e))
            else:
                st.session_state.role_preps[key] = (data, usages)
                charge(usages)
    if key not in st.session_state.role_preps:
        return
    data, usages = st.session_state.role_preps[key]
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
    cost_breakdown(usages)


def render_research(profile: dict, r: dict, roles_label: str) -> None:
    st.subheader(r["company"])
    if r["website"]:
        st.caption(r["website"])
    for w in r["warnings"]:
        st.warning(w)

    roles = r["roles"]
    names = ["Fit score"] + ([roles_label] if roles else []) + \
            ["Interview prep", "Product news", "Product overview"]
    tabs = dict(zip(names, st.tabs(names)))

    with tabs["Fit score"]:
        fit = r["fit"]
        st.metric("Overall fit", f"{fit['total']} / 100")
        labels = {"skills": "Skills match", "domain": "Domain match", "experience": "Years of experience"}
        for col, (key, label) in zip(st.columns(3), labels.items()):
            part = fit.get(key, {})
            col.metric(f"{label} ({int(config.FIT_WEIGHTS[key] * 100)}%)", f"{part.get('score', 0)}")
            col.caption(part.get("reason", ""))
        if fit.get("gaps"):
            st.markdown("**Gaps to prepare for**")
            for g in fit["gaps"]:
                st.markdown(f"- {g}")

    if roles:
        with tabs[roles_label]:
            st.caption(f"Source: {r['roles_source']}")
            for role in roles:
                with st.container(border=True):
                    title = f"[{role['title']}]({role['url']})" if role["url"].startswith("http") else role["title"]
                    meta = " · ".join(x for x in (role.get("location", ""),
                                                  f"match {role['match']}" if role.get("match") else "") if x)
                    st.markdown(f"**{title}**" + (f" · {meta}" if meta else ""))
                    if role.get("reason"):
                        st.caption(role["reason"])
                    render_role_prep(profile, r["company"], role)

    with tabs["Interview prep"]:
        prep = r["prep"]
        st.markdown("#### Talking points")
        for t in prep.get("talking_points", []):
            st.markdown(f"- {t}")
        st.markdown("#### Likely questions")
        for q in prep.get("questions", []):
            with st.expander(q.get("question", "")):
                st.write(q.get("how_to_answer", ""))
        if prep.get("gap_answers"):
            st.markdown("#### Addressing gaps")
            for g in prep["gap_answers"]:
                st.markdown(f"- **{g.get('gap', '')}**: {g.get('how_to_address', '')}")
        st.markdown("#### Questions to ask them")
        for q in prep.get("questions_to_ask_them", []):
            st.markdown(f"- {q}")

    with tabs["Product news"]:
        st.caption(f"Most important product news, last {config.NEWS_WINDOW_DAYS} days.")
        if not r["news"]:
            st.info("No product news in this window.")
        for n in r["news"]:
            st.markdown(f"**{n['date']}** · [{n['headline']}]({n['url']})")
            st.caption(n.get("why_it_matters", ""))

    with tabs["Product overview"]:
        po = r["product"]
        st.write(po.get("summary", ""))
        if po.get("positioning"):
            st.markdown(f"**Positioning:** {po['positioning']}")
        for p in po.get("products", []):
            st.markdown(f"- **{p.get('name', '')}**: {p.get('what_it_does', '')}")
        if po.get("customers"):
            st.markdown(f"**Customers:** {po['customers']}")
        if po.get("competitors"):
            st.markdown(f"**Competitors:** {', '.join(po['competitors'])}")

    cost_breakdown(r["usages"])


def run_research(key: str, company: str, slug: str | None = None, pasted_role: dict | None = None,
                 roles_label: str = "Best-fit roles") -> None:
    profile = get_profile()
    if profile is None:
        return
    if key not in st.session_state.results:
        with st.spinner(f"Sub-agents researching {company}…"):
            try:
                result = research_company(API_KEY, profile, company, slug, pasted_role)
            except AgentError as e:
                st.error(str(e))
                return
        st.session_state.results[key] = result
        charge(result["usages"])
    render_research(profile, st.session_state.results[key], roles_label)


# ---------- Main ----------
st.title("🔎 Job Search Prep Agent")
tab_profile, tab_company, tab_paste = st.tabs(
    ["Profile & target companies", "Research a company", "Paste a job description"]
)

with tab_profile:
    if resume_hash in st.session_state.analyses:
        render_profile(st.session_state.analyses[resume_hash])
    else:
        st.info("Click **Analyze resume** in the sidebar. The Resume Profiler reads the resume, "
                "then the Company Scout suggests target companies.")

with tab_company:
    with st.form("search"):
        c1, c2 = st.columns([3, 2])
        company = c1.text_input("Company name", placeholder="e.g. Highspot")
        slug = c2.text_input(
            "Job board slug (optional)",
            help="The name in the company's Greenhouse/Lever/Ashby URL, e.g. 'highspot' "
                 "from jobs.lever.co/highspot. Leave blank to auto-detect.",
        )
        go = st.form_submit_button("Research")
    if go and company.strip():
        st.session_state.active_company = (company.strip(), slug.strip() or None)
    if st.session_state.get("active_company"):
        name, s = st.session_state.active_company
        run_research(f"{resume_hash}:{name.lower()}:{s or ''}", name, slug=s)

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
        pc, pt, pu, pj = st.session_state.active_paste
        jd_hash = hashlib.sha256(pj.encode()).hexdigest()[:12]
        role = {"id": f"paste:{jd_hash}", "title": pt or "Pasted role", "location": "", "url": pu,
                "description": pj, "source": "Pasted", "match": None, "reason": ""}
        run_research(f"{resume_hash}:paste:{jd_hash}", pc, pasted_role=role, roles_label="Your role")

spend_slot.caption(f"Session spend (est.): **${st.session_state.session_cost:.3f}**")
