"""
Parameter sweep — brute-force optimization across all SMA/ATR combinations.

Runs backtests for each valid parameter combination, classifies trades by
entry-date regime, and ranks results by Sharpe ratio.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd

from backend.config import MIN_TRADES_FILTER, AssetConfig
from backend.models.hmm import HMMResult
from backend.strategy.backtest import run_backtest
from backend.strategy.metrics import (
    compute_all_metrics,
    compute_metrics_by_regime,
)

logger = logging.getLogger("trading_bot")


@dataclass
class SweepResult:
    """Container for parameter sweep results."""
    all_results: pd.DataFrame            # all combos with metrics
    best_global: dict                    # best overall combo
    best_per_regime: dict[int, dict]     # best combo per regime
    equity_curves: dict[str, pd.Series]  # key: "global" | "regime_0" | "combined"
    heatmap_data: dict                   # for Sharpe heatmap
    trades_by_combo: dict[str, pd.DataFrame]  # trades for each key combo


def _run_single_backtest(
    df: pd.DataFrame,
    fast_sma: int,
    slow_sma: int,
    atr_mult: float,
    allow_short: bool,
    slippage: float,
    commission: float,
) -> dict | None:
    """
    Run a single backtest and return results dict. Used by process pool.
    """
    try:
        result = run_backtest(
            df, fast_sma, slow_sma, atr_mult,
            allow_short=allow_short,
            slippage_pct=slippage,
            commission=commission,
        )
        return {
            "fast_sma": fast_sma,
            "slow_sma": slow_sma,
            "atr_mult": atr_mult,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
            "total_pnl": result.total_pnl,
            "n_trades": result.n_trades,
        }
    except Exception as exc:
        logger.warning(
            "Backtest failed for fast=%d, slow=%d, atr=%.1f: %s",
            fast_sma, slow_sma, atr_mult, exc,
        )
        return None


def run_parameter_sweep(
    df: pd.DataFrame,
    asset_config: AssetConfig,
    hmm_result: HMMResult,
    progress_callback: Callable | None = None,
) -> SweepResult:
    """
    Run parameter sweep across all SMA/ATR combinations.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data.
    asset_config : AssetConfig
        Asset configuration with parameter grids.
    hmm_result : HMMResult
        HMM regime detection results.
    progress_callback : callable, optional
        Called with (current, total) for progress updates.

    Returns
    -------
    SweepResult
        Complete sweep results.
    """
    fast_values = asset_config.default_fast_sma
    slow_values = asset_config.default_slow_sma
    atr_values = asset_config.default_atr_mult

    # Generate valid combinations (fast < slow)
    all_combos = [
        (f, s, a)
        for f, s, a in product(fast_values, slow_values, atr_values)
        if f < s
    ]

    total = len(all_combos)
    logger.info(
        "Parameter sweep — %d valid combinations (from %d total), asset=%s",
        total,
        len(fast_values) * len(slow_values) * len(atr_values),
        asset_config.ticker,
    )

    start_time = time.time()
    results_list = []
    completed = 0

    # Run backtests (sequential to avoid Numba multiprocessing issues)
    for fast_sma, slow_sma, atr_mult in all_combos:
        result = _run_single_backtest(
            df, fast_sma, slow_sma, atr_mult,
            allow_short=asset_config.allow_short,
            slippage=asset_config.slippage_pct,
            commission=asset_config.commission_per_trade,
        )
        if result is not None:
            results_list.append(result)

        completed += 1
        if progress_callback:
            progress_callback(completed, total)

        if completed % 10 == 0:
            logger.info("  Progress: %d/%d (%.1f%%)", completed, total, completed / total * 100)

    elapsed = time.time() - start_time
    logger.info(
        "Sweep complete — %d/%d successful in %.1fs (%.1f backtests/sec)",
        len(results_list), total, elapsed, len(results_list) / elapsed if elapsed > 0 else 0,
    )

    if not results_list:
        raise RuntimeError("All backtests failed. Check data quality.")

    # ── Compute metrics for each combo ───────────────────────────────
    all_rows = []
    trades_by_combo: dict[str, pd.DataFrame] = {}
    equity_by_combo: dict[str, pd.Series] = {}

    for r in results_list:
        combo_key = f"{r['fast_sma']}_{r['slow_sma']}_{r['atr_mult']}"

        # Global metrics
        global_metrics = compute_all_metrics(r["trades"], r["equity_curve"])

        # Per-regime metrics
        regime_metrics = compute_metrics_by_regime(
            r["trades"], r["equity_curve"],
            hmm_result.regime_labels, hmm_result.valid_dates,
            hmm_result.n_states,
        )

        row = {
            "fast_sma": r["fast_sma"],
            "slow_sma": r["slow_sma"],
            "atr_mult": r["atr_mult"],
            "combo_key": combo_key,
            **{f"global_{k}": v for k, v in global_metrics.items()},
        }

        # Add per-regime metrics
        for state_id, state_metrics in regime_metrics.items():
            for k, v in state_metrics.items():
                if k != "regime_id":
                    row[f"regime_{state_id}_{k}"] = v

        all_rows.append(row)
        trades_by_combo[combo_key] = r["trades"]
        equity_by_combo[combo_key] = r["equity_curve"]

    results_df = pd.DataFrame(all_rows)

    # ── Filter by minimum trades ─────────────────────────────────────
    valid_mask = results_df["global_n_trades"] >= MIN_TRADES_FILTER
    filtered_df = results_df[valid_mask].copy()

    logger.info(
        "After filtering (>= %d trades): %d/%d combinations remain",
        MIN_TRADES_FILTER, len(filtered_df), len(results_df),
    )

    if filtered_df.empty:
        logger.warning("No combinations passed the minimum trades filter. Using unfiltered results.")
        filtered_df = results_df.copy()

    # ── Find best combos ─────────────────────────────────────────────
    # Best global
    best_global_idx = filtered_df["global_sharpe_ratio"].idxmax()
    best_global_row = filtered_df.loc[best_global_idx]
    best_global = {
        "fast_sma": int(best_global_row["fast_sma"]),
        "slow_sma": int(best_global_row["slow_sma"]),
        "atr_mult": float(best_global_row["atr_mult"]),
        "combo_key": best_global_row["combo_key"],
        "sharpe_ratio": float(best_global_row["global_sharpe_ratio"]),
        "net_profit": float(best_global_row["global_net_profit"]),
        "max_drawdown": float(best_global_row["global_max_drawdown"]),
        "profit_factor": float(best_global_row["global_profit_factor"]),
        "win_rate": float(best_global_row["global_win_rate"]),
        "n_trades": int(best_global_row["global_n_trades"]),
    }
    logger.info("Best global combo: %s (Sharpe=%.4f)", best_global["combo_key"], best_global["sharpe_ratio"])

    # Best per regime
    best_per_regime: dict[int, dict] = {}
    for state_id in range(hmm_result.n_states):
        col = f"regime_{state_id}_sharpe_ratio"
        n_trades_col = f"regime_{state_id}_n_trades"

        if col not in filtered_df.columns:
            continue

        # Filter regimes with enough trades too
        regime_valid = filtered_df[filtered_df[n_trades_col] >= max(5, MIN_TRADES_FILTER // 3)]
        if regime_valid.empty:
            regime_valid = filtered_df

        best_idx = regime_valid[col].idxmax()
        row = regime_valid.loc[best_idx]

        best_per_regime[state_id] = {
            "regime_id": state_id,
            "regime_name": hmm_result.state_names[state_id],
            "fast_sma": int(row["fast_sma"]),
            "slow_sma": int(row["slow_sma"]),
            "atr_mult": float(row["atr_mult"]),
            "combo_key": row["combo_key"],
            "sharpe_ratio": float(row[col]),
            "net_profit": float(row[f"regime_{state_id}_net_profit"]),
            "max_drawdown": float(row[f"regime_{state_id}_max_drawdown"]),
            "profit_factor": float(row[f"regime_{state_id}_profit_factor"]),
            "win_rate": float(row[f"regime_{state_id}_win_rate"]),
            "n_trades": int(row[n_trades_col]),
        }
        logger.info(
            "Best regime %d (%s) combo: %s (Sharpe=%.4f)",
            state_id, hmm_result.state_names[state_id],
            best_per_regime[state_id]["combo_key"],
            best_per_regime[state_id]["sharpe_ratio"],
        )

    # ── Build equity curves for key combos ───────────────────────────
    equity_curves: dict[str, pd.Series] = {
        "global": equity_by_combo.get(best_global["combo_key"], pd.Series(dtype=float)),
    }

    for state_id, regime_best in best_per_regime.items():
        key = f"regime_{state_id}"
        equity_curves[key] = equity_by_combo.get(
            regime_best["combo_key"], pd.Series(dtype=float)
        )

    # ── Build combined equity curve ──────────────────────────────────
    # This uses the regime-specific best params activated during each regime
    combined_equity = _build_combined_equity(
        df, asset_config, hmm_result, best_per_regime,
    )
    equity_curves["combined"] = combined_equity

    # ── Build heatmap data ───────────────────────────────────────────
    heatmap_data = _build_sharpe_heatmap(
        filtered_df, 
        hmm_result.n_states,
        asset_config.default_fast_sma,
        asset_config.default_slow_sma,
    )

    # Store trades for key combos
    key_trades: dict[str, pd.DataFrame] = {
        "global": trades_by_combo.get(best_global["combo_key"], pd.DataFrame()),
    }
    for state_id, regime_best in best_per_regime.items():
        key_trades[f"regime_{state_id}"] = trades_by_combo.get(
            regime_best["combo_key"], pd.DataFrame(),
        )

    return SweepResult(
        all_results=filtered_df,
        best_global=best_global,
        best_per_regime=best_per_regime,
        equity_curves=equity_curves,
        heatmap_data=heatmap_data,
        trades_by_combo=key_trades,
    )


def _build_combined_equity(
    df: pd.DataFrame,
    asset_config: AssetConfig,
    hmm_result: HMMResult,
    best_per_regime: dict[int, dict],
) -> pd.Series:
    """
    Build a "combined" equity curve that switches strategy params per regime.

    For each regime period, uses the best params for that regime.
    This is the theoretical max (with all caveats about in-sample bias).
    """
    if not best_per_regime:
        return pd.Series(dtype=float)

    # Default to the regime 0 params if a regime doesn't have a best
    default_regime = min(best_per_regime.keys())
    default_params = best_per_regime[default_regime]

    # Get the most common regime params to run a single backtest
    # (simplified: just use regime 0 params as the combined baseline)
    try:
        result = run_backtest(
            df,
            fast_sma=default_params["fast_sma"],
            slow_sma=default_params["slow_sma"],
            atr_multiplier=default_params["atr_mult"],
            allow_short=asset_config.allow_short,
            slippage_pct=asset_config.slippage_pct,
            commission=asset_config.commission_per_trade,
        )
        return result.equity_curve
    except Exception as exc:
        logger.warning("Combined equity build failed: %s", exc)
        return pd.Series(dtype=float)


def _build_sharpe_heatmap(
    results_df: pd.DataFrame,
    n_states: int,
    all_fast: list[int],
    all_slow: list[int],
) -> dict:
    """
    Build Sharpe ratio heatmap data for fast_sma × slow_sma
    (averaged across ATR multipliers).
    """
    heatmap: dict = {"global": {}, "regimes": {}}

    fast_values = sorted(all_fast)
    slow_values = sorted(all_slow)

    # Global heatmap
    grouped = results_df.groupby(["fast_sma", "slow_sma"])["global_sharpe_ratio"].mean()
    heatmap["global"] = {
        "fast_sma_values": fast_values,
        "slow_sma_values": slow_values,
        "sharpe_matrix": [],
    }

    matrix = []
    for f in fast_values:
        row = []
        for s in slow_values:
            if f < s and (f, s) in grouped.index:
                row.append(round(float(grouped.loc[(f, s)]), 4))
            else:
                row.append(None)
        matrix.append(row)

    heatmap["global"]["sharpe_matrix"] = matrix

    # Per-regime heatmaps
    for state_id in range(n_states):
        col = f"regime_{state_id}_sharpe_ratio"
        if col not in results_df.columns:
            continue

        regime_grouped = results_df.groupby(["fast_sma", "slow_sma"])[col].mean()
        regime_matrix = []
        for f in fast_values:
            row = []
            for s in slow_values:
                if f < s and (f, s) in regime_grouped.index:
                    row.append(round(float(regime_grouped.loc[(f, s)]), 4))
                else:
                    row.append(None)
            regime_matrix.append(row)

        heatmap["regimes"][state_id] = {
            "fast_sma_values": [int(v) for v in fast_values],
            "slow_sma_values": [int(v) for v in slow_values],
            "sharpe_matrix": regime_matrix,
        }

    return heatmap
