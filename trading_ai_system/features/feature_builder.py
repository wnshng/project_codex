"""Feature builder that converts MTF state and rule results into model-ready values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from trading_ai_system.data.schemas.market import MarketContext, TimeframeState
from trading_ai_system.features.feature_catalog import FEATURE_CATALOG
from trading_ai_system.signals.mtf_scoring import MTFSummary
from trading_ai_system.strategy.risk_manager import RiskAssessment
from trading_ai_system.strategy.trade_constraints import RuleEngineOutcome


FeatureValue = Union[float, int, bool, str, None]


@dataclass
class BuiltFeatures:
    values: dict[str, FeatureValue]
    active_features: list[str] = field(default_factory=list)


def _first_available_state(context: MarketContext) -> Optional[TimeframeState]:
    for timeframe in ("1h", "4h", "1d", "15m", "30m", "1m", "1w"):
        state = context.timeframe(timeframe)
        if state is not None:
            return state
    return None


def _alignment(summary: MTFSummary, higher: str, lower: str) -> bool:
    higher_state = summary.timeframe_scores.get(higher)
    lower_state = summary.timeframe_scores.get(lower)
    if higher_state is None or lower_state is None:
        return False
    if higher_state.normalized_score > 0.12 and lower_state.normalized_score > 0.12:
        return True
    if higher_state.normalized_score < -0.12 and lower_state.normalized_score < -0.12:
        return True
    return False


def _higher_tf_strength(summary: MTFSummary) -> float:
    strength = 0.0
    total_weight = 0.0
    for timeframe in ("1w", "1d", "4h"):
        score = summary.timeframe_scores.get(timeframe)
        if score is None:
            continue
        strength += abs(score.normalized_score) * score.weight
        total_weight += score.weight
    return strength / total_weight if total_weight else 0.0


def build_feature_row(
    context: MarketContext,
    mtf_summary: MTFSummary,
    rule_outcome: RuleEngineOutcome,
    risk_assessment: Optional[RiskAssessment] = None,
) -> BuiltFeatures:
    features: dict[str, FeatureValue] = {
        spec.name: spec.default for spec in FEATURE_CATALOG
    }
    active_features: list[str] = []

    anchor = _first_available_state(context)
    if anchor is not None:
        features.update(
            {
                "return_1_bar": anchor.get_float("return_1_bar"),
                "return_3_bar": anchor.get_float("return_3_bar"),
                "return_5_bar": anchor.get_float("return_5_bar"),
                "return_10_bar": anchor.get_float("return_10_bar"),
                "gap_ratio": anchor.get_float("gap_ratio"),
                "high_low_range_pct": anchor.get_float("high_low_range_pct"),
                "body_pct": anchor.get_float("body_pct"),
                "upper_wick_ratio": anchor.get_float("upper_wick_ratio"),
                "lower_wick_ratio": anchor.get_float("lower_wick_ratio"),
                "ema_5_20_spread": anchor.get_float("ema5") - anchor.get_float("ema20"),
                "ema_20_50_spread": anchor.get_float("ema20") - anchor.get_float("ema50"),
                "ema_50_200_spread": anchor.get_float("ema50") - anchor.get_float("ema200"),
                "price_above_ema20_flag": anchor.get_bool("price_above_ema20_flag"),
                "price_above_ema50_flag": anchor.get_bool("price_above_ema50_flag"),
                "macd_line": anchor.get_float("macd_line"),
                "macd_signal": anchor.get_float("macd_signal"),
                "macd_histogram": anchor.get_float("macd_histogram"),
                "adx": anchor.get_float("adx"),
                "psar_trend_flag": anchor.get_bool("psar_trend_flag"),
                "rsi14": anchor.get_float("rsi14"),
                "rsi_slope": anchor.get_float("rsi_slope"),
                "stoch_k": anchor.get_float("stoch_k"),
                "stoch_d": anchor.get_float("stoch_d"),
                "cci20": anchor.get_float("cci20"),
                "williams_r": anchor.get_float("williams_r"),
                "bullish_divergence_flag": anchor.get_bool("bullish_divergence_flag"),
                "bearish_divergence_flag": anchor.get_bool("bearish_divergence_flag"),
                "bb_width": anchor.get_float("bb_width"),
                "bb_position": anchor.get_float("bb_position"),
                "atr14": anchor.get_float("atr14"),
                "atr_close_ratio": anchor.get_float("atr_close_ratio"),
                "keltner_upper_distance": anchor.get_float("keltner_upper_distance"),
                "keltner_lower_distance": anchor.get_float("keltner_lower_distance"),
                "squeeze_flag": anchor.get_bool("squeeze_flag"),
                "obv_slope": anchor.get_float("obv_slope"),
                "vwap_distance": anchor.get_float("vwap_distance"),
                "volume_to_ma20": anchor.get_float("volume_to_ma20"),
                "mfi14": anchor.get_float("mfi14"),
                "volume_spike_flag": anchor.get_bool("volume_spike_flag"),
                "doji_flag": anchor.get_bool("doji_flag"),
                "hammer_flag": anchor.get_bool("hammer_flag"),
                "engulfing_bull_flag": anchor.get_bool("engulfing_bull_flag"),
                "engulfing_bear_flag": anchor.get_bool("engulfing_bear_flag"),
                "morning_star_flag": anchor.get_bool("morning_star_flag"),
                "flag_pattern_confirmed": anchor.get_bool("flag_pattern_confirmed"),
                "wedge_breakout_flag": anchor.get_bool("wedge_breakout_flag"),
                "head_shoulders_confirmed": anchor.get_bool("head_shoulders_confirmed"),
                "triangle_breakout_flag": anchor.get_bool("triangle_breakout_flag"),
                "estimated_wave_stage": str(anchor.signals.get("estimated_wave_stage", "unknown")),
                "impulse_candidate_flag": anchor.get_bool("impulse_candidate_flag"),
                "corrective_candidate_flag": anchor.get_bool("corrective_candidate_flag"),
                "fib_retracement_zone_class": str(anchor.signals.get("fib_retracement_zone_class", "none")),
                "fib_extension_zone_class": str(anchor.signals.get("fib_extension_zone_class", "none")),
                "common_zone_hit_flag": anchor.get_bool("common_zone_hit_flag"),
                "fifth_wave_exhaustion_flag": anchor.get_bool("fifth_wave_exhaustion_flag"),
                "abc_completion_flag": anchor.get_bool("abc_completion_flag"),
            }
        )

    features.update(
        {
            "nearest_target_distance": context.get_state_float("nearest_target_distance"),
            "target_reached_recently_flag": context.get_state_bool("target_reached_recently"),
            "overlapping_target_zone_flag": context.get_state_bool("overlapping_target_zone"),
            "entry_signal_on_3m": context.get_state_bool("entry_signal_on_3m"),
            "entry_signal_on_5m": context.get_state_bool("entry_signal_on_5m"),
            "entry_signal_on_15m": context.get_state_bool("entry_signal_on_15m"),
            "target_zone_from_1m_flag": context.get_state_bool("target_zone_from_1m_flag"),
            "lower_tf_exit_priority_flag": context.get_state_bool("lower_tf_exit_priority", True),
            "split_entry_recommended_flag": context.get_state_bool("split_entry_recommended", True),
            "stop_distance_ratio": context.get_state_float("stop_distance_ratio"),
            "stop_is_clear_flag": context.get_state_bool("stop_is_clear"),
            "chasing_risk_flag": context.get_state_bool("chasing_risk"),
            "confirmation_entry_flag": context.get_state_bool("confirmation_entry"),
            "fourth_touch_break_risk_flag": context.get_state_bool("fourth_touch_break_risk"),
            "anti_fomo_filter_flag": not context.get_state_bool("chasing_risk"),
            "one_candle_one_trade_flag": not context.get_state_bool("same_candle_reentry"),
            "alignment_1d_4h": _alignment(mtf_summary, "1d", "4h"),
            "alignment_4h_1h": _alignment(mtf_summary, "4h", "1h"),
            "alignment_1h_15m": _alignment(mtf_summary, "1h", "15m"),
            "short_vs_long_tf_conflict": context.get_state_bool("lower_tf_conflict_flag"),
            "higher_tf_trend_strength": _higher_tf_strength(mtf_summary),
            "consensus_score": mtf_summary.composite_score,
            "regime_class": mtf_summary.regime_class,
            "no_trade_flag": rule_outcome.no_trade,
        }
    )

    if risk_assessment is not None:
        features["anti_fomo_filter_flag"] = features["anti_fomo_filter_flag"] and risk_assessment.risk_grade != "HIGH"

    for name, value in features.items():
        if isinstance(value, bool) and value:
            active_features.append(name)
        elif isinstance(value, (int, float)) and value not in (0, 0.0):
            active_features.append(name)
        elif isinstance(value, str) and value not in {"", "none", "unknown", "sideways"}:
            active_features.append(name)

    return BuiltFeatures(values=features, active_features=sorted(set(active_features)))
