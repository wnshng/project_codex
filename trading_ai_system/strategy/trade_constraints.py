"""Applies the rule registry and produces a single explainable rule outcome."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.data.schemas.market import MarketContext
from trading_ai_system.signals.mtf_scoring import MTFSummary
from trading_ai_system.strategy.rule_registry import (
    RuleRegistry,
    RuleResult,
    build_default_rule_registry,
)


@dataclass
class RuleEngineOutcome:
    rule_score: float
    entry_allowed: bool
    hard_reject: bool
    no_trade: bool
    no_trade_reasons: list[str]
    caution_mode: bool
    probe_only: bool
    results: list[RuleResult] = field(default_factory=list)

    @property
    def positive_reasons(self) -> list[str]:
        labels: list[str] = []
        for result in self.results:
            if result.passed and result.reason:
                labels.append(result.reason)
        return labels


def evaluate_trade_constraints(
    context: MarketContext,
    mtf_summary: MTFSummary,
    registry: Optional[RuleRegistry] = None,
    config: SystemConfig = DEFAULT_CONFIG,
) -> RuleEngineOutcome:
    registry = registry or build_default_rule_registry()
    results = registry.evaluate_all(context, mtf_summary, config)

    rule_score = sum(result.score_impact for result in results)
    hard_reject = any(result.hard_block for result in results)
    no_trade_reasons = [result.reason for result in results if not result.passed and result.reason]
    caution_mode = any(
        result.name in {"target_overlap_warning", "countertrend_probe_only"}
        and not result.passed
        for result in results
    )
    probe_only = any(bool(result.metadata.get("probe_only")) for result in results)

    no_trade = (
        hard_reject
        or context.get_state_bool("manual_no_trade")
        or rule_score <= -2.0
        or mtf_summary.regime_class == "event_risk"
    )
    entry_allowed = not no_trade and rule_score >= -0.25

    return RuleEngineOutcome(
        rule_score=rule_score,
        entry_allowed=entry_allowed,
        hard_reject=hard_reject,
        no_trade=no_trade,
        no_trade_reasons=no_trade_reasons,
        caution_mode=caution_mode,
        probe_only=probe_only,
        results=results,
    )
