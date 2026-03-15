"""Lightweight backtest helpers for rule-on/off comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BacktestRow:
    up_probability: float
    down_probability: float
    realized_return: float
    no_trade: bool = False


@dataclass
class BacktestSummary:
    trade_count: int
    no_trade_ratio: float
    win_rate: float
    average_return: float
    gross_profit: float
    gross_loss: float
    profit_factor: float


def run_probability_backtest(
    rows: list[BacktestRow],
    *,
    threshold: float = 0.65,
    use_rules: bool = True,
) -> BacktestSummary:
    realized: list[float] = []
    skipped = 0

    for row in rows:
        if use_rules and row.no_trade:
            skipped += 1
            continue
        if row.up_probability >= threshold:
            realized.append(row.realized_return)
        elif row.down_probability >= threshold:
            realized.append(-row.realized_return)
        else:
            skipped += 1

    trade_count = len(realized)
    wins = [value for value in realized if value > 0]
    losses = [value for value in realized if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else float("inf") if gross_profit else 0.0

    return BacktestSummary(
        trade_count=trade_count,
        no_trade_ratio=(skipped / len(rows)) if rows else 0.0,
        win_rate=(len(wins) / trade_count) if trade_count else 0.0,
        average_return=(sum(realized) / trade_count) if trade_count else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
    )
