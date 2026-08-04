"""
Shared thresholds for risk_engine.py and reviewability_engine.py.

These were previously duplicated as inline magic numbers in both files -
tuning the scoring model meant editing two places and hoping they stayed
in sync. Centralized here instead; behavior is unchanged.
"""

# --- Lines-changed (LOC) thresholds used by risk_engine ---
LOC_MASSIVE = 1000
LOC_LARGE = 501
LOC_MODERATE = 101

# --- Lines-changed thresholds used by reviewability_engine (smaller = better) ---
LOC_REVIEWABLE_SMALL = 100
LOC_REVIEWABLE_MEDIUM = 300
LOC_REVIEWABLE_LARGE = 1000

# --- Changed-file-count thresholds ---
FILES_MASSIVE = 50
FILES_LARGE = 21
FILES_MODERATE = 11
FILES_REVIEWABLE_FEW = 10

# --- Changed-symbol-count thresholds ---
SYMBOLS_LARGE = 11
SYMBOLS_MODERATE = 6

# --- Downstream-caller count thresholds (dependency impact) ---
CALLERS_HIGH = 11
CALLERS_MODERATE = 6

# --- Affected-service count threshold ---
SERVICES_WIDESPREAD = 3

# --- Risk-sensitive module paths ---
CRITICAL_DIRS = [
    "backend/auth", "backend/payment", "backend/core", "backend/security",
    "core", "auth", "payment", "security",
]

# --- Final risk category boundaries (score out of 10) ---
RISK_HIGH_THRESHOLD = 6
RISK_MEDIUM_THRESHOLD = 3

# --- PR description quality threshold (characters) ---
DESCRIPTION_GOOD_LENGTH = 20
