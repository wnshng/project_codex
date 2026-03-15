"""Multi-timeframe scoring and probability priors."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.app.constants import CLASS_DOWN, CLASS_SIDE, CLASS_UP
from trading_ai_system.data.schemas.market import MarketContext, TimeframeState


@dataclass(slots=True)
class TimeframeScore:
    timeframe: str
    raw_score: float
    normalized_score: float
    bias: str
    weight: float
    weighted_score: float
    regime: str
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MTFSummary:
    timeframe_scores: dict[str, TimeframeScore]
    composite_score: float
    alignment_bonus: float
    conflict_penalty: float
    caution_penalty: float
    regime_class: str
    bias_probabilities: dict[str, float]
    warnings: list[str] = field(default_factory=list)


def _softmax(logits: dict[str, float]) -> dict[str, float]:
    max_logit = max(logits.values())
    exp_values = {name: math.exp(value - max_logit) for name, value in logits.items()}
    total = sum(exp_values.values())
    return {name: value / total for name, value in exp_values.items()}


def _score_timeframe(timeframe: str, state: TimeframeState, weight: float) -> TimeframeScore:
    weighted_score = state.normalized_score * weight * state.confidence
    notes = list(state.notes)
    if state.bias == "bull":
        notes.append(f"{timeframe} bullish structure")
    elif state.bias == "bear":
        notes.append(f"{timeframe} bearish structure")
    return TimeframeScore(
        timeframe=timeframe,
        raw_score=state.raw_score,
        normalized_score=state.normalized_score,
        bias=state.bias,
        weight=weight,
        weighted_score=weighted_score,
        regime=state.regime,
        notes=notes,
    )


def _score_sign(value: float) -> int:
    if value > 0.12:
        return 1
    if value < -0.12:
        return -1
    return 0


def _derive_regime(composite_score: float, warnings: list[str]) -> str:
    if any("event volatility" in warning.lower() for warning in warnings):
        return "event_risk"
    absolute = abs(composite_score)
    if absolute < 0.12:
        return "sideways"
    if absolute >= 0.45:
        return "trend"
    return "transition"


def compute_mtf_summary(
    context: MarketContext, config: SystemConfig = DEFAULT_CONFIG
) -> MTFSummary:
    timeframe_scores: dict[str, TimeframeScore] = {}
    warnings: list[str] = []
    composite_score = 0.0

    for timeframe, weight in config.timeframe_weights.items():
        state = context.timeframe(timeframe)
        if state is None:
            continue
        tf_score = _score_timeframe(timeframe, state, weight)
        timeframe_scores[timeframe] = tf_score
        composite_score += tf_score.weighted_score

    alignment_bonus = 0.0
    for higher_tf, lower_tf in (("1w", "1d"), ("1d", "4h"), ("4h", "1h")):
        higher = timeframe_scores.get(higher_tf)
        lower = timeframe_scores.get(lower_tf)
        if higher is None or lower is None:
            continue
        if _score_sign(higher.normalized_score) == _score_sign(lower.normalized_score) != 0:
            alignment_bonus += config.mtf_alignment_pair_bonus

    conflict_penalty = 0.0
    long_term = timeframe_scores.get("1d") or timeframe_scores.get("1w")
    for lower_tf in ("1h", "30m", "15m", "1m"):
        lower = timeframe_scores.get(lower_tf)
        if long_term is None or lower is None:
            continue
        if _score_sign(long_term.normalized_score) * _score_sign(lower.normalized_score) == -1:
            conflict_penalty += config.lower_tf_conflict_penalty

    caution_penalty = 0.0
    if context.get_state_bool("overlapping_target_zone") or context.get_state_bool("caution_zone_flag"):
        caution_penalty += config.caution_zone_penalty
        warnings.append("Overlapping target zone detected")
    if context.get_state_bool("lower_tf_conflict_flag"):
        caution_penalty += config.lower_tf_conflict_penalty
        warnings.append("Lower timeframe noise conflict detected")

    event_risk = context.get_state_str("event_volatility_risk").lower()
    if event_risk in {"high", "extreme"}:
        warnings.append("Event volatility risk is elevated")

    composite_score += alignment_bonus
    composite_score -= conflict_penalty + caution_penalty
    composite_score = max(-1.0, min(1.0, composite_score))

    priors = _softmax(
        {
            CLASS_UP: 1.9 * composite_score,
            CLASS_DOWN: -1.9 * composite_score,
            CLASS_SIDE: 0.8 - abs(composite_score),
        }
    )

    regime_class = _derive_regime(composite_score, warnings)

    return MTFSummary(
        timeframe_scores=timeframe_scores,
        composite_score=composite_score,
        alignment_bonus=alignment_bonus,
        conflict_penalty=conflict_penalty,
        caution_penalty=caution_penalty,
        regime_class=regime_class,
        bias_probabilities=priors,
        warnings=warnings,
    )
