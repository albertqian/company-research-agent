# Job Search Prep Agent

A password-protected Streamlit app that turns a resume into interview-ready company prep. A main agent (plain Python) runs focused Claude Haiku sub-agents, several of them in parallel. News and job postings come from free sources; only one paid web search runs per company.

## How it works

**1. Submit a resume → Analyze resume**
- **Resume Profiler** turns the resume into a compact profile: headline, years, seniority, domains, skills, achievements. Every other sub-agent uses this profile instead of the full resume, which keeps token costs down.
- **Company Scout** suggests 8 target companies. Companies with a live Greenhouse, Lever or Ashby job board are marked 🟢 and listed first.

**2. Research a company** (from a suggestion or by name)
```
 parallel:  Product Researcher (1 web search)
            job board → Role Matcher
            Google News RSS → News Ranker
 then:      Fit Scorer
 then:      Interview Coach
```
- **Fit score (0–100):** skills match 50%, domain match 30%, years of experience 20%, plus gaps to prepare for.
- **Best-fit roles:** up to 3 job-board postings that match strongly (≥ 75). Hidden if none qualify. Each has **Prep for this role**.
- **Interview prep:** talking points, likely questions, answers for each gap, questions to ask them.
- **Product news:** top 5 product news items from the last 30 days.
- **Product overview:** products, customers, competitors, positioning.

**3. Paste a job description** — for Workday or other career sites (e.g. Salesforce). Same analysis, with the fit score measured against the pasted posting.

Each run has a cost expander that breaks the cost down by sub-agent.

## Cost (estimates, Haiku)
| Action | Approx. cost |
|---|---|
| Analyze resume (profile + suggestions) | ~$0.015 |
| Company research | ~$0.06–0.07 |
| Pasted job description | ~$0.06 |
| Prep for one role | ~$0.01–0.02 |

---

## Deploy

### 1. API key
1. **console.anthropic.com** → **API Keys** → **Create Key** → copy it.
2. **Settings → Limits** → set a monthly spend limit.

### 2. GitHub (private repo)
1. **github.com** → **+** → **New repository** → `company-research-agent` → **Private** → **Create repository**.
2. Click **uploading an existing file**, drag in all files and folders (including `agents/`), then **Commit changes**.
3. Hidden files (`.gitignore`, `.streamlit/secrets.toml.example`): create them with **Add file → Create new file**.

### 3. Streamlit Community Cloud
1. **share.streamlit.io** → **Create app** → repo `your-username/company-research-agent`, branch `main`, main file `app.py`.
2. **Advanced settings → Secrets**:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key"
   APP_PASSWORD = "your-password"
   ```
3. **Deploy**.

## Settings (`config.py`)
| Setting | Default | What it does |
|---|---|---|
| `AGENT_MODELS` | all Haiku | Model per sub-agent; e.g. set only `interview_coach` to Sonnet for deeper prep |
| `FIT_WEIGHTS` | 0.5 / 0.3 / 0.2 | Fit score weights |
| `NEWS_WINDOW_DAYS` / `NEWS_MAX_ITEMS` | 30 / 5 | News window and count |
| `ROLE_MIN_MATCH` / `ROLE_MAX_SHOWN` | 75 / 3 | Role match threshold and max roles shown |
| `SUGGESTION_COUNT` | 8 | Companies suggested per resume |
| `PRODUCT_MAX_SEARCHES` | 1 | Paid web searches per company |
| `PRICE_*` | Haiku rates | Used only for the cost display; verify at claude.com/pricing |

## Known limits
- **Roles** come only from Greenhouse, Lever and Ashby. For Workday or custom sites, use **Paste a job description**. If roles look missing, enter the job board slug (e.g. `highspot` from `jobs.lever.co/highspot`).
- **News** comes from the free Google News RSS feed. It has no official guarantee and may sometimes block cloud servers; the news tab then shows "No product news."
- **Company Scout** works from the model's own knowledge without searching, so a suggestion may occasionally be out of date. The 🟢 badge confirms a live job board.

## Files
```
app.py                       Streamlit UI and password gate
orchestrator.py              Main agent: runs sub-agents in order / in parallel
agents/base.py               Shared Claude call, JSON parsing, cost math
agents/resume_profiler.py    Resume → structured profile
agents/company_scout.py      Target-company suggestions
agents/role_matcher.py       Best-fit job-board postings
agents/product_researcher.py Product overview (1 web search)
agents/news_ranker.py        Top product news
agents/fit_scorer.py         Skills / domain / experience scores
agents/interview_coach.py    Company prep + role-specific prep
job_boards.py                Free Greenhouse / Lever / Ashby postings
news.py                      Free Google News RSS
resume_parser.py             .docx / .pdf → text
config.py                    All settings
samples/                     Default sample resume
```
