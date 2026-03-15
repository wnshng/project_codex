"""Plotly charts for actual market view, upgraded forecast paths, and trade review."""

from __future__ import annotations

from datetime import timedelta
import math


def build_projection_bundle(
    history_frame,
    prediction,
    level_summary,
    resolved,
    *,
    trade_plan=None,
    horizon_bars: int = 32,
):
    """Builds scenario paths and synthetic OHLCV frames used by forecast and simulation."""
    close_values = history_frame["close"].tolist()
    timestamps = history_frame["timestamp"].tolist()
    current_price = float(close_values[-1])
    step = _infer_step(timestamps)
    future_times = [timestamps[-1] + (step * (index + 1)) for index in range(horizon_bars)]

    entry_anchor = _nearest_entry_to_price(level_summary, current_price)
    upper_anchor = max(level_summary.take_profits[1].value, level_summary.resistances[1].value)
    upper_extension = max(level_summary.take_profits[-1].value, level_summary.resistances[-1].value)
    lower_anchor = min(level_summary.supports[1].value, level_summary.stop_loss.value)
    lower_extension = min(level_summary.supports[-1].value, level_summary.stop_loss.value)
    confidence = max(prediction.probabilities.values())

    up_path = _piecewise_path(
        current_price,
        [
            _blend(entry_anchor, current_price, 0.35),
            upper_anchor,
            upper_extension,
        ],
        [0.18, 0.68, 1.0],
        horizon_bars=horizon_bars,
        amplitude_ratio=0.003 + confidence * 0.002,
    )
    down_path = _piecewise_path(
        current_price,
        [
            _blend(entry_anchor, current_price, 0.40),
            lower_anchor,
            lower_extension,
        ],
        [0.18, 0.68, 1.0],
        horizon_bars=horizon_bars,
        amplitude_ratio=0.003 + confidence * 0.002,
    )
    side_path = _sideways_path(
        current_price,
        entry_anchor,
        horizon_bars,
        amplitude_ratio=0.0025,
    )

    expected_path = []
    upper_band = []
    lower_band = []
    for index in range(horizon_bars):
        weighted = (
            up_path[index] * prediction.probabilities["up"]
            + down_path[index] * prediction.probabilities["down"]
            + side_path[index] * prediction.probabilities["side"]
        )
        expected_path.append(weighted)
        upper_band.append(max(up_path[index], side_path[index], weighted))
        lower_band.append(min(down_path[index], side_path[index], weighted))

    frames = {
        "상승": build_projection_frame(history_frame, future_times, up_path),
        "하락": build_projection_frame(history_frame, future_times, down_path),
        "횡보": build_projection_frame(history_frame, future_times, side_path),
        "가중": build_projection_frame(history_frame, future_times, expected_path),
    }

    return {
        "future_times": future_times,
        "up_path": up_path,
        "down_path": down_path,
        "side_path": side_path,
        "expected_path": expected_path,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "frames": frames,
        "trade_plan": trade_plan,
        "resolved": resolved,
    }


def build_forecast_chart(
    history_frame,
    prediction,
    level_summary,
    resolved,
    *,
    trade_plan=None,
    horizon_bars: int = 32,
    projection_bundle=None,
    price_unit: str = "",
):
    """Builds an upgraded separated AI forecast chart."""
    import plotly.graph_objects as go

    bundle = projection_bundle or build_projection_bundle(
        history_frame,
        prediction,
        level_summary,
        resolved,
        trade_plan=trade_plan,
        horizon_bars=horizon_bars,
    )
    close_values = history_frame["close"].tolist()
    timestamps = history_frame["timestamp"].tolist()

    figure = go.Figure()
    figure.add_scatter(
        x=timestamps[-100:],
        y=close_values[-100:],
        mode="lines",
        name="최근 종가",
        line={"color": "#94a3b8", "width": 2},
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["upper_band"],
        mode="lines",
        line={"color": "rgba(59,130,246,0.0)"},
        showlegend=False,
        hoverinfo="skip",
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["lower_band"],
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(59,130,246,0.12)",
        line={"color": "rgba(59,130,246,0.0)"},
        name="예상 범위",
        hoverinfo="skip",
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["up_path"],
        mode="lines",
        name=f"상승 경로 ({prediction.probabilities['up'] * 100:.1f}%)",
        line={"color": "#10b981", "width": 2},
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["down_path"],
        mode="lines",
        name=f"하락 경로 ({prediction.probabilities['down'] * 100:.1f}%)",
        line={"color": "#ef4444", "width": 2},
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["side_path"],
        mode="lines",
        name=f"횡보 경로 ({prediction.probabilities['side'] * 100:.1f}%)",
        line={"color": "#f59e0b", "width": 2, "dash": "dot"},
    )
    figure.add_scatter(
        x=bundle["future_times"],
        y=bundle["expected_path"],
        mode="lines",
        name="확률 가중 경로",
        line={"color": "#2563eb", "width": 3},
    )

    for level in level_summary.supports[:2]:
        figure.add_hline(y=level.value, line_color="#22c55e", line_dash="dot", opacity=0.45)
    for level in level_summary.resistances[:2]:
        figure.add_hline(y=level.value, line_color="#f87171", line_dash="dot", opacity=0.45)
    for level in level_summary.entries[:2]:
        figure.add_hline(y=level.value, line_color="#60a5fa", line_dash="dash", opacity=0.55)
    for level in level_summary.take_profits[:2]:
        figure.add_hline(y=level.value, line_color="#c084fc", line_dash="dash", opacity=0.55)
    figure.add_hline(y=level_summary.stop_loss.value, line_color="#fb923c", line_dash="dot", opacity=0.55)

    if trade_plan and getattr(trade_plan, "allowed", False):
        figure.add_annotation(
            x=bundle["future_times"][max(2, int(len(bundle["future_times"]) * 0.22))],
            y=trade_plan.entry_price,
            text="추천 진입",
            showarrow=False,
            bgcolor="rgba(37,99,235,0.18)",
        )
        figure.add_annotation(
            x=bundle["future_times"][max(6, int(len(bundle["future_times"]) * 0.72))],
            y=trade_plan.target_price,
            text="목표가",
            showarrow=False,
            bgcolor="rgba(16,185,129,0.18)",
        )

    figure.update_layout(
        title=f"{resolved.display_name} 예상 차트",
        xaxis_title="시간",
        yaxis_title=f"가격 ({price_unit})" if price_unit else "가격",
        template="plotly_dark",
        height=520,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
        legend={"orientation": "h"},
    )
    return figure


def build_actual_price_chart(
    history_frame,
    resolved,
    *,
    level_summary=None,
    title: str = "실제 차트",
    price_unit: str = "",
):
    """Fallback actual chart used especially for KRX stocks."""
    import plotly.graph_objects as go

    frame = history_frame.tail(120).copy()
    closes = frame["close"].astype(float)
    ema20 = closes.ewm(span=20, adjust=False).mean()
    ema50 = closes.ewm(span=50, adjust=False).mean()

    figure = go.Figure(
        data=[
            go.Candlestick(
                x=frame["timestamp"],
                open=frame["open"],
                high=frame["high"],
                low=frame["low"],
                close=frame["close"],
                name="실제 차트",
                increasing_line_color="#0ea5e9",
                decreasing_line_color="#ef4444",
            )
        ]
    )
    figure.add_scatter(
        x=frame["timestamp"],
        y=ema20,
        mode="lines",
        name="이동평균 20",
        line={"color": "#f59e0b", "width": 1.8},
    )
    figure.add_scatter(
        x=frame["timestamp"],
        y=ema50,
        mode="lines",
        name="이동평균 50",
        line={"color": "#22c55e", "width": 1.8},
    )

    if level_summary is not None:
        for level in level_summary.entries[:1]:
            figure.add_hline(y=level.value, line_color="#60a5fa", line_dash="dash", opacity=0.6)
        for level in level_summary.take_profits[:1]:
            figure.add_hline(y=level.value, line_color="#c084fc", line_dash="dash", opacity=0.6)
        figure.add_hline(y=level_summary.stop_loss.value, line_color="#fb923c", line_dash="dot", opacity=0.6)

    figure.update_layout(
        title=f"{resolved.display_name} {title}",
        xaxis_title="시간",
        yaxis_title=f"가격 ({price_unit})" if price_unit else "가격",
        template="plotly_dark",
        height=620,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    figure.update_xaxes(rangeslider_visible=False)
    return figure


def build_trade_review_chart(history_frame, trade_input, simulation_result, *, price_unit: str = ""):
    """Shows entry, stop, and target markers on a review chart."""
    import plotly.graph_objects as go

    figure = go.Figure(
        data=[
            go.Candlestick(
                x=history_frame["timestamp"],
                open=history_frame["open"],
                high=history_frame["high"],
                low=history_frame["low"],
                close=history_frame["close"],
                name="시뮬레이션 차트",
                increasing_line_color="#0ea5e9",
                decreasing_line_color="#ef4444",
            )
        ]
    )

    figure.add_scatter(
        x=[trade_input.entry_time],
        y=[trade_input.entry_price],
        mode="markers+text",
        name="진입",
        text=["진입"],
        textposition="top center",
        marker={"size": 12, "color": "#2563eb", "symbol": "triangle-up"},
    )
    figure.add_scatter(
        x=[simulation_result.exit_time],
        y=[simulation_result.exit_price],
        mode="markers+text",
        name="청산",
        text=["청산"],
        textposition="bottom center",
        marker={"size": 12, "color": "#f97316", "symbol": "x"},
    )

    if trade_input.stop_loss is not None:
        figure.add_hline(y=trade_input.stop_loss, line_color="#ef4444", line_dash="dot")
    if trade_input.take_profit is not None:
        figure.add_hline(y=trade_input.take_profit, line_color="#10b981", line_dash="dot")

    figure.update_layout(
        title="추천 시나리오 시뮬레이션 차트",
        xaxis_title="시간",
        yaxis_title=f"가격 ({price_unit})" if price_unit else "가격",
        template="plotly_dark",
        height=520,
        margin={"l": 20, "r": 20, "t": 60, "b": 20},
    )
    figure.update_xaxes(rangeslider_visible=False)
    return figure


def build_projection_frame(history_frame, future_times, projection_values):
    """Converts one forecast path into synthetic OHLCV for the simulator."""
    import pandas as pd

    previous_close = float(history_frame["close"].iloc[-1])
    average_volume = float(history_frame["volume"].tail(20).mean())
    rows = []
    for index, timestamp in enumerate(future_times):
        close = float(projection_values[index])
        spread = max(abs(close - previous_close), previous_close * 0.0025)
        rows.append(
            {
                "timestamp": timestamp,
                "open": previous_close,
                "high": max(previous_close, close) + (spread * 0.35),
                "low": min(previous_close, close) - (spread * 0.35),
                "close": close,
                "volume": average_volume,
                "is_confirmed": False,
            }
        )
        previous_close = close
    return pd.DataFrame(rows)


def _infer_step(timestamps):
    if len(timestamps) >= 2:
        return timestamps[-1] - timestamps[-2]
    return timedelta(hours=1)


def _nearest_entry_to_price(level_summary, current_price: float) -> float:
    return min(level_summary.entries, key=lambda level: abs(level.value - current_price)).value


def _blend(a: float, b: float, ratio: float) -> float:
    return (a * ratio) + (b * (1 - ratio))


def _piecewise_path(current_price, anchors, checkpoints, *, horizon_bars: int, amplitude_ratio: float):
    values = []
    for index in range(horizon_bars):
        progress = (index + 1) / horizon_bars
        base = _interpolate_anchors(current_price, anchors, checkpoints, progress)
        swing = math.sin((index + 1) / 2.5) * current_price * amplitude_ratio
        values.append(max(0.01, base + swing))
    return values


def _sideways_path(current_price, entry_anchor, horizon_bars: int, amplitude_ratio: float):
    midpoint = _blend(current_price, entry_anchor, 0.45)
    values = []
    for index in range(horizon_bars):
        oscillation = math.sin((index + 1) / 1.8) * current_price * amplitude_ratio
        drift = math.sin((index + 1) / 6.0) * current_price * amplitude_ratio * 0.4
        values.append(midpoint + oscillation + drift)
    return values


def _interpolate_anchors(start_value, anchors, checkpoints, progress: float):
    previous_point = 0.0
    previous_value = start_value
    for target_value, target_point in zip(anchors, checkpoints):
        if progress <= target_point:
            local_ratio = (progress - previous_point) / max(target_point - previous_point, 1e-9)
            eased = 1 - ((1 - local_ratio) ** 2)
            return previous_value + ((target_value - previous_value) * eased)
        previous_point = target_point
        previous_value = target_value
    return anchors[-1]
