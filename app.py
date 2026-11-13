"""Company Research Agent: Streamlit UI."""
import hashlib
import hmac
from pathlib import Path

import streamlit as st

import config
from agent import AgentError, analyze_company, cost_of, suggest_companies
from job_boards import fetch_jobs
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
        if hmac.compare_digest(pw, st.secrets.get("APP_PASSWORD", "")) and pw:
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

st.session_state.setdefault("results", {})
st.session_state.setdefault("suggestions", None)
st.session_state.setdefault("session_cost", 0.0)


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
    except Exception as e:  # noqa: BLE001 - surface any parse failure to the user
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


# ---------- Rendering ----------
def render_analysis(d: dict, usage: dict, jobs_source: str | None) -> None:
    st.subheader(d.get("company", ""))
    if d.get("website"):
        st.caption(d["website"])

    tabs = st.tabs(["Fit score", "Open roles", "Interview prep", "Recent news", "Product overview"])

    with tabs[0]:
        st.metric("Overall fit", f"{d['fit_total']} / 100")
        labels = {"skills": "Skills match", "domain": "Domain match", "experience": "Years of experience"}
        cols = st.columns(3)
        for col, (key, label) in zip(cols, labels.items()):
            part = d.get("fit", {}).get(key, {})
            col.metric(f"{label} ({int(config.FIT_WEIGHTS[key] * 100)}%)", f"{part.get('score', 0)}")
            col.caption(part.get("reason", ""))

    with tabs[1]:
        st.caption(f"Source: {jobs_source or 'web search'} · Verify each role on the company careers page.")
        roles = d.get("open_roles", [])
        if not roles:
            st.info("No matching roles found.")
        for r in roles:
            title = f"[{r.get('title')}]({r['url']})" if r.get("url") else r.get("title", "")
            st.markdown(f"**{title}** · {r.get('location', '')}")
            st.markdown(f"✅ {r.get('why_qualified', '')}")
            if r.get("gaps"):
                st.markdown(f"⚠️ {r['gaps']}")
            st.divider()
        if d.get("roles_note"):
            st.caption(d["roles_note"])

    with tabs[2]:
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

    with tabs[3]:
        st.caption(f"Last {config.NEWS_WINDOW_DAYS} days only.")
        news = d.get("news", [])
        if not news:
            st.info("No dated news found in the window.")
        for n in news:
            head = f"[{n.get('headline')}]({n['url']})" if n.get("url") else n.get("headline", "")
            st.markdown(f"**{n.get('date')}** · {head}")
            st.caption(n.get("why_it_matters", ""))

    with tabs[4]:
        po = d.get("product_overview", {})
        st.write(po.get("summary", ""))
        for p in po.get("products", []):
            st.markdown(f"- **{p.get('name', '')}**: {p.get('what_it_does', '')}")
        if po.get("customers"):
            st.markdown(f"**Customers:** {po['customers']}")
        if po.get("competitors"):
            st.markdown(f"**Competitors:** {', '.join(po['competitors'])}")

    st.caption(
        f"Run cost (est.): ${cost_of(usage):.3f} · {usage['input_tokens']:,} in / "
        f"{usage['output_tokens']:,} out tokens · {usage['searches']} searches"
    )


def run_analysis(company: str, slug: str | None = None) -> None:
    key = f"{resume_hash}:{company.lower().strip()}:{slug or ''}"
    if key not in st.session_state.results:
        with st.spinner(f"Researching {company}…"):
            jobs, source = fetch_jobs(company, slug)
            try:
                data, usage = analyze_company(API_KEY, resume_text, company, jobs)
            except AgentError as e:
                st.error(str(e))
                return
        st.session_state.results[key] = (data, usage, source)
        st.session_state.session_cost += cost_of(usage)
    data, usage, source = st.session_state.results[key]
    render_analysis(data, usage, source)


# ---------- Main ----------
st.title("🔎 Company Research Agent")
mode_search, mode_suggest = st.tabs(["Search a company", "Suggest companies"])

with mode_search:
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

with mode_suggest:
    with st.form("suggest"):
        focus = st.text_input("Preferences (optional)", placeholder="e.g. remote, Series B+, AI/analytics, LA area")
        go_s = st.form_submit_button("Suggest companies")
    if go_s:
        with st.spinner("Finding companies…"):
            try:
                data, usage = suggest_companies(API_KEY, resume_text, focus)
                st.session_state.suggestions = (data, usage)
                st.session_state.session_cost += cost_of(usage)
            except AgentError as e:
                st.error(str(e))
    if st.session_state.suggestions:
        data, usage = st.session_state.suggestions
        st.caption(data.get("candidate_summary", ""))
        for i, c in enumerate(data.get("companies", [])):
            with st.container(border=True):
                st.markdown(f"**{c.get('name', '')}** · {c.get('website', '')}")
                st.write(c.get("why_fit", ""))
                st.caption(f"Target role: {c.get('likely_role', '')}")
                st.button(
                    f"Research {c.get('name', '')}", key=f"sug_{i}",
                    on_click=lambda name=c.get("name", ""): st.session_state.update(
                        active_company=(name, None), picked=name),
                )
        if st.session_state.get("picked"):
            st.success(f"Researching {st.session_state.picked}: open the **Search a company** tab.")
        st.caption(f"Run cost (est.): ${cost_of(usage):.3f}")

spend_slot.caption(f"Session spend (est.): **${st.session_state.session_cost:.3f}**")
