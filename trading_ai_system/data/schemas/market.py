"""Schema objects shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trading_ai_system.app.constants import MAX_TIMEFRAME_COMPONENT_SCORE

Scalar = float | int | bool | str | None

_TF_ALIASES = {
    "1w": "1w",
    "1wk": "1w",
    "1d": "1d",
    "1day": "1d",
    "4h": "4h",
    "1h": "1h",
    "60m": "1h",
    "30m": "30m",
    "15m": "15m",
    "1m": "1m",
}


def canonical_timeframe(timeframe: str) -> str:
    return _TF_ALIASES.get(timeframe.strip().lower(), timeframe.strip().lower())


@dataclass(slots=True)
class TimeframeState:
    timeframe: str
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    volume_score: float = 0.0
    pattern_score: float = 0.0
    target_score: float = 0.0
    confidence: float = 1.0
    regime: str = "neutral"
    signals: dict[str, Scalar] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.timeframe = canonical_timeframe(self.timeframe)
        self.confidence = max(0.0, min(1.0, float(self.confidence)))

    @property
    def raw_score(self) -> float:
        return (
            self.trend_score
            + self.momentum_score
            + self.volatility_score
            + self.volume_score
            + self.pattern_score
            + self.target_score
        )

    @property
    def normalized_score(self) -> float:
        normalized = self.raw_score / MAX_TIMEFRAME_COMPONENT_SCORE
        return max(-1.0, min(1.0, normalized))

    @property
    def bias(self) -> str:
        if self.raw_score >= 3:
            return "bull"
        if self.raw_score <= -3:
            return "bear"
        return "neutral"

    def get_float(self, key: str, default: float = 0.0) -> float:
        value = self.signals.get(key, default)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.signals.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "bull", "on"}
        return bool(value)


@dataclass(slots=True)
class ModelProbabilities:
    model_name: str
    up: float
    down: float
    side: float
    feature_importance: list[tuple[str, float]] = field(default_factory=list)

    def normalized(self) -> "ModelProbabilities":
        up = max(0.0, self.up)
        down = max(0.0, self.down)
        side = max(0.0, self.side)
        total = up + down + side
        if total <= 0:
            return ModelProbabilities(
                model_name=self.model_name,
                up=1 / 3,
                down=1 / 3,
                side=1 / 3,
                feature_importance=list(self.feature_importance),
            )
        return ModelProbabilities(
            model_name=self.model_name,
            up=up / total,
            down=down / total,
            side=side / total,
            feature_importance=list(self.feature_importance),
        )

    def as_dict(self) -> dict[str, float]:
        normalized = self.normalized()
        return {
            "up": normalized.up,
            "down": normalized.down,
            "side": normalized.side,
        }


@dataclass(slots=True)
class MarketContext:
    symbol: str
    asset_type: str
    exchange: str
    mode: str
    current_price: float | None = None
    timestamp: str | None = None
    timeframes: dict[str, TimeframeState] = field(default_factory=dict)
    strategy_state: dict[str, Scalar] = field(default_factory=dict)
    model_outputs: dict[str, ModelProbabilities] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.timeframes = {
            canonical_timeframe(name): state for name, state in self.timeframes.items()
        }

    def timeframe(self, timeframe: str) -> TimeframeState | None:
        return self.timeframes.get(canonical_timeframe(timeframe))

    def get_state_float(self, key: str, default: float = 0.0) -> float:
        value = self.strategy_state.get(key, default)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def get_state_bool(self, key: str, default: bool = False) -> bool:
        value = self.strategy_state.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "bull"}
        return bool(value)

    def get_state_str(self, key: str, default: str = "") -> str:
        value = self.strategy_state.get(key, default)
        if value is None:
            return default
        return str(value)

    def to_debug_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type,
            "exchange": self.exchange,
            "mode": self.mode,
            "current_price": self.current_price,
            "timeframes": {
                timeframe: {
                    "raw_score": state.raw_score,
                    "bias": state.bias,
                    "signals": state.signals,
                }
                for timeframe, state in self.timeframes.items()
            },
            "strategy_state": self.strategy_state,
            "model_outputs": {
                name: output.as_dict() for name, output in self.model_outputs.items()
            },
        }
