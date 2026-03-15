"""Risk grading and position sizing."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.data.schemas.market import MarketContext
from trading_ai_system.signals.mtf_scoring import MTFSummary
from trading_ai_system.strategy.trade_constraints import RuleEngineOutcome


@dataclass(slots=True)
class RiskAssessment:
    risk_grade: str
    risk_points: int
    max_loss_pct: float
    position_notional: float | None
    position_fraction: float | None
    warnings: list[str] = field(default_factory=list)


def assess_risk(
    context: MarketContext,
    mtf_summary: MTFSummary,
    rule_outcome: RuleEngineOutcome,
    config: SystemConfig = DEFAULT_CONFIG,
) -> RiskAssessment:
    risk_points = 0
    warnings: list[str] = []

    if rule_outcome.hard_reject:
        risk_points += 3
        warnings.append("Hard reject 규칙이 발생했습니다.")
    if rule_outcome.caution_mode:
        risk_points += 1
        warnings.append("중첩 타겟 또는 역추세 probe-only 상황입니다.")
    if context.get_state_bool("countertrend"):
        risk_points += 1
        warnings.append("역추세 매매는 선발대만 허용됩니다.")
    if context.get_state_bool("chasing_risk"):
        risk_points += 2
        warnings.append("추격 진입 위험이 큽니다.")
    if not context.get_state_bool("stop_is_clear"):
        risk_points += 2
        warnings.append("손절 기준선이 명확하지 않습니다.")
    if context.get_state_str("event_volatility_risk").lower() in {"high", "extreme"}:
        risk_points += 2
        warnings.append("이벤트성 변동성 확대로 보수적 운영이 필요합니다.")
    if abs(mtf_summary.composite_score) < config.thresholds.weak_direction_threshold:
        risk_points += 1
        warnings.append("상위 방향성 우위가 약합니다.")
    if rule_outcome.rule_score >= 2 and abs(mtf_summary.composite_score) >= config.thresholds.strong_direction_threshold:
        risk_points = max(0, risk_points - 1)

    if risk_points >= 5:
        risk_grade = "HIGH"
    elif risk_points >= 2:
        risk_grade = "MEDIUM"
    else:
        risk_grade = "LOW"

    account_equity = context.get_state_float("account_equity")
    stop_distance_ratio = max(context.get_state_float("stop_distance_ratio"), 0.0001)
    risk_per_trade_pct = min(
        context.get_state_float("risk_per_trade_pct", config.risk.max_loss_per_trade_pct),
        config.risk.max_loss_per_trade_pct,
    )
    position_notional = None
    position_fraction = None
    if account_equity > 0:
        risk_capital = account_equity * risk_per_trade_pct
        position_notional = risk_capital / stop_distance_ratio
        position_fraction = min(position_notional / account_equity, 1.0)

    return RiskAssessment(
        risk_grade=risk_grade,
        risk_points=risk_points,
        max_loss_pct=risk_per_trade_pct,
        position_notional=position_notional,
        position_fraction=position_fraction,
        warnings=warnings,
    )
