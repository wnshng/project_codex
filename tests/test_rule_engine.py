from trading_ai_system.data.schemas.market import MarketContext, TimeframeState
from trading_ai_system.signals.mtf_scoring import compute_mtf_summary
from trading_ai_system.strategy.trade_constraints import evaluate_trade_constraints


def _base_context(**strategy_overrides: object) -> MarketContext:
    strategy_state = {
        "pattern_confirmed": True,
        "confirmation_entry": True,
        "stop_is_clear": True,
        "stop_distance_ratio": 0.01,
        "reward_risk_ratio": 2.0,
        "split_entry_recommended": True,
        "lower_tf_exit_priority": True,
        "chasing_risk": False,
        "sr_touch_count": 2,
        "event_volatility_risk": "normal",
    }
    strategy_state.update(strategy_overrides)
    return MarketContext(
        symbol="BTCUSDT",
        asset_type="crypto",
        exchange="Binance",
        mode="historical",
        timeframes={
            "1d": TimeframeState("1d", trend_score=2, momentum_score=1, pattern_score=1),
            "4h": TimeframeState("4h", trend_score=2, momentum_score=1),
            "1h": TimeframeState("1h", trend_score=1.5, momentum_score=1),
        },
        strategy_state=strategy_state,
    )


def test_rule_engine_allows_trade_for_clean_setup() -> None:
    context = _base_context()

    outcome = evaluate_trade_constraints(context, compute_mtf_summary(context))

    assert outcome.entry_allowed is True
    assert outcome.no_trade is False
    assert outcome.hard_reject is False


def test_rule_engine_hard_rejects_for_chasing_and_fourth_touch() -> None:
    context = _base_context(
        chasing_risk=True,
        sr_touch_count=4,
        fourth_touch_break_risk=True,
    )

    outcome = evaluate_trade_constraints(context, compute_mtf_summary(context))

    assert outcome.hard_reject is True
    assert outcome.no_trade is True
    assert any("추격" in reason or "4번째" in reason for reason in outcome.no_trade_reasons)
