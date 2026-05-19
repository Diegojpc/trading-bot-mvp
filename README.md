# 🤖 AI Trading Bot — HMM Regime Analysis + Live Execution

An institutional-grade algorithmic trading framework that combines **Gaussian Hidden Markov Models** for market regime detection with **SMA crossover** trend-following strategies. The system validates strategies using strict **Out-Of-Sample (OOS) testing** to eliminate curve-fitting, and executes live trades directly on **Binance** via the CCXT library.

---

## Architecture

```
backend/
├── api/            → FastAPI REST endpoints (analysis, execution, results)
├── analysis/       → Brute-force parameter sweep & OOS validation engine
├── config.py       → Asset registry & regime color palette
├── data/           → Market data downloader (yfinance) with parquet caching
├── execution/      → Live trading engine (CCXT → Binance Spot/Futures)
├── models/         → Gaussian HMM training, feature engineering, state projection
└── strategy/       → Backtest engine, SMA signal generation, performance metrics

frontend/
├── src/api/        → Typed fetch wrapper for all backend endpoints
├── src/components/ → Reusable UI components (Plot, MetricCard, Warning, Spinner)
├── src/sections/   → Dashboard panels (RegimeTimeline, EquityCurves, ParameterTable, Heatmap)
└── src/types/      → TypeScript interfaces matching backend JSON schemas
```

## Features

### 📊 Analysis Engine
- **Multi-asset support**: QQQ (NASDAQ 100), BTC-USD, SPY, ETH-USD
- **HMM regime detection**: Gaussian HMM with 2–5 states, BIC model selection, volatility-sorted state naming (Low Vol → Crisis)
- **Parameter sweep**: SMA crossover + ATR trailing stop across 20+ combinations per regime
- **Interactive charts**: Plotly.js regime timeline, equity curves, Sharpe heatmaps, transition matrices

### 🔬 Out-Of-Sample Validation
- **70/30 time-series split**: HMM and parameter sweep are trained exclusively on the first 70% of data
- **Blind OOS testing**: Best parameters are locked and tested on the remaining 30% of unseen market data
- **Robustness scoring**: Side-by-side IS Sharpe vs OOS Sharpe comparison to instantly identify overfitted strategies
- **Production Mode toggle**: Train on 100% of data after validation is confirmed, preparing the model for live deployment

### ⚡ Live Execution Engine (Binance)
- **Direct exchange connectivity** via CCXT — no TradingView or MetaTrader required
- **Spot & Futures support**: Configurable market type per trade
- **Regime-aware risk management**: Automatically goes to cash during "Crisis" regimes
- **Hard capital limit**: Configurable maximum exposure (default $100 USD) — the bot will never risk more than this amount
- **Smart order capping**: If available balance is below target, the bot caps the order to what you have instead of failing
- **Dashboard control**: Manual "Run Daily Tick" button for supervised execution with real-time result feedback
- **Balance tracking**: Live Binance USDT balance displayed in the dashboard header

---

## Quick Start

### 1. Backend

```bash
# Install Python dependencies (requires uv)
uv sync

# Start the API server
uv run uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Open Dashboard

Navigate to **http://localhost:5173**, select an asset, and click **Run Analysis**.

### 4. Live Trading Setup (Optional)

```bash
# 1. Create your .env file from the template
cp .env.template .env

# 2. Edit .env and paste your Binance API Key and Secret Key
#    NEVER commit the .env file to git

# 3. Transfer USDT from Binance Funding Wallet → Spot Wallet

# 4. Open the dashboard, select BTC-USD, click "⚡ Run Daily Tick"
```

---

## How the Strategy Works

1. **Regime Detection**: The Gaussian HMM analyzes 10 years of daily returns and volatility to classify the market into 5 states: Low Vol, Med-Low Vol, Medium Vol, High Vol, and Crisis.

2. **Signal Generation**: A 10-period Fast SMA / 30-period Slow SMA crossover determines the trend direction. Fast > Slow = Bullish. Fast < Slow = Bearish.

3. **Risk Management**: The HMM regime controls **position sizing**, not signal parameters:
   - Bullish signal + Normal regime → Buy up to max capital
   - Bullish signal + Crisis regime → Stay in cash (regime override)
   - Bearish signal + Any regime → Stay in cash

4. **Execution**: The bot compares the target allocation to the current Binance position and fires a market order to close the gap.

---

## Key Design Principles

- **No curve-fitting**: Parameters are validated on unseen data before deployment
- **Universalist strategy**: One robust global parameter set across all regimes — no regime-switching of indicators
- **Regimes for sizing, not signals**: The HMM tells you *when* to trade and *how big*, not *what parameters* to use
- **Extreme traceability**: Every function logs entry points, state changes, and errors with full context

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. Algorithmic trading involves substantial risk of financial loss. Past performance (including backtested results) is NOT indicative of future results. The authors are not responsible for any trading losses incurred through the use of this software. Always test with small amounts you can afford to lose.
