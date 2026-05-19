"""
Performance metrics — Sharpe, Max Drawdown, Profit Factor, Win Rate, etc.

All metrics can be computed globally or filtered by regime.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("trading_bot")


def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Annualized Sharpe ratio from a daily equity curve.

    Sharpe = sqrt(252) * (mean_daily_return - rf) / std_daily_return
    """
    daily_returns = equity_curve.pct_change().dropna()

    if len(daily_returns) < 2 or daily_returns.std() == 0:
        return 0.0

    excess_return = daily_returns.mean() - risk_free_rate / 252
    return float(np.sqrt(252) * excess_return / daily_returns.std())


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum drawdown as a negative percentage.

    Returns the worst peak-to-trough decline.
    """
    if len(equity_curve) < 2:
        return 0.0

    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    return float(drawdown.min())


def profit_factor(trades: pd.DataFrame) -> float:
    """
    Profit Factor = Gross Profit / |Gross Loss|.

    Returns inf if no losing trades, 0.0 if no winning trades.
    """
    if trades.empty:
        return 0.0

    gross_profit = trades.loc[trades["pnl"] > 0, "pnl"].sum()
    gross_loss = abs(trades.loc[trades["pnl"] < 0, "pnl"].sum())

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return float(gross_profit / gross_loss)


def win_rate(trades: pd.DataFrame) -> float:
    """Fraction of profitable trades."""
    if trades.empty:
        return 0.0
    return float((trades["pnl"] > 0).sum() / len(trades))


def net_profit(trades: pd.DataFrame) -> float:
    """Total net P&L across all trades."""
    if trades.empty:
        return 0.0
    return float(trades["pnl"].sum())


def compute_all_metrics(
    trades: pd.DataFrame,
    equity_curve: pd.Series,
) -> dict:
    """
    Compute all performance metrics for a set of trades.

    Parameters
    ----------
    trades : pd.DataFrame
        Trade log with at least 'pnl' column.
    equity_curve : pd.Series
        Daily equity curve.

    Returns
    -------
    dict
        Dictionary with all metrics.
    """
    metrics = {
        "sharpe_ratio": round(sharpe_ratio(equity_curve), 4),
        "net_profit": round(net_profit(trades), 2),
        "max_drawdown": round(max_drawdown(equity_curve) * 100, 2),  # as percentage
        "profit_factor": round(profit_factor(trades), 4),
        "win_rate": round(win_rate(trades) * 100, 2),  # as percentage
        "n_trades": len(trades),
        "avg_pnl": round(float(trades["pnl"].mean()), 2) if len(trades) > 0 else 0.0,
        "avg_bars_held": round(float(trades["bars_held"].mean()), 1) if len(trades) > 0 else 0.0,
    }

    logger.debug("Metrics: %s", metrics)
    return metrics


def compute_metrics_by_regime(
    trades: pd.DataFrame,
    equity_curve: pd.Series,
    regime_labels: np.ndarray,
    regime_dates: pd.DatetimeIndex,
    n_states: int,
) -> dict[int, dict]:
    """
    Compute metrics for trades grouped by their ENTRY regime.

    Parameters
    ----------
    trades : pd.DataFrame
        Trade log with 'entry_date' and 'pnl' columns.
    equity_curve : pd.Series
        Full daily equity curve.
    regime_labels : np.ndarray
        Regime label for each date in regime_dates.
    regime_dates : pd.DatetimeIndex
        Dates aligned with regime_labels.
    n_states : int
        Number of regime states.

    Returns
    -------
    dict[int, dict]
        {regime_id: {metric_name: value}}.
    """
    # Build a date -> regime mapping
    regime_map = pd.Series(regime_labels, index=regime_dates)

    # Classify each trade by regime at entry date
    if trades.empty:
        return {s: compute_all_metrics(pd.DataFrame(), pd.Series(dtype=float)) for s in range(n_states)}

    # Find closest regime date for each trade entry
    trade_regimes = []
    for entry_date in trades["entry_date"]:
        # Find the regime on or before the entry date
        valid_dates = regime_map.index[regime_map.index <= entry_date]
        if len(valid_dates) > 0:
            closest_date = valid_dates[-1]
            trade_regimes.append(int(regime_map.loc[closest_date]))
        else:
            trade_regimes.append(0)  # default to lowest regime

    trades_with_regime = trades.copy()
    trades_with_regime["regime"] = trade_regimes

    results: dict[int, dict] = {}
    for state in range(n_states):
        state_trades = trades_with_regime[trades_with_regime["regime"] == state]
        # Build a rough equity curve for this regime's trades
        state_equity = _build_regime_equity(state_trades, equity_curve)
        results[state] = compute_all_metrics(state_trades, state_equity)
        results[state]["regime_id"] = state

    return results


def _build_regime_equity(
    regime_trades: pd.DataFrame,
    full_equity: pd.Series,
) -> pd.Series:
    """
    Build an approximate equity curve for trades in a specific regime.

    This sums the P&L of only the regime's trades to create a regime-specific
    equity trajectory.
    """
    if regime_trades.empty:
        return pd.Series([10000.0], name="equity")

    # Start with initial capital and add trade P&Ls sequentially
    equity_values = [10000.0]
    running = 10000.0
    for _, trade in regime_trades.iterrows():
        running += trade["pnl"]
        equity_values.append(running)

    return pd.Series(equity_values, name="equity")
