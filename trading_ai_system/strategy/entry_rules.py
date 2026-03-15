"""Entry decision logic derived from MTF state and rule-engine outcome."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.app.constants import (
    ENTRY_ALLOW_FULL,
    ENTRY_ALLOW_PROBE,
    ENTRY_CONFIRMED_BREAKOUT,
    ENTRY_PULLBACK,
    ENTRY_REJECT,
    ENTRY_REVERSAL_PROBE,
)
from trading_ai_system.data.schemas.market import MarketContext
from trading_ai_system.signals.mtf_scoring import MTFSummary
from trading_ai_system.strategy.trade_constraints import RuleEngineOutcome


@dataclass
class EntryPlan:
    decision: str
    direction: str
    entry_type: str
    reasons: list[str] = field(default_factory=list)
    split_entry_plan: list[dict[str, object]] = field(default_factory=list)


def _direction(mtf_summary: MTFSummary) -> str:
    if mtf_summary.composite_score >= 0.18:
        return "long"
    if mtf_summary.composite_score <= -0.18:
        return "short"
    return "neutral"


def build_entry_plan(
    context: MarketContext,
    mtf_summary: MTFSummary,
    rule_outcome: RuleEngineOutcome,
    config: SystemConfig = DEFAULT_CONFIG,
) -> EntryPlan:
    direction = _direction(mtf_summary)
    if rule_outcome.no_trade or direction == "neutral":
        return EntryPlan(
            decision=ENTRY_REJECT,
            direction=direction,
            entry_type="none",
            reasons=rule_outcome.no_trade_reasons or ["방향성 부족 또는 no-trade"],
        )

    breakout_confirmed = any(
        [
            context.get_state_bool("breakout_confirmed_flag"),
            context.get_state_bool("retest_success_flag"),
            context.get_state_bool("close_above_key_level_flag"),
            context.get_state_bool("close_below_key_level_flag"),
        ]
    )
    pullback_ready = any(
        [
            context.get_state_bool("pullback_entry_ready"),
            context.get_state_bool("ema_support_hold"),
            context.get_state_bool("vwap_support_hold"),
            context.get_state_bool("common_zone_hit_flag"),
        ]
    )
    reversal_probe = any(
        [
            context.get_state_bool("bullish_divergence_flag"),
            context.get_state_bool("bearish_divergence_flag"),
            context.get_state_bool("fifth_wave_exhaustion_flag"),
            context.get_state_bool("abc_completion_flag"),
            context.get_state_bool("reversal_setup"),
        ]
    )

    if rule_outcome.probe_only or context.get_state_bool("countertrend"):
        return EntryPlan(
            decision=ENTRY_ALLOW_PROBE,
            direction=direction,
            entry_type=ENTRY_REVERSAL_PROBE,
            reasons=["역추세 또는 전환 초입이므로 선발대만 허용"],
            split_entry_plan=[
                {"stage": "probe", "ratio": 0.25, "trigger": "1차 확인 진입"},
                {"stage": "reserve", "ratio": 0.75, "trigger": "추세 전환 컨펌 후만 허용"},
            ],
        )

    if breakout_confirmed and abs(mtf_summary.composite_score) >= config.thresholds.weak_direction_threshold:
        return EntryPlan(
            decision=ENTRY_ALLOW_FULL,
            direction=direction,
            entry_type=ENTRY_CONFIRMED_BREAKOUT,
            reasons=["돌파/이탈 후 리테스트 확인", "상위 프레임 방향과 정합"],
            split_entry_plan=[
                {"stage": "starter", "ratio": 0.40, "trigger": "돌파 종가 확인"},
                {"stage": "main", "ratio": 0.35, "trigger": "리테스트 성공"},
                {"stage": "add", "ratio": 0.25, "trigger": "후속 거래량 확인"},
            ],
        )

    if pullback_ready and abs(mtf_summary.composite_score) >= config.thresholds.weak_direction_threshold:
        return EntryPlan(
            decision=ENTRY_ALLOW_FULL,
            direction=direction,
            entry_type=ENTRY_PULLBACK,
            reasons=["상위 추세 유지 상태의 눌림/되돌림 자리"],
            split_entry_plan=[
                {"stage": "starter", "ratio": 0.35, "trigger": "지지 확인"},
                {"stage": "main", "ratio": 0.35, "trigger": "1차 반응 성공"},
                {"stage": "add", "ratio": 0.30, "trigger": "재돌파 확인"},
            ],
        )

    if reversal_probe:
        return EntryPlan(
            decision=ENTRY_ALLOW_PROBE,
            direction=direction,
            entry_type=ENTRY_REVERSAL_PROBE,
            reasons=["다이버전스/엔딩 패턴 기반 반전 탐색"],
            split_entry_plan=[
                {"stage": "probe", "ratio": 0.20, "trigger": "반전 시그널 확인"},
                {"stage": "main", "ratio": 0.80, "trigger": "상위 TF 동조 시만 허용"},
            ],
        )

    return EntryPlan(
        decision=ENTRY_REJECT,
        direction=direction,
        entry_type="none",
        reasons=["확인 진입 조건 부족"],
    )
