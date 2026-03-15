"""Target label helpers for up/down/sideways classification."""

from __future__ import annotations


def classify_future_return(
    future_return: float,
    *,
    up_threshold: float,
    down_threshold: float | None = None,
) -> str:
    down_threshold = down_threshold if down_threshold is not None else up_threshold
    if future_return >= up_threshold:
        return "up"
    if future_return <= -down_threshold:
        return "down"
    return "side"
