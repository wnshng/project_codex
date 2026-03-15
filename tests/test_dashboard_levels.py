from trading_ai_system.dashboard.streamlit_app import _build_context, build_trade_levels
from trading_ai_system.models.predictor import run_pipeline


def test_trade_levels_for_bullish_context_are_ordered() -> None:
    context = _build_context(
        symbol="BTCUSDT",
        asset_type="crypto",
        exchange="Binance",
        mode="historical",
        higher_tf_bias=0.45,
        lower_tf_bias=0.30,
        breakout_confirmed=True,
        retest_success=True,
        stop_clear=True,
        chasing_risk=False,
        fourth_touch_risk=False,
        overlap_zone=False,
        countertrend=False,
        event_risk="normal",
        reward_risk_ratio=2.0,
        xgb_up=0.58,
        lstm_up=0.54,
        rf_up=0.52,
    )
    prediction = run_pipeline(context)
    levels = build_trade_levels(context, prediction)

    assert levels.supports[0].value < context.current_price
    assert levels.entries[0].value < context.current_price
    assert levels.take_profits[0].value > context.current_price
    assert levels.stop_loss.value < levels.entries[1].value


def test_trade_levels_for_bearish_context_flip_direction() -> None:
    context = _build_context(
        symbol="BTCUSDT",
        asset_type="crypto",
        exchange="Binance",
        mode="historical",
        higher_tf_bias=-0.45,
        lower_tf_bias=-0.35,
        breakout_confirmed=True,
        retest_success=True,
        stop_clear=True,
        chasing_risk=False,
        fourth_touch_risk=False,
        overlap_zone=False,
        countertrend=False,
        event_risk="normal",
        reward_risk_ratio=2.0,
        xgb_up=0.22,
        lstm_up=0.25,
        rf_up=0.28,
    )
    prediction = run_pipeline(context)
    levels = build_trade_levels(context, prediction)

    assert levels.entries[0].value > context.current_price
    assert levels.take_profits[0].value < context.current_price
    assert levels.stop_loss.value > levels.entries[1].value
