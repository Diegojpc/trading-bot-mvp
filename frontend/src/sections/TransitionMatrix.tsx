/* ═══════════════════════════════════════════════════════════════════════
   TransitionMatrix — HMM state transition probability heatmap.
   ═══════════════════════════════════════════════════════════════════════ */

import Plot from '../components/Plot';
import type { RegimeResults } from '../types';

interface TransitionMatrixProps {
  data: RegimeResults;
}

export default function TransitionMatrix({ data }: TransitionMatrixProps) {
  const { transition_matrix, state_names, colors } = data;

  // Build annotation text
  const annotations: Partial<Plotly.Annotations>[] = [];
  for (let i = 0; i < transition_matrix.length; i++) {
    for (let j = 0; j < transition_matrix[i].length; j++) {
      const val = transition_matrix[i][j];
      annotations.push({
        x: j,
        y: i,
        text: `${(val * 100).toFixed(1)}%`,
        showarrow: false,
        font: {
          color: val > 0.5 ? '#0a0e17' : '#e8ecf4',
          size: 13,
          family: 'JetBrains Mono',
        },
      });
    }
  }

  return (
    <div className="card fade-in-up" id="transition-matrix-section">
      <div className="card__header">
        <div className="card__title">
          <span className="card__title-icon">🔄</span>
          Transition Matrix
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Probability of transitioning between regimes
        </span>
      </div>

      <Plot
        data={[
          {
            z: transition_matrix,
            x: state_names,
            y: state_names,
            type: 'heatmap',
            colorscale: [
              [0, '#0f1520'],
              [0.25, '#1a2744'],
              [0.5, '#2d4a8a'],
              [0.75, '#3b82f6'],
              [1, '#93c5fd'],
            ],
            showscale: true,
            colorbar: {
              title: { text: 'Probability', font: { size: 11, color: '#8b95a8' } },
              tickfont: { color: '#8b95a8', size: 10 },
              outlinewidth: 0,
            },
            hovertemplate:
              'From: %{y}<br>To: %{x}<br>Probability: %{z:.3f}<extra></extra>',
          },
        ]}
        layout={{
          height: 380,
          template: 'plotly_dark',
          paper_bgcolor: 'transparent',
          plot_bgcolor: 'transparent',
          margin: { t: 20, r: 80, b: 60, l: 100 },
          xaxis: {
            title: 'To State',
            side: 'bottom',
            tickfont: { size: 11 },
          },
          yaxis: {
            title: 'From State',
            autorange: 'reversed',
            tickfont: { size: 11 },
          },
          annotations,
        }}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%' }}
        useResizeHandler
      />
    </div>
  );
}
