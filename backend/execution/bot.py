import logging
import pandas as pd
from typing import Dict, Any

from backend.execution.exchange import BinanceExchange
from backend.data.downloader import download_ohlcv
from backend.models.features import compute_hmm_features
from backend.models.hmm import train_hmm
from backend.config import ASSET_REGISTRY

logger = logging.getLogger("trading_bot")

# Hardcoded absolute risk limit per the user's instructions
MAX_CAPITAL_USD = 100.0

def calculate_sma_signal(ohlcv: pd.DataFrame, fast_period: int = 10, slow_period: int = 30) -> int:
    """
    Returns 1 if Fast > Slow (Bullish), -1 if Fast < Slow (Bearish).
    Uses the most recent closed bar.
    """
    close = ohlcv['Close']
    fast_sma = close.rolling(fast_period).mean()
    slow_sma = close.rolling(slow_period).mean()
    
    # Get the last valid values
    last_fast = fast_sma.iloc[-1]
    last_slow = slow_sma.iloc[-1]
    
    logger.info(f"Current SMA State: Fast({fast_period})=${last_fast:.2f} | Slow({slow_period})=${last_slow:.2f}")
    
    if pd.isna(last_fast) or pd.isna(last_slow):
        logger.warning("SMAs are NaN. Not enough data.")
        return 0
        
    return 1 if last_fast > last_slow else -1

def run_daily_tick(ticker: str, market_type: str = "spot", testnet: bool = False) -> Dict[str, Any]:
    """
    Executes the daily trading logic:
    1. Update data & identify regime.
    2. Check SMA signal.
    3. Determine target exposure.
    4. Execute order to match exposure.
    """
    logger.info(f"=== STARTING LIVE EXECUTION TICK for {ticker} ({market_type.upper()}) ===")
    
    if ticker not in ASSET_REGISTRY:
        raise ValueError(f"Unknown ticker {ticker}")
        
    asset_config = ASSET_REGISTRY[ticker]
    exchange = BinanceExchange(market_type=market_type, testnet=testnet)
    
    # 1. Fetch latest data (Force refresh to ensure we have today's data)
    logger.info("Downloading latest market data...")
    ohlcv = download_ohlcv(asset_config, force_refresh=True)
    
    # 2. Determine Current Regime (Train on 100% data as per Production Mode)
    logger.info("Computing HMM features to determine current regime...")
    features, valid_dates = compute_hmm_features(ohlcv, window=asset_config.rolling_window)
    hmm_result = train_hmm(features, valid_dates)
    
    current_regime_idx = hmm_result.regime_labels[-1]
    current_regime_name = hmm_result.state_names[current_regime_idx]
    logger.info(f"Current Market Regime: {current_regime_name}")
    
    # 3. Check Signal (Global 10/30)
    signal = calculate_sma_signal(ohlcv, fast_period=10, slow_period=30)
    signal_label = "BULLISH" if signal == 1 else "BEARISH"
    logger.info(f"Current SMA Signal: {signal_label}")
    
    # 4. Determine Target Allocation
    # Risk Engine Rules:
    # - If Regime is "Crisis", exposure = 0% (Cash)
    # - If Signal is Bearish (-1), exposure = 0% (Cash)
    # - If Signal is Bullish (1) and not Crisis, exposure = 100% (of MAX_CAPITAL_USD)
    
    target_exposure_usd = 0.0
    if current_regime_name == "Crisis":
        logger.warning("🚨 CRISIS REGIME DETECTED. Forcing target exposure to $0 (Cash).")
        target_exposure_usd = 0.0
    elif signal == 1:
        logger.info(f"Bullish signal in {current_regime_name}. Targeting max capital.")
        target_exposure_usd = MAX_CAPITAL_USD
    else:
        logger.info("Bearish signal. Targeting $0 (Cash).")
        target_exposure_usd = 0.0
        
    # Get account state from Binance
    free_usdt = exchange.get_usdt_balance()
    current_price = ohlcv['Close'].iloc[-1]
    
    # Get current position (BTC already held)
    symbol = "BTC/USDT" if ticker == "BTC-USD" else f"{ticker.split('-')[0]}/USDT"
    current_pos_base = exchange.get_position(symbol)
    current_pos_usd = current_pos_base * current_price
    total_portfolio_usd = free_usdt + current_pos_usd
    
    logger.info(f"=== PORTFOLIO STATE ===")
    logger.info(f"  Free USDT: ${free_usdt:.2f}")
    logger.info(f"  BTC held: {current_pos_base:.8f} (~${current_pos_usd:.2f})")
    logger.info(f"  Total portfolio: ${total_portfolio_usd:.2f}")
    logger.info(f"  Current BTC price: ${current_price:.2f}")
    logger.info(f"  Target exposure: ${target_exposure_usd:.2f}")
    
    # Build base response (always included in every return)
    base_response = {
        "current_regime": current_regime_name,
        "signal": signal,
        "signal_label": signal_label,
        "target_usd": target_exposure_usd,
        "portfolio": {
            "free_usdt": round(free_usdt, 2),
            "btc_held": round(current_pos_base, 8),
            "btc_value_usd": round(current_pos_usd, 2),
            "total_usd": round(total_portfolio_usd, 2),
            "btc_price": round(current_price, 2),
        }
    }
    
    # 5. Calculate Order Size
    # Cap target to MAX_CAPITAL_USD or total portfolio, whichever is smaller
    effective_target = min(target_exposure_usd, total_portfolio_usd)
    diff_usd = effective_target - current_pos_usd
    
    # Binance minimum order size is usually ~$5 for Spot, avoid dust trades
    MIN_ORDER_USD = 5.0
    
    if abs(diff_usd) < MIN_ORDER_USD:
        reason = "Already at target" if current_pos_usd > 0 else "Difference too small"
        logger.info(f"Difference (${diff_usd:.2f}) is below minimum order size (${MIN_ORDER_USD}). {reason}.")
        return {
            **base_response,
            "status": "holding" if current_pos_usd > 0 and signal == 1 else "skipped",
            "reason": reason,
        }
        
    order_amount_base = abs(diff_usd) / current_price
    side = "buy" if diff_usd > 0 else "sell"
    
    # Check if we have enough USDT to buy — cap to available balance
    if side == "buy":
        if free_usdt < MIN_ORDER_USD:
            logger.info(f"Want to buy ${abs(diff_usd):.2f} but only ${free_usdt:.2f} USDT free (below ${MIN_ORDER_USD} min).")
            if current_pos_usd > 0:
                logger.info(f"Already holding ${current_pos_usd:.2f} worth of BTC. Holding position.")
                return {
                    **base_response,
                    "status": "holding",
                    "reason": f"Already holding ${current_pos_usd:.2f} BTC. No free USDT to add more.",
                }
            else:
                return {
                    **base_response,
                    "status": "error",
                    "reason": f"Insufficient USDT (${free_usdt:.2f} available, ${MIN_ORDER_USD} minimum)",
                }
        elif free_usdt < abs(diff_usd):
            logger.warning(f"Capping buy order from ${abs(diff_usd):.2f} to available ${free_usdt:.2f} USDT.")
            diff_usd = free_usdt
            order_amount_base = abs(diff_usd) / current_price
        
    # 6. Execute Order
    logger.info(f"Executing {side.upper()} order for {order_amount_base:.8f} {symbol} (~${abs(diff_usd):.2f})")
    result = exchange.execute_market_order(symbol, side, order_amount_base)
    
    logger.info("=== TICK COMPLETE ===")
    
    return {
        **base_response,
        "status": "executed",
        "order": result,
        "side": side,
        "amount_usd": round(abs(diff_usd), 2),
    }
