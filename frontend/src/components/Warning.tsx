/* ═══════════════════════════════════════════════════════════════════════
   Warning Banner — Out-of-sample validation notice.
   ═══════════════════════════════════════════════════════════════════════ */

export default function Warning() {
  return (
    <div className="warning-banner fade-in-up" id="warning-banner" style={{ borderLeftColor: '#10b981', background: 'rgba(16, 185, 129, 0.05)' }}>
      <div className="warning-banner__title" style={{ color: '#10b981' }}>
        ✅ Out-Of-Sample (OOS) Validated
      </div>
      <div className="warning-banner__text">
        <p>
          This architecture operates on a strict <strong>70% / 30% In-Sample (IS) to Out-Of-Sample (OOS) split</strong>. 
          The HMM transition matrices and the SMA parameter sweep are generated using <strong>only the first 7 years of data</strong>.
          The chosen strategy parameters are then projected forward onto the final 3 years of <strong>unseen testing data</strong> to evaluate their true robustness.
        </p>
        <br />
        <p>
          Compare the <strong>IS Metrics</strong> vs <strong>OOS Metrics</strong> carefully. 
          If a strategy shows exceptional IS returns but negative OOS returns, it has fallen victim to <strong>curve-fitting</strong> and will likely fail in live trading.
          A robust strategy is a <strong>universalist</strong>—surviving and generating profit in both unseen historical regimes and future unpredictable volatility.
        </p>
      </div>
    </div>
  );
}
