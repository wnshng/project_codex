"""Manual trade simulation engine for long/short scenario review."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TradeInput:
    """User-defined trade parameters used for manual simulation."""

    symbol: str
    side: str
    entry_time: datetime
    entry_price: float
    quantity: Optional[float] = None
    investment_amount: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    fee_rate: float = 0.0005
    leverage: float = 1.0

    def normalized_quantity(self) -> float:
        """Derives quantity from either quantity or investment amount."""
        if self.quantity is not None and self.quantity > 0:
            return float(self.quantity)
        if self.investment_amount is None or self.investment_amount <= 0:
            raise ValueError("수량 또는 투자금액 중 하나는 반드시 입력해야 합니다.")
        return float(self.investment_amount * max(self.leverage, 1.0) / self.entry_price)


@dataclass
class TradeSimulationResult:
    """Output of one simulated trade."""

    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fee_paid: float
    net_pnl: float
    return_pct: float
    mfe_pct: float
    mae_pct: float
    used_margin: float
    balance_delta: float
    exit_reason: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AggregateSimulation:
    """Summary across multiple manual trades."""

    trade_count: int
    win_rate: float
    cumulative_net_pnl: float
    cumulative_return_pct: float


def simulate_trade(trade_input: TradeInput, history_frame=None) -> TradeSimulationResult:
    """Runs one trade simulation with stop/take-profit and fee handling."""
    quantity = trade_input.normalized_quantity()
    used_margin = (trade_input.entry_price * quantity) / max(trade_input.leverage, 1.0)
    exit_time = trade_input.exit_time or trade_input.entry_time
    exit_price = trade_input.exit_price or trade_input.entry_price
    exit_reason = "사용자 지정 청산"
    path_frame = history_frame

    if history_frame is not None and trade_input.exit_time is not None:
        path_frame = _slice_history(history_frame, trade_input.entry_time, trade_input.exit_time)
        resolved_exit = _resolve_exit_from_history(trade_input, path_frame)
        if resolved_exit is not None:
            exit_time, exit_price, exit_reason = resolved_exit
        elif trade_input.exit_price is not None:
            exit_time = trade_input.exit_time
            exit_price = trade_input.exit_price
            exit_reason = "사용자 지정 청산"
        elif not path_frame.empty:
            exit_time = path_frame.iloc[-1]["timestamp"]
            exit_price = float(path_frame.iloc[-1]["close"])
            exit_reason = "종가 기준 청산"

    gross_pnl = _gross_pnl(
        side=trade_input.side,
        entry_price=trade_input.entry_price,
        exit_price=exit_price,
        quantity=quantity,
    )
    fee_paid = (
        trade_input.entry_price * quantity * trade_input.fee_rate
        + exit_price * quantity * trade_input.fee_rate
    )
    net_pnl = gross_pnl - fee_paid
    return_pct = (net_pnl / used_margin) if used_margin else 0.0
    mfe_pct, mae_pct = _mfe_mae_pct(trade_input, path_frame)

    return TradeSimulationResult(
        symbol=trade_input.symbol,
        side=trade_input.side,
        entry_time=trade_input.entry_time,
        exit_time=exit_time,
        entry_price=trade_input.entry_price,
        exit_price=exit_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        fee_paid=fee_paid,
        net_pnl=net_pnl,
        return_pct=return_pct,
        mfe_pct=mfe_pct,
        mae_pct=mae_pct,
        used_margin=used_margin,
        balance_delta=net_pnl,
        exit_reason=exit_reason,
    )


def summarize_trade_results(results: list[TradeSimulationResult]) -> AggregateSimulation:
    """Builds a cumulative performance snapshot for the dashboard."""
    trade_count = len(results)
    if trade_count == 0:
        return AggregateSimulation(
            trade_count=0,
            win_rate=0.0,
            cumulative_net_pnl=0.0,
            cumulative_return_pct=0.0,
        )
    cumulative_net_pnl = sum(result.net_pnl for result in results)
    win_rate = sum(1 for result in results if result.net_pnl > 0) / trade_count
    cumulative_return_pct = sum(result.return_pct for result in results)
    return AggregateSimulation(
        trade_count=trade_count,
        win_rate=win_rate,
        cumulative_net_pnl=cumulative_net_pnl,
        cumulative_return_pct=cumulative_return_pct,
    )


def _slice_history(history_frame, start_time: datetime, end_time: datetime):
    return history_frame[
        (history_frame["timestamp"] >= start_time)
        & (history_frame["timestamp"] <= end_time)
    ].copy()


def _resolve_exit_from_history(trade_input: TradeInput, history_frame) -> Optional[tuple[datetime, float, str]]:
    if history_frame is None or history_frame.empty:
        return None
    for _, row in history_frame.iterrows():
        timestamp = row["timestamp"]
        high = float(row["high"])
        low = float(row["low"])
        if trade_input.side == "long":
            if trade_input.stop_loss is not None and low <= trade_input.stop_loss:
                return timestamp, float(trade_input.stop_loss), "손절 도달"
            if trade_input.take_profit is not None and high >= trade_input.take_profit:
                return timestamp, float(trade_input.take_profit), "익절 도달"
        else:
            if trade_input.stop_loss is not None and high >= trade_input.stop_loss:
                return timestamp, float(trade_input.stop_loss), "손절 도달"
            if trade_input.take_profit is not None and low <= trade_input.take_profit:
                return timestamp, float(trade_input.take_profit), "익절 도달"
    return None


def _gross_pnl(*, side: str, entry_price: float, exit_price: float, quantity: float) -> float:
    if side == "short":
        return (entry_price - exit_price) * quantity
    return (exit_price - entry_price) * quantity


def _mfe_mae_pct(trade_input: TradeInput, history_frame) -> tuple[float, float]:
    if history_frame is None or history_frame.empty:
        return 0.0, 0.0
    entry = trade_input.entry_price
    if trade_input.side == "short":
        favorable = max((entry - float(value)) / entry for value in history_frame["low"])
        adverse = min((entry - float(value)) / entry for value in history_frame["high"])
        return favorable, adverse
    favorable = max((float(value) - entry) / entry for value in history_frame["high"])
    adverse = min((float(value) - entry) / entry for value in history_frame["low"])
    return favorable, adverse
