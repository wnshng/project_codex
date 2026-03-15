"""Exit and split-profit templates."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_ai_system.data.schemas.market import MarketContext
from trading_ai_system.signals.mtf_scoring import MTFSummary


@dataclass
class ExitPlan:
    stop_loss_policy: dict[str, object]
    take_profit_plan: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_exit_plan(context: MarketContext, mtf_summary: MTFSummary) -> ExitPlan:
    nearest_target_distance = context.get_state_float("nearest_target_distance", 0.02)
    heavy_first_tp = nearest_target_distance <= 0.01 or context.get_state_bool("target_reached_recently")
    take_profit_plan = [
        {
            "level": "TP1",
            "ratio": 0.50 if heavy_first_tp else 0.25,
            "reason": "1m/3m 목표 반응 구간",
        },
        {
            "level": "TP2",
            "ratio": 0.20 if heavy_first_tp else 0.25,
            "reason": "5m 타겟 또는 채널 상단/하단",
        },
        {
            "level": "TP3",
            "ratio": 0.15 if heavy_first_tp else 0.25,
            "reason": "15m 공통구간 / 피보나치 타겟",
        },
        {
            "level": "TP4",
            "ratio": 0.15 if heavy_first_tp else 0.25,
            "reason": "상위 TF 목표 또는 추세 추종 청산",
        },
    ]

    warnings: list[str] = []
    if context.get_state_bool("overlapping_target_zone"):
        warnings.append("중첩 타겟 구간이라 빠른 분할 청산이 유리합니다.")
    if context.get_state_bool("lower_tf_conflict_flag"):
        warnings.append("하위 프레임 잡음이 커서 잔여분 추세 추종을 보수화합니다.")

    direction = "long" if mtf_summary.composite_score >= 0 else "short"
    invalidation = "직전 스윙 저점" if direction == "long" else "직전 스윙 고점"
    stop_loss_policy = {
        "direction": direction,
        "anchor": invalidation,
        "stop_distance_ratio": context.get_state_float("stop_distance_ratio"),
        "time_stop_bars": int(context.get_state_float("time_stop_bars", 6)),
        "structural_exit": "패턴 실패 또는 공통구간 이탈 시 즉시 청산",
    }

    return ExitPlan(
        stop_loss_policy=stop_loss_policy,
        take_profit_plan=take_profit_plan,
        warnings=warnings,
    )
