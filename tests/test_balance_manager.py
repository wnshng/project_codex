from datetime import datetime

from trading_ai_system.portfolio.balance_manager import BalanceManager
from trading_ai_system.simulation.trade_simulator import TradeSimulationResult


def test_balance_manager_updates_realized_pnl_and_cash() -> None:
    manager = BalanceManager(initial_balance=1000000.0, currency="KRW")
    result = TradeSimulationResult(
        symbol="BTCUSDT",
        side="long",
        entry_time=datetime(2026, 3, 15, 9, 0),
        exit_time=datetime(2026, 3, 15, 10, 0),
        entry_price=100.0,
        exit_price=110.0,
        quantity=10.0,
        gross_pnl=100.0,
        fee_paid=2.0,
        net_pnl=98.0,
        return_pct=0.098,
        mfe_pct=0.10,
        mae_pct=-0.01,
        used_margin=1000.0,
        balance_delta=98.0,
        exit_reason="사용자 지정 청산",
    )

    snapshot = manager.apply_closed_trade(result)

    assert snapshot.cash_balance == 1000098.0
    assert snapshot.realized_pnl == 98.0
    assert snapshot.trade_count == 1
