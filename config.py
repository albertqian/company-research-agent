"""All tunable settings live here."""

# Model: swap to a Sonnet model ID here if Haiku output feels thin.
MODEL = "claude-haiku-5-5"

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
MAX_JOB_TITLES = 150          # titles sent to Claude for matching
JD_CHARS = 4000               # job description characters sent per matched role

# Paid web searches (each costs $0.01). Only the product overview uses search.
MAX_SEARCHES_ANALYZE = 1

MAX_OUTPUT_TOKENS = 6000

# Price per million tokens, used only for the on-screen cost estimate.
# Verify against https://claude.com/pricing and update if needed.
PRICE_INPUT_PER_M = 1.00
PRICE_OUTPUT_PER_M = 5.00
PRICE_PER_SEARCH = 0.01
