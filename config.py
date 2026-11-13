"""All tunable settings live here."""

# Model per sub-agent. Swap any one to a Sonnet model ID for deeper output there.
DEFAULT_MODEL = "claude-haiku-5-5"
AGENT_MODELS = {
    "resume_profiler": DEFAULT_MODEL,
    "company_scout": DEFAULT_MODEL,
    "role_matcher": DEFAULT_MODEL,
    "product_researcher": DEFAULT_MODEL,
    "news_ranker": DEFAULT_MODEL,
    "fit_scorer": DEFAULT_MODEL,
    "interview_coach": DEFAULT_MODEL,
}

# Fit score weights (must add up to 1.0)
FIT_WEIGHTS = {
    "skills": 0.50,
    "domain": 0.30,
    "experience": 0.20,
}

# News: only items from the last N days; show at most N items.
NEWS_WINDOW_DAYS = 30
NEWS_MAX_ITEMS = 5
NEWS_HEADLINES_TO_RANK = 40

# Job-board roles: only show roles scoring at least this (0-100), max N roles.
ROLE_MIN_MATCH = 75
ROLE_MAX_SHOWN = 3
MAX_JOB_TITLES = 150          # titles sent to the Role Matcher
JD_CHARS = 4000               # job description characters sent per role

# Suggestions per resume.
SUGGESTION_COUNT = 8

# Paid web searches (each costs $0.01). Only the Product Researcher searches.
PRODUCT_MAX_SEARCHES = 1

MAX_OUTPUT_TOKENS = 4000

# Price per million tokens, used only for the on-screen cost estimate.
# Verify against https://claude.com/pricing and update if needed.
PRICE_INPUT_PER_M = 1.00
PRICE_OUTPUT_PER_M = 5.00
PRICE_PER_SEARCH = 0.01
