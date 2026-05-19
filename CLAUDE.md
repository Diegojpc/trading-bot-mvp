# AI Trading Bot MVP — Architecture & Context Guide

## 1. Project Overview
This project is an institutional-grade algorithmic trading framework built for analyzing and executing trend-following strategies (specifically SMA crossovers) across varying market conditions. 

The core innovation is the use of a **Gaussian Hidden Markov Model (HMM)**. Instead of blindly trading a moving average, the system mathematically detects the current market "Regime" (e.g., Low Volatility, Crisis) by analyzing historical log returns and volatility. It then optimizes trading parameters (In-Sample) and strictly validates them (Out-Of-Sample) to avoid curve-fitting.

The project is currently transitioning from a pure analytical dashboard to a **Live Execution Engine** via Binance using the `ccxt` library.

## 2. Tech Stack
*   **Backend:** Python 3.12+, FastAPI, Uvicorn, Pandas, NumPy, HMMlearn, scikit-learn, yfinance.
*   **Frontend:** React, TypeScript, Vite, Plotly.js for high-performance interactive charting.
*   **Package Manager (Python):** `uv`
*   **Package Manager (Node):** `npm`

## 3. How to Run the Application
You must run both the backend API and the frontend dev server simultaneously.

**Backend (API running on port 8000):**
```bash
cd "/mnt/Proyectos/Personal Projects/AI Trading Bot/trading_bot_mvp"
uv run uvicorn backend.main:app --reload --port 8000
```

**Frontend (Vite running on port 5173):**
```bash
cd "/mnt/Proyectos/Personal Projects/AI Trading Bot/trading_bot_mvp/frontend"
npm run dev
```

## 4. Key Architectural Concepts
1.  **Strict 70/30 IS/OOS Split:** To prevent curve-fitting, the HMM and the parameter sweep are trained exclusively on the first 70% of historical data. The resulting strategies are then blindly projected onto the remaining 30% of unseen data to validate their true Sharpe ratio.
2.  **Production Mode Toggle:** The frontend contains a "100% Data" toggle. When checked, the bot bypasses OOS validation and trains the HMM and parameter sweep on the entire dataset to prepare the final state matrices for live trading.
3.  **The "Universalist" Philosophy:** Strategies are not swapped based on regimes (which causes overfitting). Instead, a single robust "Global" strategy is selected, and the Regimes are used merely to dictate **position sizing** (e.g., cutting size in half during a "Crisis" regime).

## 5. Directory Structure
*   `backend/api/` — FastAPI routes and endpoints (`routes.py`).
*   `backend/models/` — Machine learning models, specifically the HMM logic (`hmm.py`).
*   `backend/analysis/` — Brute-force backtesting and parameter sweeping (`sweep.py`).
*   `backend/data/` — Market data fetchers (`downloader.py`).
*   `frontend/src/sections/` — Main UI dashboard components (Charts, Tables).
*   `frontend/src/types/` — TypeScript interfaces matching the backend API JSON structure.

## 6. Coding Standards & Behavioral Protocols
*   **Extreme Traceability:** All backend python scripts must feature robust logging. Use appropriate levels (`INFO`, `DEBUG`, `WARNING`, `ERROR`). Log entry points, exit points, and data transformations so execution flow can be perfectly reconstructed.
*   **Zero Complacency:** Code must be objective and brutally honest about risk. Do not sugarcoat metrics or allow look-ahead bias in any mathematical calculations.
*   **UI/UX:** The frontend must maintain a sleek, premium, dark-mode aesthetic. Use rich typography, distinct regime colors, and interactive Plotly charts.
