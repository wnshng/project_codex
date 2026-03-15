"""Minimal Streamlit dashboard for the trading AI system scaffold."""

from __future__ import annotations

from typing import Iterable

from trading_ai_system.data.schemas.market import MarketContext, ModelProbabilities, TimeframeState
from trading_ai_system.models.predictor import run_pipeline


def _build_timeframe_state(timeframe: str, bias: float, confidence: float) -> TimeframeState:
    raw = bias * 12
    return TimeframeState(
        timeframe=timeframe,
        trend_score=raw * 0.35,
        momentum_score=raw * 0.18,
        volatility_score=raw * 0.08,
        volume_score=raw * 0.08,
        pattern_score=raw * 0.18,
        target_score=raw * 0.13,
        confidence=confidence,
        regime="trend" if abs(bias) > 0.35 else "transition",
        signals={
            "rsi14": 58 + bias * 18,
            "macd_line": bias * 1.2,
            "macd_signal": bias * 0.8,
            "macd_histogram": bias * 0.4,
            "adx": 18 + abs(bias) * 20,
            "volume_to_ma20": 1.0 + abs(bias) * 0.6,
            "bb_width": 0.04 + abs(bias) * 0.03,
            "atr14": 0.9 + abs(bias),
            "atr_close_ratio": 0.01 + abs(bias) * 0.015,
            "vwap_distance": bias * 0.02,
            "ema5": 101 + bias * 4,
            "ema20": 100 + bias * 2,
            "ema50": 99 + bias,
            "ema200": 95,
            "return_1_bar": bias * 0.01,
            "return_3_bar": bias * 0.015,
            "return_5_bar": bias * 0.02,
            "return_10_bar": bias * 0.03,
            "bullish_divergence_flag": bias > 0.45,
            "bearish_divergence_flag": bias < -0.45,
            "price_above_ema20_flag": bias > 0,
            "price_above_ema50_flag": bias > 0.1,
            "psar_trend_flag": bias > 0,
            "estimated_wave_stage": "impulse" if bias > 0.35 else "corrective" if bias < -0.35 else "transition",
            "impulse_candidate_flag": bias > 0.35,
            "corrective_candidate_flag": bias < -0.35,
        },
    )


def _build_context(
    *,
    symbol: str,
    asset_type: str,
    exchange: str,
    mode: str,
    higher_tf_bias: float,
    lower_tf_bias: float,
    breakout_confirmed: bool,
    retest_success: bool,
    stop_clear: bool,
    chasing_risk: bool,
    fourth_touch_risk: bool,
    overlap_zone: bool,
    countertrend: bool,
    event_risk: str,
    reward_risk_ratio: float,
    xgb_up: float,
    lstm_up: float,
    rf_up: float,
) -> MarketContext:
    xgb_down = max(0.0, 1 - xgb_up - 0.15)
    lstm_down = max(0.0, 1 - lstm_up - 0.20)
    rf_down = max(0.0, 1 - rf_up - 0.25)
    timeframes = {
        "1w": _build_timeframe_state("1w", higher_tf_bias, 0.95),
        "1d": _build_timeframe_state("1d", higher_tf_bias, 0.92),
        "4h": _build_timeframe_state("4h", (higher_tf_bias + lower_tf_bias) / 2, 0.88),
        "1h": _build_timeframe_state("1h", lower_tf_bias, 0.84),
        "30m": _build_timeframe_state("30m", lower_tf_bias * 0.9, 0.80),
        "15m": _build_timeframe_state("15m", lower_tf_bias * 0.85, 0.78),
        "1m": _build_timeframe_state("1m", lower_tf_bias * 0.65, 0.72),
    }
    return MarketContext(
        symbol=symbol,
        asset_type=asset_type,
        exchange=exchange,
        mode=mode,
        current_price=100.0,
        timeframes=timeframes,
        strategy_state={
            "breakout_confirmed_flag": breakout_confirmed,
            "pattern_confirmed": breakout_confirmed or retest_success,
            "confirmation_entry": breakout_confirmed or retest_success,
            "retest_success_flag": retest_success,
            "stop_is_clear": stop_clear,
            "stop_distance_ratio": 0.012 if stop_clear else 0.05,
            "chasing_risk": chasing_risk,
            "fourth_touch_break_risk": fourth_touch_risk,
            "sr_touch_count": 4 if fourth_touch_risk else 2,
            "overlapping_target_zone": overlap_zone,
            "caution_zone_flag": overlap_zone,
            "countertrend": countertrend,
            "event_volatility_risk": event_risk,
            "reward_risk_ratio": reward_risk_ratio,
            "lower_tf_exit_priority": True,
            "split_entry_recommended": True,
            "entry_signal_on_3m": breakout_confirmed,
            "entry_signal_on_5m": retest_success,
            "entry_signal_on_15m": higher_tf_bias > 0.2,
            "nearest_target_distance": 0.008 if overlap_zone else 0.025,
            "lower_tf_conflict_flag": higher_tf_bias * lower_tf_bias < 0,
        },
        model_outputs={
            "xgboost": ModelProbabilities("xgboost", up=xgb_up, down=xgb_down, side=0.15),
            "lstm": ModelProbabilities("lstm", up=lstm_up, down=lstm_down, side=0.20),
            "random_forest": ModelProbabilities("random_forest", up=rf_up, down=rf_down, side=0.25),
        },
    )


def _format_probability(probability: float) -> str:
    return f"{probability * 100:.1f}%"


def _show_table(st_module, rows: Iterable[dict[str, object]]) -> None:
    st_module.dataframe(list(rows), use_container_width=True, hide_index=True)


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("streamlit is required to run the dashboard") from exc

    st.set_page_config(page_title="Trading AI System", layout="wide")
    st.title("Trading AI System MVP")
    st.caption("문서 기반 규칙 엔진 + MTF 점수 + 확률 예측을 한 흐름으로 묶은 데모")

    with st.sidebar:
        st.subheader("Asset")
        symbol = st.text_input("Ticker", value="BTCUSDT")
        asset_type = st.selectbox("Asset Type", options=["crypto", "stock"], index=0)
        exchange = st.selectbox("Exchange", options=["Binance", "Upbit", "NASDAQ", "KRX"], index=0)
        mode = st.selectbox("Mode", options=["realtime", "historical", "backtest"], index=0)

        st.subheader("Bias")
        higher_tf_bias = st.slider("Higher TF Bias", min_value=-1.0, max_value=1.0, value=0.45, step=0.05)
        lower_tf_bias = st.slider("Lower TF Bias", min_value=-1.0, max_value=1.0, value=0.25, step=0.05)

        st.subheader("Rule Inputs")
        breakout_confirmed = st.checkbox("Breakout Confirmed", value=True)
        retest_success = st.checkbox("Retest Success", value=True)
        stop_clear = st.checkbox("Stop Clear", value=True)
        chasing_risk = st.checkbox("Chasing Risk", value=False)
        fourth_touch_risk = st.checkbox("Fourth Touch Risk", value=False)
        overlap_zone = st.checkbox("Overlap Target Zone", value=False)
        countertrend = st.checkbox("Countertrend", value=False)
        event_risk = st.selectbox("Event Risk", options=["normal", "high", "extreme"], index=0)
        reward_risk_ratio = st.slider("Reward/Risk", min_value=0.5, max_value=4.0, value=2.0, step=0.1)

        st.subheader("Model Priors")
        xgb_up = st.slider("XGBoost Up Prob", min_value=0.05, max_value=0.90, value=0.58, step=0.01)
        lstm_up = st.slider("LSTM Up Prob", min_value=0.05, max_value=0.90, value=0.54, step=0.01)
        rf_up = st.slider("RF Up Prob", min_value=0.05, max_value=0.90, value=0.52, step=0.01)

    context = _build_context(
        symbol=symbol,
        asset_type=asset_type,
        exchange=exchange,
        mode=mode,
        higher_tf_bias=higher_tf_bias,
        lower_tf_bias=lower_tf_bias,
        breakout_confirmed=breakout_confirmed,
        retest_success=retest_success,
        stop_clear=stop_clear,
        chasing_risk=chasing_risk,
        fourth_touch_risk=fourth_touch_risk,
        overlap_zone=overlap_zone,
        countertrend=countertrend,
        event_risk=event_risk,
        reward_risk_ratio=reward_risk_ratio,
        xgb_up=xgb_up,
        lstm_up=lstm_up,
        rf_up=rf_up,
    )
    prediction = run_pipeline(context)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Final Action", prediction.final_action)
    col2.metric("Predicted Class", prediction.predicted_class.upper())
    col3.metric("Confidence", prediction.confidence_grade)
    col4.metric("Decision Score", f"{prediction.decision_score:.3f}")

    st.subheader("Probabilities")
    prob_cols = st.columns(3)
    prob_cols[0].metric("Up", _format_probability(prediction.probabilities["up"]))
    prob_cols[1].metric("Down", _format_probability(prediction.probabilities["down"]))
    prob_cols[2].metric("Side", _format_probability(prediction.probabilities["side"]))

    st.subheader("Top Reasons")
    for reason in prediction.top_reasons:
        st.write(f"- {reason}")

    left, right = st.columns(2)
    with left:
        st.subheader("MTF Summary")
        _show_table(
            st,
            [
                {
                    "timeframe": timeframe,
                    "raw_score": round(score.raw_score, 3),
                    "normalized": round(score.normalized_score, 3),
                    "bias": score.bias,
                    "weight": score.weight,
                }
                for timeframe, score in prediction.mtf_summary.timeframe_scores.items()
            ],
        )
        st.caption(
            f"Composite {prediction.mtf_summary.composite_score:.3f} | "
            f"Alignment bonus {prediction.mtf_summary.alignment_bonus:.3f} | "
            f"Caution penalty {prediction.mtf_summary.caution_penalty:.3f}"
        )

    with right:
        st.subheader("Rule Engine")
        _show_table(
            st,
            [
                {
                    "rule": result.name,
                    "passed": result.passed,
                    "impact": round(result.score_impact, 2),
                    "reason": result.reason or "",
                }
                for result in prediction.rule_outcome.results
            ],
        )
        if prediction.rule_outcome.no_trade_reasons:
            st.warning(" / ".join(prediction.rule_outcome.no_trade_reasons))

    lower_left, lower_right = st.columns(2)
    with lower_left:
        st.subheader("Entry Plan")
        st.json(
            {
                "decision": prediction.entry_plan.decision,
                "direction": prediction.entry_plan.direction,
                "entry_type": prediction.entry_plan.entry_type,
                "reasons": prediction.entry_plan.reasons,
                "split_entry_plan": prediction.entry_plan.split_entry_plan,
            }
        )

    with lower_right:
        st.subheader("Exit & Risk")
        st.json(
            {
                "risk_grade": prediction.risk_assessment.risk_grade,
                "risk_points": prediction.risk_assessment.risk_points,
                "stop_loss_policy": prediction.exit_plan.stop_loss_policy,
                "take_profit_plan": prediction.exit_plan.take_profit_plan,
                "warnings": prediction.risk_assessment.warnings + prediction.exit_plan.warnings,
            }
        )

    st.subheader("Active Features")
    st.code(", ".join(prediction.features.active_features[:40]) or "No active features")
