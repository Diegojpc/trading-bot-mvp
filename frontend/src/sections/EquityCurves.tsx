/* ═══════════════════════════════════════════════════════════════════════
   EquityCurves — Multi-trace equity chart with regime ribbon.
   ═══════════════════════════════════════════════════════════════════════ */

import Plot from 'react-plotly.js';
import type { EquityResults } from '../types';

interface EquityCurvesProps {
  data: EquityResults;
}

export default function EquityCurves({ data }: EquityCurvesProps) {
  const { equity_curves, price_data, regime_bar, state_names, colors } = data;

  const traces: Plotly.Data[] = [];

  // ── Equity curve traces ─────────────────────────────────────────
  // Global
  if (equity_curves.global?.dates?.length) {
    traces.push({
      x: equity_curves.global.dates,
      y: equity_curves.global.values,
      type: 'scatter',
      mode: 'lines',
      name: 'Global Best',
      line: { color: '#e8ecf4', width: 2 },
      yaxis: 'y1',
      hovertemplate: '%{x}<br>Equity: $%{y:,.0f}<extra>Global Best</extra>',
    });
  }

  // Per-regime
  state_names.forEach((name, i) => {
    const key = `regime_${i}`;
    const curve = equity_curves[key];
    if (curve?.dates?.length) {
      traces.push({
        x: curve.dates,
        y: curve.values,
        type: 'scatter',
        mode: 'lines',
        name: `${name} Best`,
        line: { color: colors[i], width: 1.5, dash: 'dot' },
        yaxis: 'y1',
        opacity: 0.8,
        hovertemplate: `%{x}<br>Equity: $%{y:,.0f}<extra>${name} Best</extra>`,
      });
    }
  });

  // Combined (if available)
  if (equity_curves.combined?.dates?.length) {
    traces.push({
      x: equity_curves.combined.dates,
      y: equity_curves.combined.values,
      type: 'scatter',
      mode: 'lines',
      name: 'Combined',
      line: { color: '#a855f7', width: 2, dash: 'dashdot' },
      yaxis: 'y1',
      hovertemplate: '%{x}<br>Equity: $%{y:,.0f}<extra>Combined</extra>',
    });
  }

  // ── Price on secondary axis ─────────────────────────────────────
  if (price_data.dates.length) {
    traces.push({
      x: price_data.dates,
      y: price_data.values,
      type: 'scatter',
      mode: 'lines',
      name: 'Asset Price',
      line: { color: 'rgba(255,255,255,0.2)', width: 1 },
      yaxis: 'y2',
      hovertemplate: '%{x}<br>Price: $%{y:,.2f}<extra>Asset Price</extra>',
    });
  }

  // ── Regime ribbon shapes ────────────────────────────────────────
  const shapes: Plotly.Shape[] = [];
  if (regime_bar.dates.length) {
    let segStart = 0;
    for (let i = 1; i <= regime_bar.dates.length; i++) {
      if (i === regime_bar.dates.length || regime_bar.labels[i] !== regime_bar.labels[segStart]) {
        shapes.push({
          type: 'rect',
          xref: 'x',
          yref: 'paper',
          x0: regime_bar.dates[segStart],
          x1: regime_bar.dates[Math.min(i, regime_bar.dates.length - 1)],
          y0: 0,
          y1: 0.04,
          fillcolor: colors[regime_bar.labels[segStart]] || '#333',
          opacity: 0.9,
          line: { width: 0 },
        });
        segStart = i;
      }
    }
  }

  return (
    <div className="card fade-in-up" id="equity-curves-section">
      <div className="card__header">
        <div className="card__title">
          <span className="card__title-icon">📈</span>
          Equity Curves
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Click legend entries to toggle traces
        </span>
      </div>

      <Plot
        data={traces}
        layout={{
          height: 500,
          template: 'plotly_dark',
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { t: 20, r: 70, b: 50, l: 70 },
          shapes,
          xaxis: {
            gridcolor: 'rgba(255,255,255,0.04)',
            showgrid: true,
            type: 'date',
          },
          yaxis: {
            title: 'Equity ($)',
            gridcolor: 'rgba(255,255,255,0.04)',
            showgrid: true,
            side: 'left',
          },
          yaxis2: {
            title: 'Price ($)',
            overlaying: 'y',
            side: 'right',
            showgrid: false,
            gridcolor: 'rgba(255,255,255,0.02)',
          },
          legend: {
            orientation: 'h',
            yanchor: 'bottom',
            y: 1.02,
            xanchor: 'center',
            x: 0.5,
            font: { size: 10, color: '#8b95a8' },
            bgcolor: 'transparent',
          },
          hovermode: 'x unified',
        }}
        config={{ responsive: true, displayModeBar: true, displaylogo: false }}
        style={{ width: '100%' }}
        useResizeHandler
      />

      {/* Regime ribbon legend */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          justifyContent: 'center',
          marginTop: '0.5rem',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
        }}
      >
        ↑ Regime ribbon at bottom of chart
      </div>
    </div>
  );
}
