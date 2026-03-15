from trading_ai_system.data.schemas.market import MarketContext, ModelProbabilities, TimeframeState
from trading_ai_system.models.predictor import run_pipeline


def _context(no_trade: bool = False) -> MarketContext:
    strategy_state = {
        "pattern_confirmed": True,
        "confirmation_entry": True,
        "stop_is_clear": True,
        "stop_distance_ratio": 0.01,
        "reward_risk_ratio": 2.2,
        "breakout_confirmed_flag": True,
        "retest_success_flag": True,
        "split_entry_recommended": True,
        "lower_tf_exit_priority": True,
        "event_volatility_risk": "normal",
        "chasing_risk": False,
        "sr_touch_count": 2,
    }
    if no_trade:
        strategy_state.update(
            {
                "chasing_risk": True,
                "stop_is_clear": False,
                "event_volatility_risk": "extreme",
            }
        )
    return MarketContext(
        symbol="BTCUSDT",
        asset_type="crypto",
        exchange="Binance",
        mode="historical",
        timeframes={
            "1w": TimeframeState("1w", trend_score=2, momentum_score=1, pattern_score=1),
            "1d": TimeframeState("1d", trend_score=2, momentum_score=1, pattern_score=1),
            "4h": TimeframeState("4h", trend_score=2, momentum_score=1),
            "1h": TimeframeState("1h", trend_score=1.5, momentum_score=1),
        },
        strategy_state=strategy_state,
        model_outputs={
            "xgboost": ModelProbabilities("xgboost", up=0.62, down=0.20, side=0.18),
            "lstm": ModelProbabilities("lstm", up=0.57, down=0.22, side=0.21),
            "random_forest": ModelProbabilities("random_forest", up=0.54, down=0.25, side=0.21),
        },
    )


def test_pipeline_returns_long_action_for_clean_bullish_setup() -> None:
    prediction = run_pipeline(_context())

    assert prediction.predicted_class == "up"
    assert prediction.final_action in {"WEAK_LONG", "STRONG_LONG"}
    assert prediction.entry_plan.decision in {"allow_full", "allow_probe"}


def test_pipeline_returns_no_trade_when_hard_filters_fail() -> None:
    prediction = run_pipeline(_context(no_trade=True))

    assert prediction.final_action == "NO_TRADE"
    assert prediction.rule_outcome.no_trade is True
