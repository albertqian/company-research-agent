# Company Research Agent

A password-protected Streamlit app that prepares job seekers for a specific company, using Claude Haiku. It is built to keep costs low: news and job postings come from free sources, and only the product overview uses a paid web search (at most 1 per run).

**For any company it returns:**
- **Fit score (0–100):** skills match 50%, domain match 30%, years of experience 20%. Scored against the real job descriptions when the company posts on a supported job board.
- **Best-fit roles:** up to 3 postings from the company's free Greenhouse, Lever or Ashby job board, only when the candidate is a strong fit (match ≥ 75). If none fit, the tab is hidden. Each role has a **Prep for this role** button that maps the job's requirements to the resume, plans for gaps, and builds role-specific questions and a 60-second pitch.
- **Interview prep:** talking points, likely questions with how to answer, and questions to ask them.
- **Product news:** the top 5 product news items from the last 30 days, taken from the free Google News feed and ranked by Claude.
- **Product overview:** products, customers, competitors.

**Paste a job description:** for roles on Workday or other career sites (e.g. Salesforce). Paste the job description to get the same analysis, with the fit score measured against that exact posting, plus **Prep for this role**.

**Suggest mode:** proposes 8 companies from the resume. Companies with a live job board are marked 🟢 and listed first.

## Cost (estimates)
| Action | Approx. cost |
|---|---|
| Company research | $0.05–0.08 |
| Pasted job description analysis | $0.05–0.08 |
| Prep for one role | $0.02–0.03 |
| Suggestions | $0.01–0.02 |

Each run shows its cost, and the sidebar shows the session total. Opening the same company again in a session doesn't charge twice.

---

## Deploy

### 1. API key
1. **console.anthropic.com** → **API Keys** → **Create Key** → copy it.
2. **Settings → Limits** → set a monthly spend limit.

### 2. GitHub (private repo)
1. **github.com** → **+** → **New repository** → name `company-research-agent` → **Private** → **Create repository**.
2. Click **uploading an existing file**, drag in all files and folders, then **Commit changes**.
3. Hidden files (`.gitignore`, `.streamlit/secrets.toml.example`): create them with **Add file → Create new file**.

### 3. Streamlit Community Cloud
1. **share.streamlit.io** → sign in with GitHub → **Create app**.
2. Repo `your-username/company-research-agent` · Branch `main` · Main file `app.py`.
3. **Advanced settings → Secrets**:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key"
   APP_PASSWORD = "your-password"
   ```
4. **Deploy**.

## Settings (`config.py`)
| Setting | Default | What it does |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Switch to a Sonnet model ID for deeper output |
| `FIT_WEIGHTS` | 0.5 / 0.3 / 0.2 | Fit score weights |
| `NEWS_WINDOW_DAYS` | 30 | How far back news goes |
| `NEWS_MAX_ITEMS` | 5 | Number of news items shown |
| `ROLE_MIN_MATCH` | 75 | Minimum match score for a role to show |
| `ROLE_MAX_SHOWN` | 3 | Maximum roles shown |
| `MAX_SEARCHES_ANALYZE` | 1 | Paid web searches per company run |
| `PRICE_*` | Haiku rates | Used only for the cost display; verify at claude.com/pricing |

## Known limits
- **Roles** only come from Greenhouse, Lever and Ashby. Companies on Workday or custom career sites show no roles; use the **Paste a job description** tab for those. If roles look missing, enter the job board slug (e.g. `gong` from `boards.greenhouse.io/gong`).
- **News** comes from the free Google News RSS feed. It has no official guarantee and may sometimes block cloud servers; when that happens, the news tab shows "No product news."

## Files
```
app.py            Streamlit UI and password gate
agent.py          Claude calls: role matching, analysis, role prep, suggestions
job_boards.py     Free Greenhouse / Lever / Ashby postings
news.py           Free Google News RSS
resume_parser.py  .docx / .pdf → text
config.py         All settings
samples/          Default sample resume
```
