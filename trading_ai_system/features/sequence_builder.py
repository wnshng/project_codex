"""Helpers for building LSTM-friendly fixed windows."""

from __future__ import annotations


def select_sequence_feature_names() -> list[str]:
    return [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "return_1_bar",
        "return_3_bar",
        "return_5_bar",
        "rsi14",
        "macd_histogram",
        "atr14",
        "bb_width",
        "vwap_distance",
        "ema_20_50_spread",
        "volume_to_ma20",
        "consensus_score",
    ]


def build_sequences(
    rows: list[dict[str, float | int | bool | str | None]],
    feature_names: list[str] | None = None,
    lookback: int = 60,
) -> list[list[list[float]]]:
    feature_names = feature_names or select_sequence_feature_names()
    sequences: list[list[list[float]]] = []
    if lookback <= 0:
        return sequences
    for end_index in range(lookback, len(rows) + 1):
        window = rows[end_index - lookback : end_index]
        sequences.append(
            [
                [float(record.get(feature_name, 0.0) or 0.0) for feature_name in feature_names]
                for record in window
            ]
        )
    return sequences
