"""
Signal generation — SMA crossover with configurable fast/slow periods.

Generates +1 (long entry) and -1 (exit/short entry) signals from SMA crosses.
Signals are lagged by 1 bar to prevent lookahead bias (execute at next open).
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("trading_bot")


def compute_sma_signals(
    df: pd.DataFrame,
    fast_period: int,
    slow_period: int,
    allow_short: bool = False,
) -> pd.DataFrame:
    """
    Generate SMA crossover signals.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with 'Close' column.
    fast_period : int
        Fast SMA period.
    slow_period : int
        Slow SMA period.
    allow_short : bool
        If True, death cross generates a short entry signal (-1).
        If False, death cross only generates an exit signal (0).

    Returns
    -------
    pd.DataFrame
        Copy of input with added columns:
        - sma_fast, sma_slow: SMA values
        - raw_signal: +1 (long), -1 (short/exit), 0 (no change)
        - signal: lagged raw_signal (for next-bar execution)
    """
    logger.debug(
        "compute_sma_signals — fast=%d, slow=%d, allow_short=%s",
        fast_period, slow_period, allow_short,
    )

    if fast_period >= slow_period:
        raise ValueError(
            f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
        )

    result = df.copy()
    close = result["Close"].astype(float)

    # Compute SMAs
    result["sma_fast"] = close.rolling(window=fast_period).mean()
    result["sma_slow"] = close.rolling(window=slow_period).mean()

    # Position indicator: fast > slow = 1 (bullish), fast < slow = -1 or 0
    fast_above = (result["sma_fast"] > result["sma_slow"]).astype(int)

    if allow_short:
        # +1 when fast > slow, -1 when fast < slow
        position = np.where(fast_above == 1, 1, -1)
    else:
        # +1 when fast > slow, 0 otherwise (long only)
        position = fast_above.values

    # Detect changes (crossovers)
    position_series = pd.Series(position, index=result.index)
    position_change = position_series.diff()

    # raw_signal: only fires on crossover events
    # +1 = golden cross (enter long)
    # -1 = death cross (exit long / enter short)
    result["raw_signal"] = np.where(
        position_change > 0, 1,
        np.where(position_change < 0, -1, 0),
    )

    # Lag signal by 1 bar: trade at NEXT bar's open, not current bar's close
    result["signal"] = result["raw_signal"].shift(1).fillna(0).astype(int)

    # Also carry forward the intended position (useful for backtest)
    result["target_position"] = position_series.shift(1).fillna(0).astype(int)

    # Drop warmup NaN rows
    result = result.dropna(subset=["sma_fast", "sma_slow"])

    logger.debug(
        "Signals generated — %d bars, %d entry signals, %d exit signals",
        len(result),
        (result["signal"] == 1).sum(),
        (result["signal"] == -1).sum(),
    )

    return result
