"""
REST API routes — endpoints for frontend consumption.

Provides endpoints for triggering analysis, checking status, and retrieving results.
"""

import asyncio
import logging
import traceback
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.analysis.sweep import SweepResult, run_parameter_sweep
from backend.config import ASSET_REGISTRY, REGIME_COLORS, AssetConfig
from backend.data.downloader import download_ohlcv
from backend.models.features import compute_hmm_features
from backend.models.hmm import HMMResult, train_hmm

logger = logging.getLogger("trading_bot")
router = APIRouter(prefix="/api")

# ── In-memory state ──────────────────────────────────────────────────────
_analysis_state: dict[str, Any] = {
    "status": "idle",          # idle | running | complete | error
    "progress": 0,             # 0-100
    "progress_message": "",
    "current_asset": None,
    "error": None,
    # Results (populated after analysis)
    "ohlcv": None,             # pd.DataFrame
    "hmm_result": None,        # HMMResult
    "sweep_result": None,      # SweepResult
    "asset_config": None,      # AssetConfig
}
_analysis_lock = asyncio.Lock()


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replace inf/-inf/NaN with JSON-safe values."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if np.isnan(obj):
            return None
        if np.isinf(obj):
            return 9999.0 if obj > 0 else -9999.0
        return obj
    elif isinstance(obj, (np.floating,)):
        return _sanitize_for_json(float(obj))
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def _serialize_df(df: pd.DataFrame) -> list[dict]:
    """Convert DataFrame to list of dicts, handling dates and NaN."""
    if df is None or df.empty:
        return []

    result = df.copy()
    for col in result.columns:
        if pd.api.types.is_datetime64_any_dtype(result[col]):
            result[col] = result[col].dt.strftime("%Y-%m-%d")

    return result.replace({np.nan: None, np.inf: None, -np.inf: None}).to_dict(orient="records")


def _serialize_series(s: pd.Series) -> dict:
    """Convert Series with DatetimeIndex to {dates, values}."""
    if s is None or s.empty:
        return {"dates": [], "values": []}

    dates = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in s.index]
    values = [None if (pd.isna(v) or np.isinf(v)) else round(float(v), 2) for v in s.values]
    return {"dates": dates, "values": values}


# ─────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "message": "Trading Bot API is running"}


@router.get("/assets")
async def list_assets():
    """Return available assets for analysis."""
    assets = []
    for key, config in ASSET_REGISTRY.items():
        assets.append({
            "ticker": config.ticker,
            "display_name": config.display_name,
            "asset_type": config.asset_type,
            "allow_short": config.allow_short,
        })
    return {"assets": assets}


@router.post("/analyze")
async def start_analysis(
    ticker: str = Query(..., description="Asset ticker (e.g., QQQ, BTC-USD)"),
    force_refresh: bool = Query(False, description="Force re-download data"),
):
    """
    Trigger full analysis pipeline for a given asset.

    This runs asynchronously in the background. Poll /api/status for progress.
    """
    global _analysis_state

    if ticker not in ASSET_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ticker '{ticker}'. Available: {list(ASSET_REGISTRY.keys())}",
        )

    async with _analysis_lock:
        if _analysis_state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="Analysis already in progress. Wait for completion.",
            )

        _analysis_state["status"] = "running"
        _analysis_state["progress"] = 0
        _analysis_state["progress_message"] = "Starting..."
        _analysis_state["current_asset"] = ticker
        _analysis_state["error"] = None

    # Run in background thread to not block the event loop
    asyncio.get_event_loop().run_in_executor(
        None, _run_analysis_sync, ticker, force_refresh,
    )

    return {"status": "started", "ticker": ticker}


def _run_analysis_sync(ticker: str, force_refresh: bool):
    """Synchronous analysis pipeline — runs in a thread pool."""
    global _analysis_state

    asset_config = ASSET_REGISTRY[ticker]

    try:
        # ── Step 1: Download data ────────────────────────────────────
        _update_progress(5, "Downloading market data...")
        logger.info("=== ANALYSIS START — %s ===", ticker)

        ohlcv = download_ohlcv(asset_config, force_refresh=force_refresh)
        _update_progress(15, f"Downloaded {len(ohlcv)} bars of data")

        # ── Step 2: Feature engineering ──────────────────────────────
        _update_progress(20, "Computing HMM features...")
        features, valid_dates = compute_hmm_features(
            ohlcv, window=asset_config.rolling_window,
        )
        _update_progress(25, f"Features computed: {features.shape[0]} valid rows")

        # ── Step 3: HMM training ────────────────────────────────────
        _update_progress(30, "Training HMM models (2-5 states)...")
        hmm_result = train_hmm(features, valid_dates)
        _update_progress(40, f"HMM trained: {hmm_result.n_states} states selected")

        # ── Step 4: Parameter sweep ──────────────────────────────────
        _update_progress(45, "Running parameter sweep...")

        def sweep_progress(current: int, total: int):
            pct = 45 + int(50 * current / total)
            _update_progress(pct, f"Backtesting {current}/{total} combinations...")

        sweep_result = run_parameter_sweep(
            ohlcv, asset_config, hmm_result,
            progress_callback=sweep_progress,
        )

        # ── Store results ────────────────────────────────────────────
        _analysis_state["ohlcv"] = ohlcv
        _analysis_state["hmm_result"] = hmm_result
        _analysis_state["sweep_result"] = sweep_result
        _analysis_state["asset_config"] = asset_config
        _analysis_state["status"] = "complete"
        _update_progress(100, "Analysis complete!")
        logger.info("=== ANALYSIS COMPLETE — %s ===", ticker)

    except Exception as exc:
        logger.error("Analysis failed: %s", exc, exc_info=True)
        _analysis_state["status"] = "error"
        _analysis_state["error"] = str(exc)
        _analysis_state["progress_message"] = f"Error: {exc}"


def _update_progress(pct: int, message: str):
    """Update the analysis progress state."""
    _analysis_state["progress"] = pct
    _analysis_state["progress_message"] = message
    logger.info("Progress: %d%% — %s", pct, message)


@router.get("/status")
async def get_status():
    """Get current analysis status and progress."""
    return {
        "status": _analysis_state["status"],
        "progress": _analysis_state["progress"],
        "message": _analysis_state["progress_message"],
        "current_asset": _analysis_state["current_asset"],
        "error": _analysis_state["error"],
    }


@router.get("/results/regimes")
async def get_regime_results():
    """
    Get regime detection results.

    Returns regime timeline, distribution, transition matrix, and BIC scores.
    """
    hmm: HMMResult | None = _analysis_state.get("hmm_result")
    ohlcv: pd.DataFrame | None = _analysis_state.get("ohlcv")

    if hmm is None or ohlcv is None:
        raise HTTPException(status_code=404, detail="No analysis results. Run /api/analyze first.")

    # Build regime timeline (aligned with full OHLCV data)
    regime_series = pd.Series(hmm.regime_labels, index=hmm.valid_dates)

    # Price data for overlay
    price_data = _serialize_series(ohlcv["Close"])

    # Regime timeline
    regime_timeline = {
        "dates": [d.strftime("%Y-%m-%d") for d in hmm.valid_dates],
        "labels": hmm.regime_labels.tolist(),
    }

    return {
        "n_states": hmm.n_states,
        "state_names": hmm.state_names,
        "colors": REGIME_COLORS[:hmm.n_states],
        "timeline": regime_timeline,
        "distribution": hmm.regime_distribution,
        "transition_matrix": hmm.transition_matrix.round(4).tolist(),
        "bic_scores": {str(k): round(v, 2) for k, v in hmm.bic_scores.items()},
        "state_volatilities": hmm.state_volatilities.round(4).tolist(),
        "price_data": price_data,
    }


@router.get("/results/sweep")
async def get_sweep_results():
    """
    Get parameter sweep results.

    Returns best params per regime, all combo results, and global best.
    """
    sweep: SweepResult | None = _analysis_state.get("sweep_result")
    hmm: HMMResult | None = _analysis_state.get("hmm_result")

    if sweep is None or hmm is None:
        raise HTTPException(status_code=404, detail="No analysis results. Run /api/analyze first.")

    return _sanitize_for_json({
        "best_global": sweep.best_global,
        "best_per_regime": {
            str(k): v for k, v in sweep.best_per_regime.items()
        },
        "state_names": hmm.state_names,
        "colors": REGIME_COLORS[:hmm.n_states],
        "total_combinations": len(sweep.all_results),
    })


@router.get("/results/equity")
async def get_equity_curves():
    """
    Get equity curve data for charting.

    Returns global, per-regime, and combined equity curves, plus price overlay.
    """
    sweep: SweepResult | None = _analysis_state.get("sweep_result")
    hmm: HMMResult | None = _analysis_state.get("hmm_result")
    ohlcv: pd.DataFrame | None = _analysis_state.get("ohlcv")

    if sweep is None or hmm is None or ohlcv is None:
        raise HTTPException(status_code=404, detail="No analysis results.")

    curves: dict[str, dict] = {}

    for key, curve in sweep.equity_curves.items():
        curves[key] = _serialize_series(curve)

    # Regime bar data
    regime_bar = {
        "dates": [d.strftime("%Y-%m-%d") for d in hmm.valid_dates],
        "labels": hmm.regime_labels.tolist(),
    }

    return {
        "equity_curves": curves,
        "price_data": _serialize_series(ohlcv["Close"]),
        "regime_bar": regime_bar,
        "state_names": hmm.state_names,
        "colors": REGIME_COLORS[:hmm.n_states],
    }


@router.get("/results/heatmap")
async def get_heatmap_data():
    """
    Get Sharpe ratio heatmap data.

    Returns heatmap matrices for fast_sma × slow_sma, global and per-regime.
    """
    sweep: SweepResult | None = _analysis_state.get("sweep_result")
    hmm: HMMResult | None = _analysis_state.get("hmm_result")

    if sweep is None or hmm is None:
        raise HTTPException(status_code=404, detail="No analysis results.")

    return _sanitize_for_json({
        "heatmap": sweep.heatmap_data,
        "state_names": hmm.state_names,
        "colors": REGIME_COLORS[:hmm.n_states],
    })
