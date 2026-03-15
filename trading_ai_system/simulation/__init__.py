"""Trade simulation package."""

from trading_ai_system.simulation.trade_simulator import (
    AggregateSimulation,
    TradeInput,
    TradeSimulationResult,
    simulate_trade,
    summarize_trade_results,
)

__all__ = [
    "AggregateSimulation",
    "TradeInput",
    "TradeSimulationResult",
    "simulate_trade",
    "summarize_trade_results",
]
