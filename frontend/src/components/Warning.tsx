/* ═══════════════════════════════════════════════════════════════════════
   Warning Banner — In-sample over-optimization disclaimer.
   ═══════════════════════════════════════════════════════════════════════ */

export default function Warning() {
  return (
    <div className="warning-banner fade-in-up" id="warning-banner">
      <div className="warning-banner__title">
        ⚠️ Critical Disclaimer — In-Sample Over-Optimization
      </div>
      <div className="warning-banner__text">
        <p>
          This analysis performs <strong>in-sample parameter optimization</strong> — the strategy
          parameters are being optimized on the <strong>same data used to evaluate them</strong>.
          Results shown here are <strong>NOT predictive of future performance</strong> and should
          <strong>never</strong> be used directly for live trading without proper out-of-sample
          validation.
        </p>
        <br />
        <p>
          <strong>The correct use of HMM regime analysis</strong> is to classify strategies as
          <strong> universalists vs. specialists</strong> — strategies that perform well across all
          regimes vs. those that only shine in specific conditions. This informs{' '}
          <strong>portfolio-level decisions</strong>: which strategies to activate/deactivate and
          with what position sizing per regime. It is <strong>NOT</strong> meant to change signal
          parameters per regime — that's curve-fitting.
        </p>
      </div>
    </div>
  );
}
