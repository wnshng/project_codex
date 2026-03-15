"""Shared constants used across the trading AI system."""

TIMEFRAME_ORDER = ("1w", "1d", "4h", "1h", "30m", "15m", "1m")

TIMEFRAME_WEIGHTS = {
    "1w": 0.22,
    "1d": 0.20,
    "4h": 0.18,
    "1h": 0.14,
    "30m": 0.10,
    "15m": 0.09,
    "1m": 0.07,
}

MAX_TIMEFRAME_COMPONENT_SCORE = 12.0

CLASS_UP = "up"
CLASS_DOWN = "down"
CLASS_SIDE = "side"
CLASS_ORDER = (CLASS_UP, CLASS_DOWN, CLASS_SIDE)

ENTRY_ALLOW_FULL = "allow_full"
ENTRY_ALLOW_PROBE = "allow_probe"
ENTRY_REJECT = "reject"

ENTRY_CONFIRMED_BREAKOUT = "confirmed_breakout"
ENTRY_PULLBACK = "pullback_entry"
ENTRY_REVERSAL_PROBE = "reversal_probe"

FINAL_ACTIONS = (
    "STRONG_LONG",
    "WEAK_LONG",
    "NEUTRAL",
    "WEAK_SHORT",
    "STRONG_SHORT",
    "NO_TRADE",
)

MODEL_WEIGHTS = {
    "xgboost": 0.50,
    "lstm": 0.35,
    "random_forest": 0.15,
}

RULE_CATEGORIES = (
    "entry",
    "risk",
    "filter",
    "exit",
    "position",
)
