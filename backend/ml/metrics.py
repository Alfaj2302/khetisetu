"""Error metrics for the demand forecast.

MAPE is deliberately absent. The panel is intermittent — many months are a
genuine zero — and MAPE divides by the actual, so a single zero month makes it
infinite and a near-zero month makes it enormous. WAPE (total absolute error
over total actual volume) is the standard replacement for intermittent demand:
it stays finite, and it weights a 50-packet miss on a 500-packet month less
than the same miss on a 5-packet month.

`bias` is reported alongside because a forecast can have good WAPE while
systematically under-shipping, and that asymmetry matters downstream: too low
strands farmers without inputs, too high just ties up working capital.
"""

from __future__ import annotations

import numpy as np


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Weighted absolute percentage error, as a fraction (0.086 == 8.6%)."""
    denominator = np.abs(actual).sum()
    if denominator == 0:
        return float("nan")
    return float(np.abs(actual - predicted).sum() / denominator)


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.abs(actual - predicted).mean())


def bias(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean signed error. Negative = forecasting low on average."""
    return float((predicted - actual).mean())


def coverage(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Share of actuals that landed inside the interval.

    The interval is built from the 10th and 90th quantiles, so a well-calibrated
    model scores ~0.80 here. Much higher means the range is uselessly wide;
    much lower means it is lying about its own certainty.
    """
    return float(((actual >= lower) & (actual <= upper)).mean())


def report(name: str, actual: np.ndarray, predicted: np.ndarray) -> str:
    return (
        f"{name:<24} WAPE {wape(actual, predicted):>7.1%}   "
        f"MAE {mae(actual, predicted):>8.1f}   bias {bias(actual, predicted):>+8.1f}"
    )
