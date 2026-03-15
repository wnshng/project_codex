"""State helpers for safe Streamlit reruns when the selected ticker changes."""

from __future__ import annotations

from dataclasses import dataclass

from trading_ai_system.data.loaders.symbol_resolver import ResolvedTicker


_SYMBOL_SCOPED_KEYS = [
    "resolved_ticker",
    "analysis_context",
    "analysis_prediction",
    "analysis_levels",
    "history_frames",
    "simulation_preview",
    "selected_trade_entry",
    "selected_trade_exit",
    "trade_form_nonce",
]


@dataclass
class DashboardStateSnapshot:
    selection_key: str
    changed: bool


def build_selection_key(
    resolved: ResolvedTicker,
    *,
    mode: str,
    analysis_timeframe: str,
) -> str:
    """Builds a stable symbol-specific key used by cache and session state."""
    return "::".join(
        [
            resolved.cache_key,
            mode,
            analysis_timeframe,
        ]
    )


def ensure_session_defaults(st) -> None:
    """Creates long-lived state containers only once."""
    if "active_selection_key" not in st.session_state:
        st.session_state.active_selection_key = ""
    if "portfolio_state" not in st.session_state:
        st.session_state.portfolio_state = None
    if "trade_results" not in st.session_state:
        st.session_state.trade_results = []
    if "trade_form_nonce" not in st.session_state:
        st.session_state.trade_form_nonce = 0
    if "quote_refresh_nonce" not in st.session_state:
        st.session_state.quote_refresh_nonce = 0


def reset_symbol_scoped_state(st, selection_key: str) -> DashboardStateSnapshot:
    """Clears symbol-scoped values so the previous ticker cannot leak forward."""
    changed = st.session_state.get("active_selection_key") != selection_key
    if changed:
        for key in _SYMBOL_SCOPED_KEYS:
            st.session_state.pop(key, None)
        st.session_state.active_selection_key = selection_key
        st.session_state.trade_form_nonce = int(st.session_state.get("trade_form_nonce", 0)) + 1
    return DashboardStateSnapshot(selection_key=selection_key, changed=changed)
