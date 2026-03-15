"""Balance and portfolio state tracking for manual trade simulations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from trading_ai_system.simulation.trade_simulator import TradeSimulationResult


@dataclass
class PositionState:
    """Open position placeholder for future portfolio expansion."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    mark_price: float
    used_margin: float

    @property
    def unrealized_pnl(self) -> float:
        if self.side == "short":
            return (self.entry_price - self.mark_price) * self.quantity
        return (self.mark_price - self.entry_price) * self.quantity


@dataclass
class PortfolioState:
    """Long-lived portfolio state stored in session state."""

    initial_balance: float
    currency: str
    cash_balance: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    used_margin: float = 0.0
    positions: dict[str, PositionState] = field(default_factory=dict)
    closed_trades: list[dict[str, object]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["positions"] = {
            symbol: asdict(position) for symbol, position in self.positions.items()
        }
        return payload


@dataclass
class BalanceSnapshot:
    """What the dashboard shows after each simulation."""

    currency: str
    initial_balance: float
    cash_balance: float
    available_balance: float
    used_margin: float
    realized_pnl: float
    unrealized_pnl: float
    total_equity: float
    trade_count: int
    win_rate: float


class BalanceManager:
    """Applies simulation results to portfolio state."""

    def __init__(self, initial_balance: float, currency: str) -> None:
        self.state = PortfolioState(
            initial_balance=float(initial_balance),
            currency=currency,
            cash_balance=float(initial_balance),
        )

    @classmethod
    def from_state(cls, state: Optional[PortfolioState], *, initial_balance: float, currency: str) -> "BalanceManager":
        if state is None:
            return cls(initial_balance=initial_balance, currency=currency)
        manager = cls(initial_balance=state.initial_balance, currency=state.currency)
        manager.state = state
        return manager

    def reset(self, *, initial_balance: float, currency: str) -> None:
        self.state = PortfolioState(
            initial_balance=float(initial_balance),
            currency=currency,
            cash_balance=float(initial_balance),
        )

    def apply_closed_trade(self, result: TradeSimulationResult) -> BalanceSnapshot:
        self.state.cash_balance += result.net_pnl
        self.state.realized_pnl += result.net_pnl
        self.state.closed_trades.append(result.as_dict())
        self.state.used_margin = self._recompute_used_margin()
        self.state.unrealized_pnl = self._recompute_unrealized_pnl()
        return self.snapshot()

    def upsert_position(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        mark_price: float,
        used_margin: float,
    ) -> None:
        self.state.positions[symbol] = PositionState(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            mark_price=mark_price,
            used_margin=used_margin,
        )
        self.state.used_margin = self._recompute_used_margin()
        self.state.unrealized_pnl = self._recompute_unrealized_pnl()

    def remove_position(self, symbol: str) -> None:
        self.state.positions.pop(symbol, None)
        self.state.used_margin = self._recompute_used_margin()
        self.state.unrealized_pnl = self._recompute_unrealized_pnl()

    def snapshot(self) -> BalanceSnapshot:
        available = self.state.cash_balance - self.state.used_margin
        total_equity = self.state.cash_balance + self.state.unrealized_pnl
        trade_count = len(self.state.closed_trades)
        wins = sum(1 for trade in self.state.closed_trades if float(trade.get("net_pnl", 0.0)) > 0)
        win_rate = (wins / trade_count) if trade_count else 0.0
        return BalanceSnapshot(
            currency=self.state.currency,
            initial_balance=self.state.initial_balance,
            cash_balance=self.state.cash_balance,
            available_balance=available,
            used_margin=self.state.used_margin,
            realized_pnl=self.state.realized_pnl,
            unrealized_pnl=self.state.unrealized_pnl,
            total_equity=total_equity,
            trade_count=trade_count,
            win_rate=win_rate,
        )

    def _recompute_used_margin(self) -> float:
        return sum(position.used_margin for position in self.state.positions.values())

    def _recompute_unrealized_pnl(self) -> float:
        return sum(position.unrealized_pnl for position in self.state.positions.values())
