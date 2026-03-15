"""Curated feature catalog aligned to the requested strategy design."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    group: str
    description: str
    default: float | int | bool | str | None = 0.0
    source_hint: str = ""


def _spec(
    name: str,
    group: str,
    description: str,
    *,
    default: float | int | bool | str | None = 0.0,
    source_hint: str = "",
) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        group=group,
        description=description,
        default=default,
        source_hint=source_hint,
    )


FEATURE_CATALOG = [
    _spec("return_1_bar", "price", "1-bar return"),
    _spec("return_3_bar", "price", "3-bar return"),
    _spec("return_5_bar", "price", "5-bar return"),
    _spec("return_10_bar", "price", "10-bar return"),
    _spec("gap_ratio", "price", "Gap ratio"),
    _spec("high_low_range_pct", "price", "High-low range %"),
    _spec("body_pct", "price", "Close-open body %"),
    _spec("upper_wick_ratio", "price", "Upper wick ratio"),
    _spec("lower_wick_ratio", "price", "Lower wick ratio"),
    _spec("ema_5_20_spread", "trend", "EMA5-EMA20 spread"),
    _spec("ema_20_50_spread", "trend", "EMA20-EMA50 spread"),
    _spec("ema_50_200_spread", "trend", "EMA50-EMA200 spread"),
    _spec("price_above_ema20_flag", "trend", "Price above EMA20 flag", default=False),
    _spec("price_above_ema50_flag", "trend", "Price above EMA50 flag", default=False),
    _spec("macd_line", "trend", "MACD line"),
    _spec("macd_signal", "trend", "MACD signal"),
    _spec("macd_histogram", "trend", "MACD histogram"),
    _spec("adx", "trend", "ADX14"),
    _spec("psar_trend_flag", "trend", "Parabolic SAR trend flag", default=False),
    _spec("rsi14", "momentum", "RSI14"),
    _spec("rsi_slope", "momentum", "RSI slope"),
    _spec("stoch_k", "momentum", "Stochastic K"),
    _spec("stoch_d", "momentum", "Stochastic D"),
    _spec("cci20", "momentum", "CCI20"),
    _spec("williams_r", "momentum", "Williams %R"),
    _spec("bullish_divergence_flag", "momentum", "Bullish divergence flag", default=False),
    _spec("bearish_divergence_flag", "momentum", "Bearish divergence flag", default=False),
    _spec("bb_width", "volatility", "Bollinger Band width"),
    _spec("bb_position", "volatility", "Price position inside BB"),
    _spec("atr14", "volatility", "ATR14"),
    _spec("atr_close_ratio", "volatility", "ATR / close"),
    _spec("keltner_upper_distance", "volatility", "Keltner upper distance"),
    _spec("keltner_lower_distance", "volatility", "Keltner lower distance"),
    _spec("squeeze_flag", "volatility", "BB squeeze flag", default=False),
    _spec("obv_slope", "volume", "OBV slope"),
    _spec("vwap_distance", "volume", "VWAP distance"),
    _spec("volume_to_ma20", "volume", "Volume / Volume MA20"),
    _spec("mfi14", "volume", "MFI14"),
    _spec("volume_spike_flag", "volume", "Volume spike flag", default=False),
    _spec("doji_flag", "pattern", "Doji flag", default=False),
    _spec("hammer_flag", "pattern", "Hammer flag", default=False),
    _spec("engulfing_bull_flag", "pattern", "Bullish engulfing flag", default=False),
    _spec("engulfing_bear_flag", "pattern", "Bearish engulfing flag", default=False),
    _spec("morning_star_flag", "pattern", "Morning star flag", default=False),
    _spec("flag_pattern_confirmed", "pattern", "Flag pattern confirmation", default=False),
    _spec("wedge_breakout_flag", "pattern", "Wedge breakout flag", default=False),
    _spec("head_shoulders_confirmed", "pattern", "Head and shoulders confirmation", default=False),
    _spec("triangle_breakout_flag", "pattern", "Triangle breakout flag", default=False),
    _spec("estimated_wave_stage", "wave", "Estimated Elliott wave stage", default="unknown", source_hint="glenn_neely"),
    _spec("impulse_candidate_flag", "wave", "Impulse candidate flag", default=False, source_hint="summary_doc"),
    _spec("corrective_candidate_flag", "wave", "Corrective candidate flag", default=False, source_hint="summary_doc"),
    _spec("fib_retracement_zone_class", "wave", "Fibonacci retracement zone class", default="none"),
    _spec("fib_extension_zone_class", "wave", "Fibonacci extension zone class", default="none"),
    _spec("common_zone_hit_flag", "wave", "Common-zone hit flag", default=False, source_hint="summary_doc"),
    _spec("fifth_wave_exhaustion_flag", "wave", "5th-wave exhaustion flag", default=False, source_hint="glenn_neely"),
    _spec("abc_completion_flag", "wave", "ABC completion flag", default=False, source_hint="summary_doc"),
    _spec("nearest_target_distance", "target_zone", "Distance to nearest target"),
    _spec("target_reached_recently_flag", "target_zone", "Target reached recently", default=False),
    _spec("overlapping_target_zone_flag", "target_zone", "Overlapping target zone flag", default=False, source_hint="chaseol_manual"),
    _spec("entry_signal_on_3m", "target_zone", "Entry signal on 3m", default=False, source_hint="chaseol_manual"),
    _spec("entry_signal_on_5m", "target_zone", "Entry signal on 5m", default=False, source_hint="chaseol_manual"),
    _spec("entry_signal_on_15m", "target_zone", "Entry signal on 15m", default=False, source_hint="chaseol_manual"),
    _spec("target_zone_from_1m_flag", "target_zone", "Target zone from 1m", default=False, source_hint="chaseol_manual"),
    _spec("lower_tf_exit_priority_flag", "target_zone", "Lower timeframe exit priority flag", default=False, source_hint="chaseol_manual"),
    _spec("split_entry_recommended_flag", "target_zone", "Split entry recommended flag", default=False, source_hint="spd_rules"),
    _spec("stop_distance_ratio", "spd_rules", "Stop distance ratio", source_hint="spd_rules"),
    _spec("stop_is_clear_flag", "spd_rules", "Stop is clear flag", default=False, source_hint="spd_rules"),
    _spec("chasing_risk_flag", "spd_rules", "Chasing risk flag", default=False, source_hint="spd_rules"),
    _spec("confirmation_entry_flag", "spd_rules", "Confirmation entry flag", default=False, source_hint="spd_rules"),
    _spec("fourth_touch_break_risk_flag", "spd_rules", "Fourth-touch break risk flag", default=False, source_hint="summary_doc"),
    _spec("anti_fomo_filter_flag", "spd_rules", "Anti-FOMO filter", default=False, source_hint="spd_rules"),
    _spec("one_candle_one_trade_flag", "spd_rules", "One candle one trade flag", default=False, source_hint="spd_rules"),
    _spec("alignment_1d_4h", "mtf", "1D and 4H alignment", default=False),
    _spec("alignment_4h_1h", "mtf", "4H and 1H alignment", default=False),
    _spec("alignment_1h_15m", "mtf", "1H and 15m alignment", default=False),
    _spec("short_vs_long_tf_conflict", "mtf", "Short vs long timeframe conflict", default=False),
    _spec("higher_tf_trend_strength", "mtf", "Higher timeframe trend strength"),
    _spec("consensus_score", "mtf", "MTF consensus score"),
    _spec("regime_class", "mtf", "Regime class", default="sideways"),
    _spec("no_trade_flag", "mtf", "No-trade flag", default=False),
]

FEATURE_INDEX = {spec.name: spec for spec in FEATURE_CATALOG}
