"""All tunable settings live here."""

# Model: swap to a Sonnet model ID here if Haiku output feels thin.
MODEL = "claude-haiku-5-5"

# Fit score weights (must add up to 1.0)
FIT_WEIGHTS = {
    "skills": 0.50,
    "domain": 0.30,
    "experience": 0.20,
}

# Only keep news published within this many days.
NEWS_WINDOW_DAYS = 90

# Web-search caps per run (each search costs $0.01).
MAX_SEARCHES_ANALYZE = 8
MAX_SEARCHES_SUGGEST = 4

# Max tokens Claude may write per run.
MAX_OUTPUT_TOKENS = 8000

# Max job titles from a job board passed to Claude (keeps input tokens down).
MAX_ATS_JOBS = 80

# Price per million tokens, used only for the on-screen cost estimate.
# Verify against https://claude.com/pricing and update if needed.
PRICE_INPUT_PER_M = 1.00
PRICE_OUTPUT_PER_M = 5.00
PRICE_PER_SEARCH = 0.01
