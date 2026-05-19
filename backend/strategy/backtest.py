"""
Backtest engine — Numba-accelerated event loop with ATR trailing stop loss.

Handles position tracking, stop loss execution, slippage, and commission.
Outputs trade list and daily equity curve.
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numba import njit

logger = logging.getLogger("trading_bot")


@dataclass
class BacktestResult:
    """Container for backtest outputs."""
    trades: pd.DataFrame         # columns: entry_date, exit_date, entry_price, exit_price,
                                 #          pnl, pnl_pct, direction, bars_held
    equity_curve: pd.Series      # daily portfolio value indexed by date
    total_pnl: float
    n_trades: int


def compute_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Compute Average True Range (ATR) using the standard method."""
    n = len(high)
    tr = np.zeros(n)
    atr = np.full(n, np.nan)

    # True Range
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Simple moving average for initial ATR, then EMA
    if n >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


@njit(cache=True)
def _run_backtest_loop(
    dates_ordinal: np.ndarray,
    open_prices: np.ndarray,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    close_prices: np.ndarray,
    signals: np.ndarray,
    target_positions: np.ndarray,
    atr_values: np.ndarray,
    atr_multiplier: float,
    slippage_pct: float,
    commission: float,
    allow_short: bool,
) -> tuple[
    np.ndarray,  # trade entry indices
    np.ndarray,  # trade exit indices
    np.ndarray,  # trade entry prices
    np.ndarray,  # trade exit prices
    np.ndarray,  # trade pnl
    np.ndarray,  # trade direction (+1 or -1)
    np.ndarray,  # daily equity values
]:
    """
    Core backtest loop — Numba JIT compiled for performance.

    Processes signals bar-by-bar, managing entries, exits, and ATR stops.
    """
    n = len(open_prices)
    max_trades = n  # upper bound

    # Trade storage
    t_entry_idx = np.zeros(max_trades, dtype=np.int64)
    t_exit_idx = np.zeros(max_trades, dtype=np.int64)
    t_entry_price = np.zeros(max_trades, dtype=np.float64)
    t_exit_price = np.zeros(max_trades, dtype=np.float64)
    t_pnl = np.zeros(max_trades, dtype=np.float64)
    t_direction = np.zeros(max_trades, dtype=np.int64)
    trade_count = 0

    # Daily equity tracking
    equity = np.ones(n, dtype=np.float64) * 10000.0  # start with $10k
    cash = 10000.0
    position = 0        # 0 = flat, +1 = long, -1 = short
    entry_price = 0.0
    stop_level = 0.0
    entry_idx = 0

    for i in range(1, n):
        current_open = open_prices[i]
        current_low = low_prices[i]
        current_high = high_prices[i]
        current_close = close_prices[i]
        sig = signals[i]
        current_atr = atr_values[i]

        # ── Check stop loss first (intra-bar) ────────────────────────
        stop_hit = False
        if position == 1 and current_low <= stop_level:
            # Long stop hit
            exit_price = stop_level * (1.0 - slippage_pct)
            pnl = (exit_price - entry_price) * 1.0 - commission
            cash += entry_price + pnl
            t_entry_idx[trade_count] = entry_idx
            t_exit_idx[trade_count] = i
            t_entry_price[trade_count] = entry_price
            t_exit_price[trade_count] = exit_price
            t_pnl[trade_count] = pnl
            t_direction[trade_count] = 1
            trade_count += 1
            position = 0
            stop_hit = True

        elif position == -1 and current_high >= stop_level:
            # Short stop hit
            exit_price = stop_level * (1.0 + slippage_pct)
            pnl = (entry_price - exit_price) * 1.0 - commission
            cash += entry_price + pnl
            t_entry_idx[trade_count] = entry_idx
            t_exit_idx[trade_count] = i
            t_entry_price[trade_count] = entry_price
            t_exit_price[trade_count] = exit_price
            t_pnl[trade_count] = pnl
            t_direction[trade_count] = -1
            trade_count += 1
            position = 0
            stop_hit = True

        # ── Process signals ──────────────────────────────────────────
        if not stop_hit:
            # Exit on signal reversal
            if position == 1 and sig == -1:
                exit_price = current_open * (1.0 - slippage_pct)
                pnl = (exit_price - entry_price) * 1.0 - commission
                cash += entry_price + pnl
                t_entry_idx[trade_count] = entry_idx
                t_exit_idx[trade_count] = i
                t_entry_price[trade_count] = entry_price
                t_exit_price[trade_count] = exit_price
                t_pnl[trade_count] = pnl
                t_direction[trade_count] = 1
                trade_count += 1
                position = 0

            elif position == -1 and sig == 1:
                exit_price = current_open * (1.0 + slippage_pct)
                pnl = (entry_price - exit_price) * 1.0 - commission
                cash += entry_price + pnl
                t_entry_idx[trade_count] = entry_idx
                t_exit_idx[trade_count] = i
                t_entry_price[trade_count] = entry_price
                t_exit_price[trade_count] = exit_price
                t_pnl[trade_count] = pnl
                t_direction[trade_count] = -1
                trade_count += 1
                position = 0

        # ── Enter new position ───────────────────────────────────────
        if position == 0 and not np.isnan(current_atr) and current_atr > 0:
            if sig == 1:
                entry_price = current_open * (1.0 + slippage_pct)
                stop_level = entry_price - atr_multiplier * current_atr
                cash -= entry_price
                position = 1
                entry_idx = i

            elif sig == -1 and allow_short:
                entry_price = current_open * (1.0 - slippage_pct)
                stop_level = entry_price + atr_multiplier * current_atr
                cash -= entry_price
                position = -1
                entry_idx = i

        # ── Update daily equity ──────────────────────────────────────
        if position == 1:
            equity[i] = cash + current_close
        elif position == -1:
            equity[i] = cash + (2.0 * entry_price - current_close)
        else:
            equity[i] = cash

    # Close any open position at the last bar
    if position != 0:
        i = n - 1
        exit_price = close_prices[i]
        if position == 1:
            exit_price *= (1.0 - slippage_pct)
            pnl = (exit_price - entry_price) * 1.0 - commission
            t_direction[trade_count] = 1
        else:
            exit_price *= (1.0 + slippage_pct)
            pnl = (entry_price - exit_price) * 1.0 - commission
            t_direction[trade_count] = -1

        cash += entry_price + pnl
        t_entry_idx[trade_count] = entry_idx
        t_exit_idx[trade_count] = i
        t_entry_price[trade_count] = entry_price
        t_exit_price[trade_count] = exit_price
        t_pnl[trade_count] = pnl
        trade_count += 1
        equity[i] = cash

    return (
        t_entry_idx[:trade_count],
        t_exit_idx[:trade_count],
        t_entry_price[:trade_count],
        t_exit_price[:trade_count],
        t_pnl[:trade_count],
        t_direction[:trade_count],
        equity,
    )


def run_backtest(
    df: pd.DataFrame,
    fast_sma: int,
    slow_sma: int,
    atr_multiplier: float,
    allow_short: bool = False,
    slippage_pct: float = 0.001,
    commission: float = 1.0,
) -> BacktestResult:
    """
    Run a full backtest for a single parameter combination.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with DatetimeIndex.
    fast_sma, slow_sma : int
        SMA periods.
    atr_multiplier : float
        ATR multiplier for stop loss.
    allow_short : bool
        Whether to trade the short side.
    slippage_pct : float
        Slippage as a fraction (0.001 = 0.1%).
    commission : float
        Commission per round-trip trade in dollars.

    Returns
    -------
    BacktestResult
        Trades, equity curve, and summary stats.
    """
    from backend.strategy.signals import compute_sma_signals

    logger.debug(
        "run_backtest — fast=%d, slow=%d, atr_mult=%.1f, short=%s",
        fast_sma, slow_sma, atr_multiplier, allow_short,
    )

    # Generate signals
    sig_df = compute_sma_signals(df, fast_sma, slow_sma, allow_short)

    # Compute ATR
    atr = compute_atr(
        sig_df["High"].values.astype(np.float64),
        sig_df["Low"].values.astype(np.float64),
        sig_df["Close"].values.astype(np.float64),
        period=14,
    )

    # Prepare arrays for Numba
    dates = sig_df.index
    dates_ordinal = np.array([d.toordinal() for d in dates], dtype=np.int64)

    (
        entry_indices,
        exit_indices,
        entry_prices,
        exit_prices,
        pnls,
        directions,
        equity_values,
    ) = _run_backtest_loop(
        dates_ordinal=dates_ordinal,
        open_prices=sig_df["Open"].values.astype(np.float64),
        high_prices=sig_df["High"].values.astype(np.float64),
        low_prices=sig_df["Low"].values.astype(np.float64),
        close_prices=sig_df["Close"].values.astype(np.float64),
        signals=sig_df["signal"].values.astype(np.int64),
        target_positions=sig_df["target_position"].values.astype(np.int64),
        atr_values=atr,
        atr_multiplier=atr_multiplier,
        slippage_pct=slippage_pct,
        commission=commission,
        allow_short=allow_short,
    )

    # Build trades DataFrame
    trades = pd.DataFrame({
        "entry_date": dates[entry_indices],
        "exit_date": dates[exit_indices],
        "entry_price": entry_prices,
        "exit_price": exit_prices,
        "pnl": pnls,
        "pnl_pct": pnls / entry_prices * 100,
        "direction": directions,
        "bars_held": exit_indices - entry_indices,
    })

    equity_curve = pd.Series(equity_values, index=dates, name="equity")

    total_pnl = float(pnls.sum()) if len(pnls) > 0 else 0.0

    logger.debug(
        "Backtest done — %d trades, total_pnl=%.2f",
        len(trades), total_pnl,
    )

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        total_pnl=total_pnl,
        n_trades=len(trades),
    )
