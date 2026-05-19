/* ═══════════════════════════════════════════════════════════════════════
   RegimeTimeline — Price chart with regime background + pie chart.
   ═══════════════════════════════════════════════════════════════════════ */

import Plot from '../components/Plot';
import type { RegimeResults } from '../types';

interface RegimeTimelineProps {
  data: RegimeResults;
}

export default function RegimeTimeline({ data }: RegimeTimelineProps) {
  const { timeline, price_data, colors, state_names, distribution, bic_scores } = data;

  // ── Build regime background shapes ──────────────────────────────
  const shapes: Plotly.Shape[] = [];
  let segStart = 0;

  for (let i = 1; i <= timeline.dates.length; i++) {
    if (i === timeline.dates.length || timeline.labels[i] !== timeline.labels[segStart]) {
      shapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: timeline.dates[segStart],
        x1: timeline.dates[Math.min(i, timeline.dates.length - 1)],
        y0: 0,
        y1: 1,
        fillcolor: colors[timeline.labels[segStart]] || '#333',
        opacity: 0.08,
        line: { width: 0 },
        layer: 'below',
      });
      segStart = i;
    }
  }

  // ── Price trace ─────────────────────────────────────────────────
  const priceTrace: Plotly.Data = {
    x: price_data.dates,
    y: price_data.values,
    type: 'scatter',
    mode: 'lines',
    name: 'Price',
    line: { color: '#e8ecf4', width: 1.5 },
    hovertemplate: '%{x}<br>Price: $%{y:,.2f}<extra></extra>',
  };

  // ── Pie chart data ──────────────────────────────────────────────
  const pieLabels = Object.keys(distribution);
  const pieValues = Object.values(distribution).map((v) => +(v * 100).toFixed(1));
  const pieColors = pieLabels.map((_, i) => colors[i] || '#333');

  // ── BIC bar data ────────────────────────────────────────────────
  const bicStates = Object.keys(bic_scores);
  const bicValues = Object.values(bic_scores);

  return (
    <div className="card fade-in-up" id="regime-timeline-section">
      <div className="card__header">
        <div className="card__title">
          <span className="card__title-icon">📊</span>
          Regime Timeline
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {data.n_states} states detected (BIC selection)
        </span>
      </div>

      {/* Price chart with regime bands */}
      <Plot
        data={[priceTrace]}
        layout={{
          height: 400,
          template: 'plotly_dark',
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { t: 20, r: 40, b: 40, l: 60 },
          shapes,
          xaxis: {
            gridcolor: 'rgba(255,255,255,0.04)',
            showgrid: true,
            type: 'date',
          },
          yaxis: {
            title: 'Price ($)',
            gridcolor: 'rgba(255,255,255,0.04)',
            showgrid: true,
          },
          hovermode: 'x unified',
          showlegend: false,
        }}
        config={{ responsive: true, displayModeBar: true, displaylogo: false }}
        style={{ width: '100%' }}
        useResizeHandler
      />

      {/* Pie + BIC row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginTop: '1rem' }}>
        {/* Pie chart */}
        <Plot
          data={[
            {
              values: pieValues,
              labels: pieLabels,
              type: 'pie',
              marker: { colors: pieColors },
              textinfo: 'label+percent',
              textfont: { size: 11, color: '#e8ecf4' },
              hovertemplate: '%{label}<br>%{value:.1f}% of days<extra></extra>',
              hole: 0.45,
            },
          ]}
          layout={{
            height: 280,
            template: 'plotly_dark',
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 30, r: 20, b: 20, l: 20 },
            title: { text: 'Regime Distribution', font: { size: 13, color: '#8b95a8' } },
            showlegend: false,
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%' }}
          useResizeHandler
        />

        {/* BIC scores */}
        <Plot
          data={[
            {
              x: bicStates.map((s) => `${s} states`),
              y: bicValues,
              type: 'bar',
              marker: {
                color: bicStates.map((s) =>
                  s === String(data.n_states) ? '#3b82f6' : 'rgba(255,255,255,0.15)'
                ),
                line: { color: '#3b82f6', width: 1 },
              },
              hovertemplate: '%{x}<br>BIC: %{y:,.0f}<extra></extra>',
            },
          ]}
          layout={{
            height: 280,
            template: 'plotly_dark',
            paper_bgcolor: 'transparent',
            plot_bgcolor: 'transparent',
            margin: { t: 30, r: 20, b: 40, l: 70 },
            title: { text: 'BIC Scores (lower = better)', font: { size: 13, color: '#8b95a8' } },
            xaxis: { gridcolor: 'rgba(255,255,255,0.04)' },
            yaxis: { gridcolor: 'rgba(255,255,255,0.04)' },
            showlegend: false,
          }}
          config={{ responsive: true, displayModeBar: false }}
          style={{ width: '100%' }}
          useResizeHandler
        />
      </div>

      {/* Regime legend */}
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem', flexWrap: 'wrap' }}>
        {state_names.map((name, i) => (
          <div
            key={name}
            className="regime-badge"
            style={{ backgroundColor: `${colors[i]}20`, color: colors[i], border: `1px solid ${colors[i]}40` }}
          >
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: colors[i], display: 'inline-block' }} />
            {name}
          </div>
        ))}
      </div>
    </div>
  );
}
