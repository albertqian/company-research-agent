# Company Research Agent

A password-protected Streamlit app that researches companies for a job seeker, using Claude Haiku with web search.

**For any company it returns:**
- **Fit score (0–100):** skills match 50%, domain match 30%, years of experience 20%. Each part shows its own score and reason.
- **Open roles the candidate qualifies for:** checks Greenhouse, Lever and Ashby job boards first, then falls back to web search.
- **Interview prep:** talking points, likely questions with how to answer, and questions to ask them.
- **Recent news:** last 90 days only, dated and linked.
- **Product overview:** products, customers, competitors.

**Suggest mode:** proposes companies that fit the uploaded resume. Click one to research it.

Estimated cost: about $0.10–0.25 per company run on Haiku. Each run shows its cost, and the sidebar shows the session total.

---

## Deploy (one time, about 10 minutes)

### 1. Get an API key
1. Go to **console.anthropic.com** → **API Keys** → **Create Key**.
2. Copy the key (it starts with `sk-ant-`).
3. Go to **Settings → Limits** and set a monthly spend limit (e.g. $20).

### 2. Put the code on GitHub
1. Go to **github.com** → **+** (top right) → **New repository**.
2. Name: `company-research-agent`. Choose **Private**. The sample resume belongs to a real person, so the repo should not be public.
3. Click **Create repository**.
4. Click **uploading an existing file**, drag in every file and folder from this zip, then click **Commit changes**.
   - Do **not** upload a `secrets.toml` file. Only `secrets.toml.example` belongs in the repo.

### 3. Deploy on Streamlit Community Cloud
1. Go to **share.streamlit.io** → sign in with GitHub.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Repository: `your-username/company-research-agent` · Branch: `main` · Main file path: `app.py`.
4. Click **Advanced settings** → in **Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-your-key"
   APP_PASSWORD = "pick-a-strong-password"
   ```
5. Click **Deploy**. Wait about 2 minutes, open the URL, and enter the password.

To change the password later: app page → **⋮** → **Settings** → **Secrets**.

---

## Run locally (optional)
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then fill it in
streamlit run app.py
```

## Settings
Everything you can change is in `config.py`:

| Setting | Default | What it does |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Change to a Sonnet model ID for deeper output (about 3× the cost) |
| `FIT_WEIGHTS` | 0.5 / 0.3 / 0.2 | Fit score weights; must add up to 1.0 |
| `NEWS_WINDOW_DAYS` | 90 | How far back news goes |
| `MAX_SEARCHES_ANALYZE` | 8 | Web-search cap per company run ($0.01 each) |
| `PRICE_*` | Haiku rates | Used only for the cost display; verify at claude.com/pricing |

## Known limits
- **Open roles:** auto-detect guesses the job-board name from the company name. If roles look missing, enter the **Job board slug** (e.g. `gong` from `boards.greenhouse.io/gong`). Companies on Workday or custom career sites fall back to web search, which can miss roles.
- **News:** items with no clear publish date are dropped, so the 90-day filter stays accurate.
- **Fit score:** Claude scores each part and the app does the weighted math. Expect a few points of variation between runs.
- Results are cached for the browser session, so re-opening the same company doesn't charge again.

## Files
```
app.py            Streamlit UI and password gate
agent.py          Claude calls, JSON parsing, fit math, news date filter
job_boards.py     Greenhouse / Lever / Ashby lookups
resume_parser.py  .docx / .pdf → text
config.py         All settings
samples/          Default sample resume
```
