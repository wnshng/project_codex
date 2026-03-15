"""Default configuration values for the trading AI system."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_ai_system.app.constants import MODEL_WEIGHTS, TIMEFRAME_WEIGHTS


@dataclass(frozen=True)
class ThresholdConfig:
    bullish_raw_score: float = 3.0
    bearish_raw_score: float = -3.0
    weak_direction_threshold: float = 0.18
    strong_direction_threshold: float = 0.45
    high_confidence_threshold: float = 0.70
    medium_confidence_threshold: float = 0.55


@dataclass(frozen=True)
class RiskConfig:
    max_loss_per_trade_pct: float = 0.05
    max_daily_loss_pct: float = 0.10
    consecutive_loss_limit: int = 3
    minimum_reward_risk: float = 1.5
    max_reasonable_stop_distance_ratio: float = 0.03


@dataclass(frozen=True)
class SystemConfig:
    timeframe_weights: dict[str, float] = field(
        default_factory=lambda: dict(TIMEFRAME_WEIGHTS)
    )
    model_weights: dict[str, float] = field(default_factory=lambda: dict(MODEL_WEIGHTS))
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    mtf_alignment_pair_bonus: float = 0.025
    lower_tf_conflict_penalty: float = 0.03
    caution_zone_penalty: float = 0.12
    rule_score_normalizer: float = 8.0
    final_score_weights: dict[str, float] = field(
        default_factory=lambda: {"mtf": 0.35, "rule": 0.25, "model": 0.40}
    )


DEFAULT_CONFIG = SystemConfig()
