# AI Trading Bot MVP — Interpretation Guide

This document explains the key metrics, charts, and concepts used in the AI Trading Bot dashboard. It acts as a guide to interpreting the results of the Hidden Markov Model (HMM) analysis and parameter optimization for algorithmic trading.

---

## 1. Regimes (Market States)

The core of this bot is the **Hidden Markov Model (HMM)**. An HMM analyzes the historical data (volatility, returns, momentum) and assumes the market shifts between unobservable "hidden" states (regimes).

We force the model to sort these states by **volatility** (from lowest to highest). When the model selects 5 states (as it did for QQQ), they are defined as:

1. **Regime 0 (Low Vol)**: Quiet, steady, usually slow-grinding bull markets. Low risk, steady returns. (Approx. 24% of the time).
2. **Regime 1 (Med-Low Vol)**: Slightly elevated activity, normal healthy market conditions. (Approx. 23% of the time).
3. **Regime 2 (Medium Vol)**: Choppier conditions, transition phases, or mild corrections. (Approx. 20% of the time).
4. **Regime 3 (High Vol)**: Highly erratic, wide price swings, typical of late-stage bull markets or early bear markets. (Approx. 22% of the time).
5. **Regime 4 (Crisis)**: Extreme panic, crashes, or massive violent rallies (e.g., COVID crash, 2008 financial crisis). Extreme risk. (Approx. 11% of the time).

---

## 2. Regime Timeline & Distribution

### Regime Timeline (Price Chart + Colored Backgrounds)
This chart overlays the detected regime on top of the historical price chart. 
* **What it means:** It allows you to visually verify if the model is correctly identifying market conditions. You should see "Crisis" (usually red or purple) during known crashes (like March 2020), and "Low Vol" (usually green) during steady grinds higher (like 2017).

### Regime Distribution (Pie Chart)
* **What it means:** Shows the percentage of historical days spent in each regime. Markets generally spend most of their time in lower volatility states (Regimes 0, 1, and 2) and less time in Crisis (Regime 4).

---

## 3. BIC Scores (Bayesian Information Criterion)

The bot tests models with 2, 3, 4, and 5 states to see which one fits the data best without overfitting. It uses the **BIC Score** to decide.

* **What it means:** BIC balances model accuracy with simplicity. A model with more states will always fit past data better, but BIC penalizes complexity to prevent curve-fitting.
* **How to read it:** The **lowest** (most negative) BIC score wins. For QQQ, 5 states had the lowest score, meaning the data clearly exhibits 5 distinct market behaviors.

---

## 4. Transition Matrix

This heatmap shows the probability of moving from one regime to another on any given day.

* **What it means:** Markets have "inertia." If you are in a Low Vol regime today, you are highly likely to stay in a Low Vol regime tomorrow.
* **How to read it:** The diagonal from top-left to bottom-right usually has the highest numbers (e.g., 80% chance to stay in the same state). Look for the off-diagonal probabilities to see where the market is likely to transition (e.g., High Vol often transitions to Crisis, but Low Vol almost never jumps straight to Crisis).

---

## 5. Parameter Optimization & Best Parameters Table

The bot tests dozens of parameter combinations for a Simple Moving Average (SMA) crossover strategy:
* **Fast SMA:** Short-term trend (e.g., 5, 10, 15, 20 days).
* **Slow SMA:** Long-term trend (e.g., 30, 50 days).
* **ATR Multiplier:** Stop-loss distance based on Average True Range.

### Best Parameters Table
This table shows the parameter combination that yielded the highest **Sharpe Ratio** overall (Global) and within each specific regime.

* **Global (All Regimes):** The best "universal" parameters. For QQQ, this was often `Fast: 10`, `Slow: 30`, `ATR: 1.5`, meaning a 10/30 crossover worked best across all 10 years.
* **Per Regime:** Shows what parameters performed best *only* during those specific conditions.
  * *Example:* In "Crisis" regimes, a much faster SMA (like 5/30) might perform better because the market moves so violently that you need a highly sensitive trigger to get out quickly.

---

## 6. Sharpe Ratio Heatmap

This chart visualizes the performance (Sharpe Ratio) of all Fast/Slow SMA combinations.

* **What it means:** It shows the "landscape" of profitability. 
* **How to read it:** 
  * Blue/Bright colors = High Sharpe ratio (good risk-adjusted returns).
  * Red/Dark colors = Negative Sharpe ratio (losses).
* **Why it matters:** You want to pick parameters that sit in a "blue neighborhood." If a specific combination (like 10/30) is bright blue, but 10/31 is bright red, the strategy is over-optimized and brittle. A broad blue area indicates robust parameters.

---

## 7. Equity Curves

This chart shows the growth of a hypothetical account trading the best parameters.

* **Global Best (Solid Line):** How the best universal parameters performed over the entire 10-year period.
* **Regime Specific (Dotted Lines):** How a specific set of parameters performed *only* during the days its regime was active (the line goes flat when the regime is inactive).
* **Why it matters:** It proves visually whether a strategy makes money steadily or suffers massive drawdowns.

---

## ⚠️ Critical Concept: In-Sample Over-Optimization

The dashboard displays a warning about **in-sample optimization**. This is the most crucial concept in algorithmic trading:

1. **The Trap:** If you test parameters on data from 2016-2026, and find that 10/30 was the best, you are looking at the past with 20/20 hindsight. There is no guarantee 10/30 will be the best in 2027. This is called "curve-fitting."
2. **The Wrong Way to use HMM:** Do not build a bot that says "If regime = Crisis, switch to 5/30 parameters. If regime = Low Vol, switch to 15/30." This will fail in live trading because it is hyper-optimized to the past.
3. **The Right Way to use HMM:** Use it for **Portfolio Allocation and Risk Management**. 
   * Find a "Universal" strategy (e.g., the Global Best) that survives all regimes.
   * If the HMM detects a "Crisis" regime, you don't change the SMA parameters—instead, you **cut your position size in half**, or turn the strategy off entirely, because the transition matrix tells you conditions are too erratic for a trend-following system to work reliably. 

**Summary:** Regimes tell you *when* to trade and *how big* to trade, not *what parameters* to use.
