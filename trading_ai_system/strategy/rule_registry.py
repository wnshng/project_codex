"""Document-derived rule registry for explainable trade filtering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.data.schemas.market import MarketContext
from trading_ai_system.signals.mtf_scoring import MTFSummary


@dataclass(slots=True)
class RuleResult:
    name: str
    category: str
    score_weight: float
    passed: bool
    score_impact: float
    hard_filter: bool
    hard_block: bool
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


RuleEvaluator = Callable[["Rule", MarketContext, MTFSummary, SystemConfig], RuleResult]


@dataclass(slots=True)
class Rule:
    name: str
    category: str
    score_weight: float
    hard_filter: bool
    evaluator: RuleEvaluator

    def evaluate(
        self,
        context: MarketContext,
        mtf_summary: MTFSummary,
        config: SystemConfig = DEFAULT_CONFIG,
    ) -> RuleResult:
        return self.evaluator(self, context, mtf_summary, config)


@dataclass(slots=True)
class RuleRegistry:
    rules: list[Rule]

    def evaluate_all(
        self,
        context: MarketContext,
        mtf_summary: MTFSummary,
        config: SystemConfig = DEFAULT_CONFIG,
    ) -> list[RuleResult]:
        return [rule.evaluate(context, mtf_summary, config) for rule in self.rules]


def _make_result(
    rule: Rule,
    passed: bool,
    reason: str | None = None,
    *,
    metadata: dict[str, object] | None = None,
    hard_block: bool | None = None,
    score_impact: float | None = None,
) -> RuleResult:
    if score_impact is None:
        score_impact = abs(rule.score_weight) if passed else -abs(rule.score_weight)
    if hard_block is None:
        hard_block = rule.hard_filter and not passed
    return RuleResult(
        name=rule.name,
        category=rule.category,
        score_weight=rule.score_weight,
        passed=passed,
        score_impact=score_impact,
        hard_filter=rule.hard_filter,
        hard_block=hard_block,
        reason=reason,
        metadata=metadata or {},
    )


def _direction(mtf_summary: MTFSummary) -> str:
    if mtf_summary.composite_score >= 0.18:
        return "long"
    if mtf_summary.composite_score <= -0.18:
        return "short"
    return "neutral"


def _eval_stop_clear(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    stop_clear = context.get_state_bool("stop_is_clear")
    stop_distance = context.get_state_float("stop_distance_ratio")
    passed = stop_clear and 0 < stop_distance <= config.risk.max_reasonable_stop_distance_ratio
    reason = None if passed else "손절 위치 불명확 또는 손절 거리가 과도함"
    return _make_result(
        rule,
        passed,
        reason,
        metadata={"stop_distance_ratio": stop_distance},
    )


def _eval_no_chasing(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    chasing = context.get_state_bool("chasing_risk")
    extension = context.get_state_float("distance_from_breakout_ratio")
    passed = not chasing and extension <= 0.03
    reason = None if passed else "추격 진입/FOMO 위험 구간"
    return _make_result(
        rule,
        passed,
        reason,
        metadata={"distance_from_breakout_ratio": extension},
    )


def _eval_pattern_confirmed(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    confirmed = any(
        [
            context.get_state_bool("pattern_confirmed"),
            context.get_state_bool("confirmation_entry"),
            context.get_state_bool("breakout_confirmed_flag"),
            context.get_state_bool("retest_success_flag"),
            context.get_state_bool("flag_breakout_volume_confirmed"),
            context.get_state_bool("triangle_breakout_volume_confirmed"),
            context.get_state_bool("hs_confirmed_breakout_flag"),
        ]
    )
    reason = None if confirmed else "패턴 컨펌 전 선진입 금지"
    return _make_result(rule, confirmed, reason)


def _eval_fourth_touch_risk(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    touch_count = context.get_state_float("sr_touch_count")
    explicit_risk = context.get_state_bool("fourth_touch_break_risk")
    passed = touch_count < 4 and not explicit_risk
    reason = None if passed else "4번째 이상 지지/저항 재터치 위험"
    return _make_result(rule, passed, reason, metadata={"sr_touch_count": touch_count})


def _eval_target_overlap(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    overlap = any(
        [
            context.get_state_bool("overlapping_target_zone"),
            context.get_state_bool("caution_zone_flag"),
            context.get_state_bool("sr_overlap_1m_3m_flag"),
            context.get_state_bool("sr_overlap_3m_5m_flag"),
            context.get_state_float("multi_tf_sr_density") >= 2.0,
        ]
    )
    reason = None if not overlap else "중첩 타겟/공통구간 한가운데"
    return _make_result(
        rule,
        not overlap,
        reason,
        hard_block=False,
        metadata={"caution_mode": overlap},
    )


def _eval_higher_tf_priority(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    direction = _direction(mtf_summary)
    higher = mtf_summary.timeframe_scores.get("1d") or mtf_summary.timeframe_scores.get("1w")
    lower = mtf_summary.timeframe_scores.get("1h") or mtf_summary.timeframe_scores.get("15m")
    aligned = higher is not None and lower is not None
    if aligned:
        higher_sign = 1 if higher.normalized_score > 0.12 else -1 if higher.normalized_score < -0.12 else 0
        lower_sign = 1 if lower.normalized_score > 0.12 else -1 if lower.normalized_score < -0.12 else 0
        aligned = higher_sign == lower_sign != 0
    if direction == "neutral":
        aligned = False
    reason = None if aligned else "상위 TF 방향 우선 원칙과 불일치"
    return _make_result(rule, aligned, reason, hard_block=False)


def _eval_lower_tf_exit_priority(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    enabled = context.get_state_bool("lower_tf_exit_priority", True)
    reason = None if enabled else "하위 TF 청산 우선 규칙 미반영"
    return _make_result(rule, enabled, reason, hard_block=False)


def _eval_split_execution(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    split_ready = any(
        [
            context.get_state_bool("split_entry_recommended", True),
            context.get_state_bool("partial_tp_enabled", True),
            context.get_state_bool("split_exit_ready", True),
        ]
    )
    reason = None if split_ready else "분할 진입/분할 익절 계획 없음"
    return _make_result(rule, split_ready, reason, hard_block=False)


def _eval_countertrend_probe_only(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    countertrend = context.get_state_bool("countertrend")
    reason = None if not countertrend else "역추세는 선발대만 허용"
    return _make_result(
        rule,
        not countertrend,
        reason,
        hard_block=False,
        metadata={"probe_only": countertrend},
        score_impact=abs(rule.score_weight) if not countertrend else -0.5 * abs(rule.score_weight),
    )


def _eval_one_candle_one_trade(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    violated = any(
        [
            context.get_state_bool("same_candle_reentry"),
            context.get_state_bool("one_candle_one_trade_violation"),
        ]
    )
    reason = None if not violated else "같은 봉 재진입 시도"
    return _make_result(rule, not violated, reason)


def _eval_event_volatility(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    risk_level = context.get_state_str("event_volatility_risk", "normal").lower()
    passed = risk_level not in {"high", "extreme"}
    reason = None if passed else "이벤트성 고변동성 구간"
    hard_block = risk_level == "extreme"
    return _make_result(
        rule,
        passed,
        reason,
        hard_block=hard_block,
        metadata={"event_volatility_risk": risk_level},
        score_impact=abs(rule.score_weight) if passed else -abs(rule.score_weight),
    )


def _eval_reward_risk_floor(
    rule: Rule,
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> RuleResult:
    reward_risk = context.get_state_float("reward_risk_ratio", 0.0)
    passed = reward_risk >= config.risk.minimum_reward_risk
    reason = None if passed else "기대수익비가 낮아 진입 비효율"
    return _make_result(
        rule,
        passed,
        reason,
        hard_block=False,
        metadata={"reward_risk_ratio": reward_risk},
    )


def build_default_rule_registry() -> RuleRegistry:
    return RuleRegistry(
        rules=[
            Rule("stop_clear", "risk", 1.5, True, _eval_stop_clear),
            Rule("no_chasing", "risk", 1.4, True, _eval_no_chasing),
            Rule("pattern_confirmed", "entry", 1.3, True, _eval_pattern_confirmed),
            Rule("fourth_touch_risk", "filter", 1.2, True, _eval_fourth_touch_risk),
            Rule("target_overlap_warning", "filter", 0.9, False, _eval_target_overlap),
            Rule("higher_tf_priority", "entry", 1.1, False, _eval_higher_tf_priority),
            Rule("lower_tf_exit_priority", "exit", 0.5, False, _eval_lower_tf_exit_priority),
            Rule("split_execution", "position", 0.6, False, _eval_split_execution),
            Rule("countertrend_probe_only", "entry", 0.8, False, _eval_countertrend_probe_only),
            Rule("one_candle_one_trade", "filter", 1.0, True, _eval_one_candle_one_trade),
            Rule("event_volatility_filter", "filter", 1.1, True, _eval_event_volatility),
            Rule("reward_risk_floor", "risk", 0.7, False, _eval_reward_risk_floor),
        ]
    )
