"""Turns resolved symbols and OHLCV history into MarketContext objects."""

from __future__ import annotations

from typing import Optional

from trading_ai_system.data.loaders.symbol_resolver import ResolvedTicker
from trading_ai_system.data.schemas.market import MarketContext, ModelProbabilities, TimeframeState


def build_context_from_histories(
    resolved: ResolvedTicker,
    histories: dict[str, object],
    *,
    mode: str,
    account_equity: Optional[float] = None,
) -> MarketContext:
    """Builds the existing prediction pipeline input from price history."""
    import pandas as pd

    timeframe_states: dict[str, TimeframeState] = {}
    for timeframe, frame in histories.items():
        if frame is None or len(frame) < 40:
            continue
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(frame)
        timeframe_states[timeframe] = _build_timeframe_state_from_frame(timeframe, frame)

    higher_bias = _score_sign(timeframe_states.get("1d")) or _score_sign(timeframe_states.get("4h"))
    lower_bias = _score_sign(timeframe_states.get("1h")) or _score_sign(timeframe_states.get("15m"))
    anchor_state = timeframe_states.get("1h") or timeframe_states.get("4h") or next(iter(timeframe_states.values()))
    latest_close = float(anchor_state.get_float("close_price"))

    strategy_state = _build_strategy_state(
        resolved,
        timeframe_states,
        account_equity=account_equity,
    )
    model_outputs = _build_model_outputs(timeframe_states, strategy_state)

    return MarketContext(
        symbol=resolved.canonical_symbol,
        asset_type=resolved.asset_class,
        exchange=resolved.exchange,
        mode=mode,
        current_price=latest_close,
        timestamp=str(anchor_state.signals.get("last_timestamp")),
        timeframes=timeframe_states,
        strategy_state=strategy_state,
        model_outputs=model_outputs,
    )


def _build_timeframe_state_from_frame(timeframe: str, frame):
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    volume = frame["volume"].astype(float)

    ema5 = _ema(close, 5)
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    ema200 = _ema(close, 200)
    macd_line = _ema(close, 12) - _ema(close, 26)
    macd_signal = _ema(macd_line, 9)
    macd_hist = macd_line - macd_signal
    rsi14 = _rsi(close, 14)
    stoch_k, stoch_d = _stochastic(high, low, close, 14, 3)
    atr14 = _atr(high, low, close, 14)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std().fillna(0.0)
    bb_upper = bb_mid + (bb_std * 2.0)
    bb_lower = bb_mid - (bb_std * 2.0)
    bb_width = ((bb_upper - bb_lower) / bb_mid.replace(0, 1)).fillna(0.0)
    vwap = _vwap(high, low, close, volume)
    volume_ma20 = volume.rolling(20).mean().replace(0, 1)
    volume_ratio = (volume / volume_ma20).fillna(0.0)
    cci20 = _cci(high, low, close, 20)
    williams_r = _williams_r(high, low, close, 14)
    obv = _obv(close, volume)
    obv_slope = _slope(obv, 5)
    adx = _trend_strength(close, ema20, ema50, atr14)
    psar_flag = close.iloc[-1] >= ema20.iloc[-1]

    breakout_high = high.tail(20).max()
    breakout_low = low.tail(20).min()
    prior_high = high.tail(40).head(20).max() if len(high) >= 40 else breakout_high
    prior_low = low.tail(40).head(20).min() if len(low) >= 40 else breakout_low
    breakout_confirmed = close.iloc[-1] > prior_high and volume_ratio.iloc[-1] > 1.1
    breakdown_confirmed = close.iloc[-1] < prior_low and volume_ratio.iloc[-1] > 1.1
    retest_success = close.iloc[-1] > ema20.iloc[-1] and low.tail(3).min() <= ema20.iloc[-1]

    price_range = max(high.tail(40).max() - low.tail(40).min(), 1e-9)
    fib_position = (close.iloc[-1] - low.tail(40).min()) / price_range
    retracement_ratio = min(max(1.0 - fib_position, 0.0), 1.0)
    extension_ratio = 1.0 + abs(_slope(close, 10)) * 25
    wave_stage = "impulse" if ema20.iloc[-1] > ema50.iloc[-1] and close.iloc[-1] > ema20.iloc[-1] else "corrective" if ema20.iloc[-1] < ema50.iloc[-1] else "transition"
    sr_touch_count = _count_level_touches(close.tail(50), close.tail(50).mean())
    triangle_flag = _is_contracting_range(high.tail(20), low.tail(20))
    wedge_flag = triangle_flag and _slope(volume, 10) < 0
    fifth_exhaustion = abs(_slope(close, 5)) < abs(_slope(close, 20)) * 0.45 and abs(_slope(close, 20)) > 0.005
    bullish_divergence = close.iloc[-1] <= close.tail(10).min() * 1.01 and rsi14.iloc[-1] > rsi14.tail(10).min()
    bearish_divergence = close.iloc[-1] >= close.tail(10).max() * 0.99 and rsi14.iloc[-1] < rsi14.tail(10).max()

    trend_score = _clip(
        ((_safe_ratio(ema20.iloc[-1], ema50.iloc[-1]) - 1.0) * 28)
        + (_slope(ema20, 5) * 120),
        -3.0,
        3.0,
    )
    momentum_score = _clip(
        ((rsi14.iloc[-1] - 50.0) / 15.0)
        + (macd_hist.iloc[-1] * 8.0),
        -2.0,
        2.0,
    )
    volatility_score = _clip(
        ((bb_width.iloc[-1] - bb_width.tail(20).mean()) * 10.0),
        -1.0,
        1.0,
    )
    volume_score = _clip((volume_ratio.iloc[-1] - 1.0) * 1.6, -1.0, 1.0)
    pattern_score = _clip(
        (1.4 if breakout_confirmed else 0.0)
        - (1.4 if breakdown_confirmed else 0.0)
        + (0.6 if bullish_divergence else 0.0)
        - (0.6 if bearish_divergence else 0.0)
        + (0.3 if triangle_flag else 0.0),
        -3.0,
        3.0,
    )
    target_score = _clip(
        (0.8 - abs(fib_position - 0.5) * 1.6)
        + (0.4 if retest_success else 0.0),
        -2.0,
        2.0,
    )

    close_open_body = ((close.iloc[-1] - float(frame["open"].iloc[-1])) / max(close.iloc[-1], 1e-9))
    high_low_range = (high.iloc[-1] - low.iloc[-1]) / max(close.iloc[-1], 1e-9)

    return TimeframeState(
        timeframe=timeframe,
        trend_score=trend_score,
        momentum_score=momentum_score,
        volatility_score=volatility_score,
        volume_score=volume_score,
        pattern_score=pattern_score,
        target_score=target_score,
        confidence=0.95 if timeframe in {"1d", "1w"} else 0.86 if timeframe in {"4h", "1h"} else 0.76,
        regime="trend" if abs(trend_score) > 1.2 else "transition",
        signals={
            "close_price": close.iloc[-1],
            "last_timestamp": frame["timestamp"].iloc[-1],
            "ema5": ema5.iloc[-1],
            "ema20": ema20.iloc[-1],
            "ema50": ema50.iloc[-1],
            "ema200": ema200.iloc[-1],
            "price_above_ema20_flag": close.iloc[-1] > ema20.iloc[-1],
            "price_above_ema50_flag": close.iloc[-1] > ema50.iloc[-1],
            "macd_line": macd_line.iloc[-1],
            "macd_signal": macd_signal.iloc[-1],
            "macd_histogram": macd_hist.iloc[-1],
            "adx": adx,
            "psar_trend_flag": psar_flag,
            "rsi14": rsi14.iloc[-1],
            "rsi_slope": _slope(rsi14, 5),
            "stoch_k": stoch_k.iloc[-1],
            "stoch_d": stoch_d.iloc[-1],
            "cci20": cci20.iloc[-1],
            "williams_r": williams_r.iloc[-1],
            "bullish_divergence_flag": bullish_divergence,
            "bearish_divergence_flag": bearish_divergence,
            "bb_width": bb_width.iloc[-1],
            "bb_position": _safe_ratio(close.iloc[-1] - bb_lower.iloc[-1], (bb_upper.iloc[-1] - bb_lower.iloc[-1]) or 1.0),
            "atr14": atr14.iloc[-1],
            "atr_close_ratio": _safe_ratio(atr14.iloc[-1], close.iloc[-1]),
            "keltner_upper_distance": _safe_ratio((ema20.iloc[-1] + (atr14.iloc[-1] * 2.0)) - close.iloc[-1], close.iloc[-1]),
            "keltner_lower_distance": _safe_ratio(close.iloc[-1] - (ema20.iloc[-1] - (atr14.iloc[-1] * 2.0)), close.iloc[-1]),
            "squeeze_flag": bb_width.iloc[-1] < bb_width.tail(20).quantile(0.35),
            "obv_slope": obv_slope,
            "vwap_distance": _safe_ratio(close.iloc[-1] - vwap.iloc[-1], vwap.iloc[-1]),
            "volume_to_ma20": volume_ratio.iloc[-1],
            "mfi14": _money_flow_index(high, low, close, volume, 14).iloc[-1],
            "volume_spike_flag": volume_ratio.iloc[-1] >= 1.5,
            "doji_flag": abs(close_open_body) <= high_low_range * 0.1,
            "hammer_flag": close_open_body > 0 and ((close.iloc[-1] - low.iloc[-1]) / max(high.iloc[-1] - low.iloc[-1], 1e-9)) > 0.55,
            "engulfing_bull_flag": close.iloc[-1] > frame["open"].iloc[-1] and close.iloc[-2] < frame["open"].iloc[-2] if len(frame) > 2 else False,
            "engulfing_bear_flag": close.iloc[-1] < frame["open"].iloc[-1] and close.iloc[-2] > frame["open"].iloc[-2] if len(frame) > 2 else False,
            "morning_star_flag": close.iloc[-1] > close.tail(3).mean() and close.iloc[-2] < close.iloc[-3] if len(frame) > 3 else False,
            "flag_pattern_confirmed": breakout_confirmed or retest_success,
            "wedge_breakout_flag": wedge_flag,
            "head_shoulders_confirmed": bearish_divergence and breakdown_confirmed,
            "triangle_breakout_flag": triangle_flag and (breakout_confirmed or breakdown_confirmed),
            "estimated_wave_stage": wave_stage,
            "impulse_candidate_flag": wave_stage == "impulse",
            "corrective_candidate_flag": wave_stage == "corrective",
            "fib_retracement_zone_class": _fib_zone_label(retracement_ratio),
            "fib_extension_zone_class": _extension_zone_label(extension_ratio),
            "common_zone_hit_flag": 0.382 <= retracement_ratio <= 0.618,
            "fifth_wave_exhaustion_flag": fifth_exhaustion,
            "abc_completion_flag": wave_stage == "corrective" and 0.6 <= retracement_ratio <= 0.88,
            "return_1_bar": _safe_ratio(close.iloc[-1] - close.iloc[-2], close.iloc[-2]) if len(close) > 1 else 0.0,
            "return_3_bar": _safe_ratio(close.iloc[-1] - close.iloc[-4], close.iloc[-4]) if len(close) > 4 else 0.0,
            "return_5_bar": _safe_ratio(close.iloc[-1] - close.iloc[-6], close.iloc[-6]) if len(close) > 6 else 0.0,
            "return_10_bar": _safe_ratio(close.iloc[-1] - close.iloc[-11], close.iloc[-11]) if len(close) > 11 else 0.0,
            "gap_ratio": _safe_ratio(float(frame["open"].iloc[-1]) - close.iloc[-2], close.iloc[-2]) if len(close) > 1 else 0.0,
            "high_low_range_pct": high_low_range,
            "body_pct": close_open_body,
            "upper_wick_ratio": _safe_ratio(high.iloc[-1] - max(close.iloc[-1], float(frame["open"].iloc[-1])), high.iloc[-1] - low.iloc[-1]),
            "lower_wick_ratio": _safe_ratio(min(close.iloc[-1], float(frame["open"].iloc[-1])) - low.iloc[-1], high.iloc[-1] - low.iloc[-1]),
            "wave_two_retracement_ratio": min(max(retracement_ratio, 0.236), 0.786),
            "wave_three_extension_ratio": max(extension_ratio, 1.0),
            "wave_four_overlap_risk": sr_touch_count >= 4 and abs(_slope(close, 5)) < 0.003,
            "wave_five_extension_ratio": 1.618 if fifth_exhaustion else 1.0,
            "triangle_e_undershoot_flag": triangle_flag and abs(_slope(close, 3)) < 0.0018,
            "diagonal_candidate_flag": wedge_flag,
            "wedge_volume_decline_flag": wedge_flag and _slope(volume, 8) < 0,
            "flat_b_retracement_ratio": min(max(retracement_ratio + 0.18, 0.78), 1.08),
            "zigzag_b_retracement_ratio": min(max(retracement_ratio, 0.62), 0.82),
            "wave_five_failure_risk": fifth_exhaustion and volume_ratio.iloc[-1] < 1.0,
            "sr_touch_count": sr_touch_count,
            "breakout_confirmed_flag": breakout_confirmed or breakdown_confirmed,
            "retest_success_flag": retest_success,
        },
        notes=[
            "글렌닐리 비율 검증을 feature score 방식으로 반영",
            "상위 프레임 구조 우선, 하위 프레임은 타점 보조",
        ],
    )


def _build_strategy_state(resolved, timeframe_states, *, account_equity: Optional[float]):
    higher = timeframe_states.get("1d") or timeframe_states.get("4h")
    lower = timeframe_states.get("1h") or timeframe_states.get("15m")
    micro = timeframe_states.get("15m") or timeframe_states.get("1m") or lower
    if higher is None or lower is None or micro is None:
        raise ValueError("멀티 타임프레임 계산에 필요한 데이터가 부족합니다.")

    higher_score = higher.normalized_score
    lower_score = lower.normalized_score
    lower_conflict = higher_score * lower_score < 0
    breakout_confirmed = lower.get_bool("breakout_confirmed_flag")
    retest_success = lower.get_bool("retest_success_flag")
    stop_distance_ratio = max(lower.get_float("atr_close_ratio", 0.01) * 1.2, 0.004)
    nearest_target_distance = max(0.004, abs(lower.get_float("keltner_upper_distance", 0.02)))
    sr_touch_count = max(lower.get_float("sr_touch_count", 2), higher.get_float("sr_touch_count", 2))
    fourth_touch_risk = sr_touch_count >= 4
    overlapping_zone = abs(micro.get_float("wave_two_retracement_ratio", 0.5) - lower.get_float("wave_two_retracement_ratio", 0.5)) <= 0.08
    chasing_risk = abs(lower.get_float("return_1_bar")) >= lower.get_float("atr_close_ratio", 0.01) * 1.3
    reward_risk_ratio = max(0.5, nearest_target_distance / max(stop_distance_ratio, 1e-9))
    current_event_risk = "high" if lower.get_float("atr_close_ratio") >= 0.035 else "normal"
    countertrend = higher_score * lower_score < 0 and abs(lower_score) > 0.15

    return {
        "symbol_key": resolved.cache_key,
        "breakout_confirmed_flag": breakout_confirmed,
        "pattern_confirmed": breakout_confirmed or retest_success,
        "confirmation_entry": breakout_confirmed or retest_success,
        "retest_success_flag": retest_success,
        "close_above_key_level_flag": lower.normalized_score > 0.18,
        "close_below_key_level_flag": lower.normalized_score < -0.18,
        "stop_is_clear": stop_distance_ratio <= 0.03,
        "stop_distance_ratio": stop_distance_ratio,
        "distance_from_breakout_ratio": abs(lower.get_float("vwap_distance")),
        "chasing_risk": chasing_risk,
        "fourth_touch_break_risk": fourth_touch_risk,
        "sr_touch_count": sr_touch_count,
        "overlapping_target_zone": overlapping_zone,
        "caution_zone_flag": overlapping_zone,
        "countertrend": countertrend,
        "event_volatility_risk": current_event_risk,
        "reward_risk_ratio": reward_risk_ratio,
        "lower_tf_exit_priority": True,
        "split_entry_recommended": True,
        "partial_tp_enabled": True,
        "split_exit_ready": True,
        "entry_signal_on_3m": micro.get_bool("triangle_breakout_flag") or breakout_confirmed,
        "entry_signal_on_5m": micro.get_bool("flag_pattern_confirmed") or retest_success,
        "entry_signal_on_15m": lower.get_bool("flag_pattern_confirmed") or breakout_confirmed,
        "target_zone_from_1m_flag": timeframe_states.get("1m").get_bool("common_zone_hit_flag") if timeframe_states.get("1m") else False,
        "nearest_target_distance": nearest_target_distance,
        "lower_tf_conflict_flag": lower_conflict,
        "target_reached_recently": lower.get_bool("fifth_wave_exhaustion_flag"),
        "flag_breakout_volume_confirmed": lower.get_bool("flag_pattern_confirmed") and lower.get_float("volume_to_ma20") > 1.1,
        "triangle_breakout_volume_confirmed": lower.get_bool("triangle_breakout_flag") and lower.get_float("volume_to_ma20") > 1.1,
        "hs_confirmed_breakout_flag": lower.get_bool("head_shoulders_confirmed"),
        "same_candle_reentry": False,
        "one_candle_one_trade_violation": False,
        "manual_no_trade": False,
        "ema_support_hold": lower.get_bool("price_above_ema20_flag"),
        "vwap_support_hold": lower.get_float("vwap_distance") >= -0.01,
        "pullback_entry_ready": 0.382 <= lower.get_float("wave_two_retracement_ratio", 0.5) <= 0.618,
        "common_zone_hit_flag": lower.get_bool("common_zone_hit_flag"),
        "bullish_divergence_flag": lower.get_bool("bullish_divergence_flag"),
        "bearish_divergence_flag": lower.get_bool("bearish_divergence_flag"),
        "fifth_wave_exhaustion_flag": lower.get_bool("fifth_wave_exhaustion_flag"),
        "abc_completion_flag": lower.get_bool("abc_completion_flag"),
        "reversal_setup": lower.get_bool("bullish_divergence_flag") or lower.get_bool("bearish_divergence_flag"),
        "risk_per_trade_pct": 0.01,
        "account_equity": float(account_equity or 0.0),
        "current_price": lower.get_float("close_price"),
    }


def _build_model_outputs(timeframe_states, strategy_state):
    higher = timeframe_states.get("1d") or timeframe_states.get("4h")
    lower = timeframe_states.get("1h") or timeframe_states.get("15m")
    higher_bias = higher.normalized_score if higher is not None else 0.0
    lower_bias = lower.normalized_score if lower is not None else 0.0
    breakout_bonus = 0.08 if strategy_state["breakout_confirmed_flag"] else 0.0
    caution_penalty = 0.06 if strategy_state["overlapping_target_zone"] else 0.0

    xgb_up = _clip(0.50 + higher_bias * 0.22 + lower_bias * 0.12 + breakout_bonus - caution_penalty, 0.05, 0.90)
    lstm_up = _clip(0.50 + higher_bias * 0.14 + lower_bias * 0.18 + breakout_bonus - caution_penalty * 0.5, 0.05, 0.90)
    rf_up = _clip(0.50 + higher_bias * 0.18 + lower_bias * 0.08 - caution_penalty, 0.05, 0.90)

    xgb_down = _clip(0.45 - higher_bias * 0.22 - lower_bias * 0.12 + caution_penalty, 0.05, 0.90)
    lstm_down = _clip(0.45 - higher_bias * 0.14 - lower_bias * 0.18 + caution_penalty * 0.5, 0.05, 0.90)
    rf_down = _clip(0.45 - higher_bias * 0.18 - lower_bias * 0.08 + caution_penalty, 0.05, 0.90)

    return {
        "xgboost": ModelProbabilities("xgboost", up=xgb_up, down=xgb_down, side=max(0.05, 1.0 - xgb_up - xgb_down)),
        "lstm": ModelProbabilities("lstm", up=lstm_up, down=lstm_down, side=max(0.05, 1.0 - lstm_up - lstm_down)),
        "random_forest": ModelProbabilities("random_forest", up=rf_up, down=rf_down, side=max(0.05, 1.0 - rf_up - rf_down)),
    }


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series, period: int):
    delta = series.diff().fillna(0.0)
    gains = delta.clip(lower=0.0)
    losses = (-delta.clip(upper=0.0)).abs()
    avg_gain = gains.rolling(period).mean()
    avg_loss = losses.rolling(period).mean().replace(0, 1e-9)
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _stochastic(high, low, close, period: int, smooth: int):
    lowest = low.rolling(period).min()
    highest = high.rolling(period).max()
    denominator = (highest - lowest).replace(0, 1e-9)
    k = ((close - lowest) / denominator) * 100
    d = k.rolling(smooth).mean()
    return k.fillna(50.0), d.fillna(50.0)


def _atr(high, low, close, period: int):
    tr = (high - low).to_frame("hl")
    tr["hc"] = (high - close.shift(1)).abs()
    tr["lc"] = (low - close.shift(1)).abs()
    return tr.max(axis=1).rolling(period).mean().fillna(method="bfill").fillna(0.0)


def _vwap(high, low, close, volume):
    typical = (high + low + close) / 3.0
    cumulative_value = (typical * volume).cumsum()
    cumulative_volume = volume.cumsum().replace(0, 1e-9)
    return cumulative_value / cumulative_volume


def _cci(high, low, close, period: int):
    typical = (high + low + close) / 3.0
    sma = typical.rolling(period).mean()
    mad = (typical - sma).abs().rolling(period).mean().replace(0, 1e-9)
    return ((typical - sma) / (0.015 * mad)).fillna(0.0)


def _williams_r(high, low, close, period: int):
    highest = high.rolling(period).max()
    lowest = low.rolling(period).min()
    denominator = (highest - lowest).replace(0, 1e-9)
    return (((highest - close) / denominator) * -100).fillna(-50.0)


def _obv(close, volume):
    direction = close.diff().fillna(0.0).apply(lambda value: 1 if value > 0 else -1 if value < 0 else 0)
    return (direction * volume).cumsum()


def _money_flow_index(high, low, close, volume, period: int):
    typical = (high + low + close) / 3.0
    money_flow = typical * volume
    direction = typical.diff().fillna(0.0)
    positive = money_flow.where(direction > 0, 0.0).rolling(period).sum()
    negative = money_flow.where(direction < 0, 0.0).rolling(period).sum().replace(0, 1e-9)
    ratio = positive / negative
    return (100 - (100 / (1 + ratio))).fillna(50.0)


def _trend_strength(close, ema20, ema50, atr14):
    spread = abs(_safe_ratio(ema20.iloc[-1] - ema50.iloc[-1], close.iloc[-1]))
    atr_ratio = _safe_ratio(atr14.iloc[-1], close.iloc[-1])
    return min(50.0, 15.0 + (spread * 900) + (atr_ratio * 500))


def _is_contracting_range(high, low):
    if len(high) < 6 or len(low) < 6:
        return False
    recent_highs = high.tolist()
    recent_lows = low.tolist()
    return max(recent_highs[:3]) >= max(recent_highs[-3:]) and min(recent_lows[:3]) <= min(recent_lows[-3:])


def _count_level_touches(series, level: float):
    touches = 0
    threshold = abs(level) * 0.01
    for value in series.tolist():
        if abs(float(value) - level) <= threshold:
            touches += 1
    return touches


def _fib_zone_label(ratio: float) -> str:
    if 0.382 <= ratio <= 0.618:
        return "0.382~0.618"
    if 0.618 < ratio <= 0.786:
        return "0.618~0.786"
    return "기타"


def _extension_zone_label(ratio: float) -> str:
    if ratio >= 2.618:
        return "2.618"
    if ratio >= 1.618:
        return "1.618"
    return "1.272"


def _slope(series, lookback: int):
    if len(series) <= lookback:
        return 0.0
    start = float(series.iloc[-lookback - 1])
    end = float(series.iloc[-1])
    if start == 0:
        return 0.0
    return (end - start) / abs(start)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _score_sign(state: Optional[TimeframeState]) -> float:
    if state is None:
        return 0.0
    return state.normalized_score
