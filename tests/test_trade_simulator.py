from datetime import datetime

from trading_ai_system.simulation.trade_simulator import TradeInput, simulate_trade


def test_trade_simulator_computes_long_profit_with_fees() -> None:
    trade_input = TradeInput(
        symbol="BTCUSDT",
        side="long",
        entry_time=datetime(2026, 3, 15, 9, 0),
        entry_price=100.0,
        exit_time=datetime(2026, 3, 15, 10, 0),
        exit_price=110.0,
        investment_amount=1000.0,
        fee_rate=0.001,
        leverage=1.0,
    )

    result = simulate_trade(trade_input)

    assert result.quantity == 10.0
    assert result.gross_pnl == 100.0
    assert result.fee_paid == 2.1
    assert round(result.net_pnl, 2) == 97.90


def test_trade_simulator_computes_short_profit() -> None:
    trade_input = TradeInput(
        symbol="TSLA",
        side="short",
        entry_time=datetime(2026, 3, 15, 9, 0),
        entry_price=200.0,
        exit_time=datetime(2026, 3, 15, 10, 0),
        exit_price=180.0,
        quantity=2.0,
        fee_rate=0.0,
        leverage=1.0,
    )

    result = simulate_trade(trade_input)

    assert result.gross_pnl == 40.0
    assert result.net_pnl == 40.0
