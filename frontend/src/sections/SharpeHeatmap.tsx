/* ═══════════════════════════════════════════════════════════════════════
   SharpeHeatmap — Fast SMA × Slow SMA Sharpe ratio heatmap.
   ═══════════════════════════════════════════════════════════════════════ */

import { useState } from 'react';
import Plot from '../components/Plot';
import type { HeatmapResults } from '../types';

interface SharpeHeatmapProps {
  data: HeatmapResults;
}

export default function SharpeHeatmap({ data }: SharpeHeatmapProps) {
  const { heatmap, state_names, colors } = data;
  const [activeTab, setActiveTab] = useState<string>('global');

  // Get the active heatmap data
  let activeData = heatmap.global;
  if (activeTab !== 'global' && heatmap.regimes[activeTab]) {
    activeData = heatmap.regimes[activeTab];
  }

  if (!activeData) return null;

  // Build the colorscale based on active tab
  const baseColor = activeTab === 'global' ? '#3b82f6' : (colors[Number(activeTab)] || '#3b82f6');

  // Determine z-range for symmetric colorscale
  const allValues = activeData.sharpe_matrix.flat().filter((v): v is number => v !== null);
  const maxAbs = Math.max(Math.abs(Math.min(...allValues, 0)), Math.abs(Math.max(...allValues, 0)));

  return (
    <div className="card fade-in-up" id="sharpe-heatmap-section">
      <div className="card__header">
        <div className="card__title">
          <span className="card__title-icon">🗺️</span>
          Sharpe Ratio Heatmap
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Fast SMA × Slow SMA (averaged across ATR multipliers)
        </span>
      </div>

      {/* Tab group */}
      <div className="tab-group" style={{ marginBottom: '1rem' }}>
        <button
          className={`tab-group__tab ${activeTab === 'global' ? 'tab-group__tab--active' : ''}`}
          onClick={() => setActiveTab('global')}
        >
          Global
        </button>
        {state_names.map((name, i) => (
          <button
            key={i}
            className={`tab-group__tab ${activeTab === String(i) ? 'tab-group__tab--active' : ''}`}
            onClick={() => setActiveTab(String(i))}
            style={{
              borderBottom: activeTab === String(i) ? `2px solid ${colors[i]}` : undefined,
            }}
          >
            {name}
          </button>
        ))}
      </div>

      <Plot
        data={[
          {
            z: activeData.sharpe_matrix,
            x: activeData.slow_sma_values.map(String),
            y: activeData.fast_sma_values.map(String),
            type: 'heatmap',
            colorscale: [
              [0, '#ef4444'],
              [0.35, '#1a1a2e'],
              [0.5, '#0f1520'],
              [0.65, '#1a2744'],
              [1, baseColor],
            ],
            zmin: -maxAbs || -1,
            zmax: maxAbs || 1,
            showscale: true,
            colorbar: {
              title: { text: 'Sharpe', font: { size: 11, color: '#8b95a8' } },
              tickfont: { color: '#8b95a8', size: 10 },
              outlinewidth: 0,
            },
            hovertemplate:
              'Fast SMA: %{y}<br>Slow SMA: %{x}<br>Sharpe: %{z:.4f}<extra></extra>',
            connectgaps: false,
          },
        ]}
        layout={{
          height: 380,
          template: 'plotly_dark',
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { t: 20, r: 80, b: 60, l: 60 },
          xaxis: {
            title: 'Slow SMA Period',
            type: 'category',
            tickfont: { size: 11 },
          },
          yaxis: {
            title: 'Fast SMA Period',
            type: 'category',
            tickfont: { size: 11 },
          },
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}
