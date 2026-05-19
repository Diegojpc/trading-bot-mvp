# Trading Operations Guide: How to Execute

This guide provides a practical, step-by-step framework for using the AI Trading Bot's dashboard to actively trade your chosen asset (e.g., QQQ or BTC-USD). 

**Core Philosophy:** We use the **Global Best Parameters** for our trade signals (to avoid curve-fitting), and we use the **Current Regime** exclusively to dictate our **Position Sizing** and risk management.

---

## Step 1: The Daily Routine (Market Close)

This strategy operates on a Daily (D1) timeframe. You should run this routine once per day, ideally right before the market closes or immediately after.

1. **Open the Dashboard:** Launch the frontend and select your asset.
2. **Run Analysis:** Click "Run Analysis" to fetch the latest daily candle and recalculate the HMM regimes.
3. **Identify Current Regime:** Look at the far right edge of the **Regime Timeline** chart. Identify the color/state of the current day. Is the market currently in *Low Vol*, *Medium Vol*, or *Crisis*?
4. **Check the Global Best Parameters:** Look at the "Best Parameters" table and note the **Global (All Regimes)** values. For example: `Fast SMA: 10`, `Slow SMA: 30`, `ATR Mult: 1.5`.

---

## Step 2: Determine Your Position Size (Regime Filter)

This is the most critical step. The HMM tells you *how aggressive* you should be. You must define a "Base Position Size" (e.g., 10% of your total portfolio per trade). You then scale this base size depending on the regime.

Here is a recommended scaling matrix:

| Current Regime | Market Condition | Action / Position Sizing | Rationale |
| :--- | :--- | :--- | :--- |
| **0 - Low Vol** | Steady, quiet | **100% (Full Size)** | Trend-following strategies thrive here. Few false signals. |
| **1 - Med-Low Vol** | Normal | **100% (Full Size)** | Standard healthy market. |
| **2 - Medium Vol** | Choppy | **50% (Half Size)** | Increased risk of whipsaws (false breakouts). Reduce exposure. |
| **3 - High Vol** | Erratic | **25% (Quarter Size)** | Trends break down quickly. Stops are hit frequently. Protect capital. |
| **4 - Crisis** | Panic/Crash | **0% (Do Not Trade)** | Stay in cash. Moving averages are useless in a crash. |

*Action:* Calculate today's specific dollar allocation based on the current regime.

---

## Step 3: Check for Trading Signals

Now, apply the **Global Best Parameters** (e.g., 10/30 SMA) to your actual trading platform (e.g., TradingView, ThinkOrSwim, Binance).

1. Open your charting platform for the asset (e.g., QQQ).
2. Add a Fast SMA (e.g., length 10) and a Slow SMA (e.g., length 30).
3. **Check the Signal:**
   * **LONG SIGNAL:** The Fast SMA crosses *above* the Slow SMA.
   * **SHORT SIGNAL:** The Fast SMA crosses *below* the Slow SMA (Only applicable if the asset config allows shorting, like Crypto).
   * **FLAT/HOLD:** No crossover occurred today.

*Action:* If a crossover occurred today, you have a signal to enter a trade. If you are already in a trade and an opposite crossover occurs, you have a signal to close the position.

---

## Step 4: Calculate the Stop Loss (ATR)

If you have an entry signal, you must calculate your stop loss *before* executing the trade, using the **ATR Multiplier** from the Global Best Parameters.

1. Add an ATR (Average True Range) indicator to your chart (default 14-day length is fine).
2. Note the current ATR value.
3. Multiply the ATR value by your global multiplier (e.g., `ATR Value * 1.5`).
4. **Long Trade:** Subtract this calculated value from your entry price. This is your hard Stop Loss.
5. **Short Trade:** Add this calculated value to your entry price. This is your hard Stop Loss.

---

## Step 5: Execute and Manage

1. **Execute:** Place the trade at your broker using the scaled Position Size calculated in Step 2.
2. **Set the Stop:** Immediately place a hard Stop Market order at the price calculated in Step 4.
3. **Manage (Trailing):** 
   * As the price moves in your favor, the ATR value will change. 
   * *Optional but recommended:* Recalculate your ATR stop daily and trail it upwards (for longs) to lock in profit. **Never** move a stop loss further away to give a losing trade "more room."
4. **Exit:** You exit the trade entirely when either:
   * Your ATR Stop Loss is hit.
   * The Fast SMA crosses back over the Slow SMA in the opposite direction.
   * The HMM shifts into a "Crisis" regime (forcing a 0% allocation).

---

## Example Scenario

* **Asset:** QQQ
* **Global Best:** 10/30 SMA, 1.5 ATR.
* **Base Size:** $10,000 per trade.
* **Today's Action:**
  1. Run analysis. Dashboard shows we just entered **Regime 2 (Medium Vol)**.
  2. Because it's Medium Vol, we scale our base size to **50%** ($5,000).
  3. We look at QQQ on TradingView. The 10 SMA just crossed above the 30 SMA. **Long Signal**.
  4. QQQ price is $450. ATR is $5.00.
  5. Stop Loss = $450 - ($5.00 * 1.5) = **$442.50**.
  6. We buy $5,000 of QQQ at $450, and place a Stop order at $442.50.
