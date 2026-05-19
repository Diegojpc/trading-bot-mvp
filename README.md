# 🤖 AI Trading Bot MVP — HMM Regime Analysis

Market regime detection using Hidden Markov Models with SMA crossover strategy parameter optimization.

## Architecture

```
backend/   → FastAPI + Python (HMM, backtesting, yfinance)
frontend/  → Vite + React + TypeScript + Plotly.js
```

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

## Features

- **Multi-asset support**: QQQ (NASDAQ 100), BTC-USD, SPY, ETH-USD
- **Adaptive strategy**: Long-only for equities, long+short for crypto
- **HMM regime detection**: 2–5 states, BIC model selection, volatility-sorted
- **Parameter sweep**: SMA crossover + ATR stop loss across 48+ combinations
- **Interactive charts**: Plotly.js regime timeline, equity curves, Sharpe heatmaps, transition matrices

## ⚠️ Disclaimer

This is an **in-sample optimization tool** for research purposes. Results are NOT predictive of future performance. See the warning banner in the dashboard for proper use of HMM regime analysis.
