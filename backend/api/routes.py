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

from backend.analysis.sweep import SweepResult, run_parameter_sweep, OOSResult, run_oos_validation
from backend.config import ASSET_REGISTRY, REGIME_COLORS, AssetConfig
from backend.data.downloader import download_ohlcv
from backend.models.features import compute_hmm_features
from backend.models.hmm import HMMResult, train_hmm, predict_oos

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
    production_mode: bool = Query(False, description="Train on 100% data (no OOS split)"),
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
        None, _run_analysis_sync, ticker, force_refresh, production_mode,
    )

    return {"status": "started", "ticker": ticker}


def _run_analysis_sync(ticker: str, force_refresh: bool, production_mode: bool):
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

        # ── Step 3: Train/Test Split (70% IS, 30% OOS or 100% IS) ────
        split_pct = 1.0 if production_mode else 0.7
        split_idx = int(len(features) * split_pct)
        is_features = features[:split_idx]
        is_dates = valid_dates[:split_idx]
        oos_features = features[split_idx:]
        oos_dates = valid_dates[split_idx:]
        
        # Also split the OHLCV dataframe (based on the dates that survived feature engineering)
        is_ohlcv = ohlcv.loc[is_dates]
        oos_ohlcv = ohlcv.loc[oos_dates]

        # ── Step 4: HMM training (In-Sample ONLY) ───────────────────
        _update_progress(30, "Training HMM models on IS data (2-5 states)...")
        is_hmm_result = train_hmm(is_features, is_dates)
        _update_progress(40, f"HMM trained: {is_hmm_result.n_states} states selected")
        
        # Project HMM to OOS (if not in production mode)
        _update_progress(42, "Projecting regimes to OOS data...")
        if len(oos_features) > 0:
            oos_hmm_result = predict_oos(is_hmm_result, oos_features, oos_dates)
        else:
            # Dummy OOS HMM result for production mode
            from backend.models.hmm import HMMResult
            oos_hmm_result = HMMResult(
                n_states=is_hmm_result.n_states,
                state_names=is_hmm_result.state_names,
                regime_labels=np.array([]),
                valid_dates=pd.DatetimeIndex([]),
                transition_matrix=is_hmm_result.transition_matrix,
                state_means=is_hmm_result.state_means,
                regime_distribution={},
                bic_scores={},
                state_volatilities=is_hmm_result.state_volatilities,
                model=None,
                state_remap=None
            )

        # ── Step 5: Parameter sweep (In-Sample ONLY) ────────────────
        _update_progress(45, "Running parameter sweep on IS data...")

        def sweep_progress(current: int, total: int):
            pct = 45 + int(40 * current / total) # goes up to 85%
            _update_progress(pct, f"IS Backtesting {current}/{total} combinations...")

        is_sweep_result = run_parameter_sweep(
            is_ohlcv, asset_config, is_hmm_result,
            progress_callback=sweep_progress,
        )
        
        # ── Step 6: OOS Validation ──────────────────────────────────
        _update_progress(85, "Running OOS Validation blindly...")
        if len(oos_features) > 0:
            oos_val_result = run_oos_validation(
                oos_ohlcv, asset_config, oos_hmm_result,
                is_sweep_result.best_global, is_sweep_result.best_per_regime
            )
        else:
            # Dummy OOS Val result for production mode
            from backend.analysis.sweep import OOSResult
            oos_val_result = OOSResult(
                global_metrics={"sharpe_ratio": None, "net_profit": None, "max_drawdown": None, "profit_factor": None, "win_rate": None, "n_trades": 0},
                regime_metrics={},
                equity_curves={"global": pd.Series()}
            )
            
        _analysis_state["production_mode"] = production_mode

        # ── Store results ────────────────────────────────────────────
        _analysis_state["ohlcv"] = ohlcv
        _analysis_state["is_hmm_result"] = is_hmm_result
        _analysis_state["oos_hmm_result"] = oos_hmm_result
        _analysis_state["is_sweep_result"] = is_sweep_result
        _analysis_state["oos_val_result"] = oos_val_result
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
    is_hmm: HMMResult | None = _analysis_state.get("is_hmm_result")
    oos_hmm: HMMResult | None = _analysis_state.get("oos_hmm_result")
    ohlcv: pd.DataFrame | None = _analysis_state.get("ohlcv")

    if is_hmm is None or oos_hmm is None or ohlcv is None:
        raise HTTPException(status_code=404, detail="No analysis results. Run /api/analyze first.")

    # Build combined regime timeline
    combined_dates = is_hmm.valid_dates.append(oos_hmm.valid_dates)
    combined_labels = np.concatenate([is_hmm.regime_labels, oos_hmm.regime_labels])
    
    # Calculate combined distribution for display
    unique, counts = np.unique(combined_labels, return_counts=True)
    total = counts.sum()
    combined_dist = {
        is_hmm.state_names[int(s)]: float(counts[i] / total)
        for i, s in enumerate(unique)
    }

    # Price data for overlay
    price_data = _serialize_series(ohlcv["Close"])

    # Regime timeline
    regime_timeline = {
        "dates": [d.strftime("%Y-%m-%d") for d in combined_dates],
        "labels": combined_labels.tolist(),
    }

    return {
        "n_states": is_hmm.n_states,
        "state_names": is_hmm.state_names,
        "colors": REGIME_COLORS[:is_hmm.n_states],
        "timeline": regime_timeline,
        "distribution": combined_dist,
        "transition_matrix": is_hmm.transition_matrix.round(4).tolist(),
        "bic_scores": {str(k): round(v, 2) for k, v in is_hmm.bic_scores.items()},
        "state_volatilities": is_hmm.state_volatilities.round(4).tolist(),
        "price_data": price_data,
        "split_date": oos_hmm.valid_dates[0].strftime("%Y-%m-%d") if len(oos_hmm.valid_dates) > 0 else None,
        "production_mode": _analysis_state.get("production_mode", False),
    }


@router.get("/results/sweep")
async def get_sweep_results():
    """
    Get parameter sweep results.

    Returns best params per regime, all combo results, and global best.
    """
    sweep: SweepResult | None = _analysis_state.get("is_sweep_result")
    oos_val: OOSResult | None = _analysis_state.get("oos_val_result")
    is_hmm: HMMResult | None = _analysis_state.get("is_hmm_result")

    if sweep is None or is_hmm is None or oos_val is None:
        raise HTTPException(status_code=404, detail="No analysis results. Run /api/analyze first.")

    # Combine IS and OOS metrics into a single response payload
    best_global = sweep.best_global.copy()
    best_global["oos_sharpe_ratio"] = oos_val.global_metrics["sharpe_ratio"]
    best_global["oos_net_profit"] = oos_val.global_metrics["net_profit"]
    best_global["oos_max_drawdown"] = oos_val.global_metrics["max_drawdown"]
    
    best_per_regime = {}
    for state_id, is_regime_data in sweep.best_per_regime.items():
        regime_data = is_regime_data.copy()
        if state_id in oos_val.regime_metrics:
            regime_data["oos_sharpe_ratio"] = oos_val.regime_metrics[state_id]["sharpe_ratio"]
            regime_data["oos_net_profit"] = oos_val.regime_metrics[state_id]["net_profit"]
        else:
            regime_data["oos_sharpe_ratio"] = None
            regime_data["oos_net_profit"] = None
        best_per_regime[str(state_id)] = regime_data

    return _sanitize_for_json({
        "best_global": best_global,
        "best_per_regime": best_per_regime,
        "state_names": is_hmm.state_names,
        "colors": REGIME_COLORS[:is_hmm.n_states],
        "total_combinations": len(sweep.all_results),
        "production_mode": _analysis_state.get("production_mode", False),
    })


@router.get("/results/equity")
async def get_equity_curves():
    """
    Get equity curve data for charting.

    Returns global, per-regime, and combined equity curves, plus price overlay.
    """
    sweep: SweepResult | None = _analysis_state.get("is_sweep_result")
    oos_val: OOSResult | None = _analysis_state.get("oos_val_result")
    is_hmm: HMMResult | None = _analysis_state.get("is_hmm_result")
    oos_hmm: HMMResult | None = _analysis_state.get("oos_hmm_result")
    ohlcv: pd.DataFrame | None = _analysis_state.get("ohlcv")

    if sweep is None or is_hmm is None or ohlcv is None or oos_val is None or oos_hmm is None:
        raise HTTPException(status_code=404, detail="No analysis results.")

    curves: dict[str, dict] = {}

    for key, curve in sweep.equity_curves.items():
        curves[f"is_{key}"] = _serialize_series(curve)
        
    for key, curve in oos_val.equity_curves.items():
        curves[f"oos_{key}"] = _serialize_series(curve)

    # Combined Regime bar data
    combined_dates = is_hmm.valid_dates.append(oos_hmm.valid_dates)
    combined_labels = np.concatenate([is_hmm.regime_labels, oos_hmm.regime_labels])
    
    regime_bar = {
        "dates": [d.strftime("%Y-%m-%d") for d in combined_dates],
        "labels": combined_labels.tolist(),
    }

    return {
        "equity_curves": curves,
        "price_data": _serialize_series(ohlcv["Close"]),
        "regime_bar": regime_bar,
        "state_names": is_hmm.state_names,
        "colors": REGIME_COLORS[:is_hmm.n_states],
        "split_date": oos_hmm.valid_dates[0].strftime("%Y-%m-%d") if len(oos_hmm.valid_dates) > 0 else None,
        "production_mode": _analysis_state.get("production_mode", False),
    }


@router.get("/results/heatmap")
async def get_heatmap_data():
    """
    Get Sharpe ratio heatmap data.

    Returns heatmap matrices for fast_sma × slow_sma, global and per-regime.
    """
    sweep: SweepResult | None = _analysis_state.get("is_sweep_result")
    is_hmm: HMMResult | None = _analysis_state.get("is_hmm_result")

    if sweep is None or is_hmm is None:
        raise HTTPException(status_code=404, detail="No analysis results.")

    return _sanitize_for_json({
        "heatmap": sweep.heatmap_data,
        "state_names": is_hmm.state_names,
        "colors": REGIME_COLORS[:is_hmm.n_states],
    })


# ── Execution Endpoints ──────────────────────────────────────────────────

@router.get("/execution/balance")
async def get_balance(market_type: str = Query("spot")):
    """Fetch current portfolio state from Binance (USDT + BTC)."""
    try:
        from backend.execution.exchange import BinanceExchange
        exchange = BinanceExchange(market_type=market_type)
        free_usdt = exchange.get_usdt_balance()
        btc_held = exchange.get_position("BTC/USDT")
        return {
            "status": "success",
            "market_type": market_type,
            "free_usdt": round(free_usdt, 2),
            "btc_held": round(btc_held, 8),
        }
    except Exception as e:
        logger.error(f"Error fetching balance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/portfolio")
async def get_portfolio_summary(market_type: str = Query("spot")):
    """
    Full portfolio snapshot: balances, current BTC price, trade history, and P&L.
    P&L is calculated from the trade history returned by Binance (last 50 trades).
    """
    try:
        from backend.execution.exchange import BinanceExchange
        exchange = BinanceExchange(market_type=market_type)
        symbol = "BTC/USDT"

        balances = exchange.get_balances()
        price = exchange.fetch_ticker_price(symbol)
        raw_trades = exchange.fetch_my_trades(symbol, limit=50)

        btc_value_usd = balances['btc'] * price
        total_usd = balances['usdt'] + btc_value_usd

        trades = [
            {
                "id": t.get("id"),
                "datetime": t.get("datetime"),
                "side": t.get("side"),
                "amount": round(float(t.get("amount") or 0), 8),
                "price": round(float(t.get("price") or 0), 2),
                "cost": round(float(t.get("cost") or 0), 4),
                "fee_currency": (t.get("fee") or {}).get("currency"),
                "fee_amount": round(float((t.get("fee") or {}).get("cost") or 0), 8),
            }
            for t in raw_trades
        ]

        # P&L based on all returned trades
        buys = [t for t in trades if t["side"] == "buy"]
        sells = [t for t in trades if t["side"] == "sell"]
        total_buy_cost = sum(t["cost"] for t in buys)
        total_bought_btc = sum(t["amount"] for t in buys)
        total_sell_proceeds = sum(t["cost"] for t in sells)
        total_sold_btc = sum(t["amount"] for t in sells)

        net_btc = total_bought_btc - total_sold_btc
        net_cost = total_buy_cost - total_sell_proceeds

        avg_entry = (net_cost / net_btc) if net_btc > 1e-9 else None
        current_val = net_btc * price if net_btc > 1e-9 else 0.0
        unrealized_pnl = (current_val - net_cost) if net_cost > 0 else None
        unrealized_pnl_pct = (unrealized_pnl / net_cost * 100) if net_cost > 0 else None

        return {
            "status": "success",
            "balances": {
                "usdt": round(balances['usdt'], 4),
                "btc": round(balances['btc'], 8),
                "btc_value_usd": round(btc_value_usd, 2),
                "total_usd": round(total_usd, 2),
            },
            "market": {
                "btc_price": round(price, 2),
            },
            "performance": {
                "avg_entry_price": round(avg_entry, 2) if avg_entry else None,
                "total_invested_usd": round(net_cost, 4),
                "unrealized_pnl_usd": round(unrealized_pnl, 4) if unrealized_pnl is not None else None,
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2) if unrealized_pnl_pct is not None else None,
                "total_buys": len(buys),
                "total_sells": len(sells),
            },
            "recent_trades": list(reversed(trades)),  # newest first
        }
    except Exception as e:
        logger.error(f"Portfolio summary failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/execution/diagnostic")
async def get_balance_diagnostic(market_type: str = Query("spot")):
    """
    Dump the raw CCXT balance structure from Binance.
    Use this to diagnose which wallet types CCXT can see.
    """
    try:
        from backend.execution.exchange import BinanceExchange
        exchange = BinanceExchange(market_type=market_type)
        raw = exchange.exchange.fetch_balance()
        non_zero = {
            k: v for k, v in raw.items()
            if isinstance(v, dict) and v.get('total', 0) and v.get('total', 0) != 0
        }
        return {"status": "success", "market_type": market_type, "non_zero_balances": non_zero}
    except Exception as e:
        logger.error(f"Diagnostic failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execution/tick")
async def run_tick(
    ticker: str = Query(..., description="Asset ticker (e.g., BTC-USD)"),
    market_type: str = Query("spot"),
    testnet: bool = Query(False)
):
    """Run a single execution tick (Fetch data, calc regime, calc signal, execute order)."""
    try:
        from backend.execution.bot import run_daily_tick
        result = run_daily_tick(ticker=ticker, market_type=market_type, testnet=testnet)
        return result
    except Exception as e:
        logger.error(f"Error executing tick: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
