"""TradingView widget helpers for the real-time chart pane."""

from __future__ import annotations

import hashlib
import json

from trading_ai_system.data.loaders.symbol_resolver import ResolvedTicker


_INTERVAL_MAP = {
    "1m": "1",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "4h": "240",
    "1d": "D",
    "1w": "W",
}


def build_tradingview_widget_html(
    resolved: ResolvedTicker,
    *,
    interval: str = "1h",
    theme: str = "dark",
    height: int = 620,
    key: str = "",
) -> str:
    """Builds embeddable HTML so Streamlit can render TradingView directly."""
    widget_key = key or resolved.cache_key
    container_id = "tv_" + hashlib.md5(widget_key.encode("utf-8")).hexdigest()
    widget_config = {
        "autosize": True,
        "symbol": resolved.tradingview_symbol,
        "interval": _INTERVAL_MAP.get(interval, "60"),
        "timezone": "Asia/Seoul",
        "theme": theme,
        "style": "1",
        "locale": "kr",
        "hide_side_toolbar": False,
        "allow_symbol_change": False,
        "container_id": container_id,
        "studies": ["Volume@tv-basicstudies"],
    }
    escaped_config = json.dumps(widget_config, ensure_ascii=False)
    return f"""
    <div style="height:{height}px;">
      <div id="{container_id}" style="height:{height}px;"></div>
    </div>
    <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
    <script type="text/javascript">
      new TradingView.widget({escaped_config});
    </script>
    """


def render_tradingview_chart(
    st,
    resolved: ResolvedTicker,
    *,
    interval: str = "1h",
    theme: str = "dark",
    height: int = 620,
    key: str = "",
) -> None:
    """Renders the TradingView widget inside Streamlit."""
    try:
        import streamlit.components.v1 as components
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("streamlit components를 불러오지 못했습니다.") from exc

    html = build_tradingview_widget_html(
        resolved,
        interval=interval,
        theme=theme,
        height=height,
        key=key,
    )
    components.html(html, height=height + 16, scrolling=False)
