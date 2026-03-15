from trading_ai_system.data.schemas.market import MarketContext, TimeframeState
from trading_ai_system.signals.mtf_scoring import compute_mtf_summary


def test_bullish_alignment_increases_composite_score() -> None:
    context = MarketContext(
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
    )

    summary = compute_mtf_summary(context)

    assert summary.composite_score > 0
    assert summary.alignment_bonus > 0
    assert summary.regime_class in {"transition", "trend"}


def test_overlap_zone_adds_warning_and_penalty() -> None:
    context = MarketContext(
        symbol="BTCUSDT",
        asset_type="crypto",
        exchange="Binance",
        mode="historical",
        timeframes={"1d": TimeframeState("1d", trend_score=2, momentum_score=1)},
        strategy_state={"overlapping_target_zone": True},
    )

    summary = compute_mtf_summary(context)

    assert summary.caution_penalty > 0
    assert any("target zone" in warning.lower() for warning in summary.warnings)
