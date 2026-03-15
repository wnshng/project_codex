"""Final prediction pipeline that layers MTF, rules, risk, and model outputs."""

from __future__ import annotations

from dataclasses import dataclass, field

from trading_ai_system.app.config import DEFAULT_CONFIG, SystemConfig
from trading_ai_system.app.constants import (
    CLASS_DOWN,
    CLASS_ORDER,
    CLASS_SIDE,
    CLASS_UP,
)
from trading_ai_system.data.schemas.market import MarketContext, ModelProbabilities
from trading_ai_system.features.feature_builder import BuiltFeatures, build_feature_row
from trading_ai_system.signals.mtf_scoring import MTFSummary, compute_mtf_summary
from trading_ai_system.strategy.entry_rules import EntryPlan, build_entry_plan
from trading_ai_system.strategy.exit_rules import ExitPlan, build_exit_plan
from trading_ai_system.strategy.risk_manager import RiskAssessment, assess_risk
from trading_ai_system.strategy.trade_constraints import (
    RuleEngineOutcome,
    evaluate_trade_constraints,
)


@dataclass
class FinalPrediction:
    probabilities: dict[str, float]
    predicted_class: str
    confidence_grade: str
    final_action: str
    decision_score: float
    mtf_summary: MTFSummary
    rule_outcome: RuleEngineOutcome
    risk_assessment: RiskAssessment
    entry_plan: EntryPlan
    exit_plan: ExitPlan
    features: BuiltFeatures
    top_reasons: list[str] = field(default_factory=list)
    model_blend: dict[str, dict[str, float]] = field(default_factory=dict)


def _normalize_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    total = sum(probabilities.values())
    if total <= 0:
        return {CLASS_UP: 1 / 3, CLASS_DOWN: 1 / 3, CLASS_SIDE: 1 / 3}
    return {label: value / total for label, value in probabilities.items()}


def _default_model_output(name: str, priors: dict[str, float]) -> ModelProbabilities:
    return ModelProbabilities(
        model_name=name,
        up=priors[CLASS_UP],
        down=priors[CLASS_DOWN],
        side=priors[CLASS_SIDE],
    )


def _soft_vote(
    context: MarketContext,
    mtf_summary: MTFSummary,
    config: SystemConfig,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    blended = {label: 0.0 for label in CLASS_ORDER}
    model_blend: dict[str, dict[str, float]] = {}
    total_weight = 0.0

    for name, weight in config.model_weights.items():
        output = context.model_outputs.get(name, _default_model_output(name, mtf_summary.bias_probabilities))
        normalized = output.normalized().as_dict()
        model_blend[name] = normalized
        total_weight += weight
        for label in CLASS_ORDER:
            blended[label] += normalized[label] * weight

    if total_weight <= 0:
        return mtf_summary.bias_probabilities, model_blend
    return _normalize_probabilities(blended), model_blend


def _confidence_grade(
    probabilities: dict[str, float],
    mtf_summary: MTFSummary,
    rule_outcome: RuleEngineOutcome,
    config: SystemConfig,
) -> str:
    confidence = max(probabilities.values())
    if confidence >= config.thresholds.high_confidence_threshold:
        grade = "HIGH"
    elif confidence >= config.thresholds.medium_confidence_threshold:
        grade = "MEDIUM"
    else:
        grade = "LOW"

    if rule_outcome.caution_mode or mtf_summary.conflict_penalty > 0:
        if grade == "HIGH":
            return "MEDIUM"
        if grade == "MEDIUM":
            return "LOW"
    return grade


def _final_action(
    decision_score: float,
    predicted_class: str,
    rule_outcome: RuleEngineOutcome,
    risk_assessment: RiskAssessment,
) -> str:
    if rule_outcome.no_trade or rule_outcome.hard_reject:
        return "NO_TRADE"
    if risk_assessment.risk_grade == "HIGH" and rule_outcome.caution_mode:
        return "NO_TRADE"
    if predicted_class == CLASS_UP:
        if decision_score >= 0.45:
            return "STRONG_LONG"
        if decision_score >= 0.18:
            return "WEAK_LONG"
    if predicted_class == CLASS_DOWN:
        if decision_score <= -0.45:
            return "STRONG_SHORT"
        if decision_score <= -0.18:
            return "WEAK_SHORT"
    return "NEUTRAL"


def _top_reasons(
    mtf_summary: MTFSummary,
    rule_outcome: RuleEngineOutcome,
    entry_plan: EntryPlan,
    context: MarketContext,
) -> list[str]:
    reasons: list[str] = []
    if mtf_summary.composite_score >= 0.18:
        reasons.append("상위 프레임 상승 정합")
    elif mtf_summary.composite_score <= -0.18:
        reasons.append("상위 프레임 하락 정합")
    reasons.extend(entry_plan.reasons)
    if context.get_state_bool("breakout_confirmed_flag"):
        reasons.append("돌파/이탈 후 확인 진입")
    if context.get_state_bool("retest_success_flag"):
        reasons.append("리테스트 성공")
    if context.get_state_bool("bullish_divergence_flag"):
        reasons.append("상승 다이버전스")
    if context.get_state_bool("bearish_divergence_flag"):
        reasons.append("하락 다이버전스")
    reasons.extend(rule_outcome.no_trade_reasons[:2])
    deduped: list[str] = []
    for reason in reasons:
        if reason and reason not in deduped:
            deduped.append(reason)
    return deduped[:5]


def run_pipeline(
    context: MarketContext, config: SystemConfig = DEFAULT_CONFIG
) -> FinalPrediction:
    mtf_summary = compute_mtf_summary(context, config)
    rule_outcome = evaluate_trade_constraints(context, mtf_summary, config=config)
    risk_assessment = assess_risk(context, mtf_summary, rule_outcome, config)
    entry_plan = build_entry_plan(context, mtf_summary, rule_outcome, config)
    exit_plan = build_exit_plan(context, mtf_summary)
    features = build_feature_row(context, mtf_summary, rule_outcome, risk_assessment)

    ensemble_probabilities, model_blend = _soft_vote(context, mtf_summary, config)
    model_score = ensemble_probabilities[CLASS_UP] - ensemble_probabilities[CLASS_DOWN]
    normalized_rule_score = max(
        -1.0, min(1.0, rule_outcome.rule_score / config.rule_score_normalizer)
    )
    decision_score = (
        config.final_score_weights["mtf"] * mtf_summary.composite_score
        + config.final_score_weights["rule"] * normalized_rule_score
        + config.final_score_weights["model"] * model_score
    )
    predicted_class = max(ensemble_probabilities, key=ensemble_probabilities.get)
    confidence_grade = _confidence_grade(
        ensemble_probabilities,
        mtf_summary,
        rule_outcome,
        config,
    )
    final_action = _final_action(
        decision_score,
        predicted_class,
        rule_outcome,
        risk_assessment,
    )

    return FinalPrediction(
        probabilities=ensemble_probabilities,
        predicted_class=predicted_class,
        confidence_grade=confidence_grade,
        final_action=final_action,
        decision_score=decision_score,
        mtf_summary=mtf_summary,
        rule_outcome=rule_outcome,
        risk_assessment=risk_assessment,
        entry_plan=entry_plan,
        exit_plan=exit_plan,
        features=features,
        top_reasons=_top_reasons(mtf_summary, rule_outcome, entry_plan, context),
        model_blend=model_blend,
    )
