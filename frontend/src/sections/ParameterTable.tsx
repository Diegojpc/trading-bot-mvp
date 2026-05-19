/* ═══════════════════════════════════════════════════════════════════════
   ParameterTable — Best parameter combination per regime + global.
   ═══════════════════════════════════════════════════════════════════════ */

import MetricCard from '../components/MetricCard';
import type { SweepResults } from '../types';

interface ParameterTableProps {
  data: SweepResults;
}

export default function ParameterTable({ data }: ParameterTableProps) {
  const { best_global, best_per_regime, state_names, colors } = data;

  // Build rows: global first, then per-regime
  const rows = [
    { label: 'Global (All Regimes)', color: '#e8ecf4', ...best_global },
    ...Object.entries(best_per_regime).map(([id, combo]) => ({
      label: combo.regime_name || state_names[Number(id)] || `Regime ${id}`,
      color: colors[Number(id)] || '#666',
      ...combo,
    })),
  ];

  return (
    <div className="card fade-in-up" id="parameter-table-section">
      <div className="card__header">
        <div className="card__title">
          <span className="card__title-icon">🎯</span>
          Best Parameters
        </div>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {data.total_combinations} combinations tested
        </span>
      </div>

      {/* Global best metrics */}
      <div className="metric-grid" style={{ marginBottom: '1.5rem' }}>
        <MetricCard
          label="Sharpe Ratio"
          value={best_global.sharpe_ratio.toFixed(3)}
          numericValue={best_global.sharpe_ratio}
        />
        <MetricCard
          label="Net Profit"
          value={`$${best_global.net_profit.toLocaleString()}`}
          numericValue={best_global.net_profit}
        />
        <MetricCard
          label="Max Drawdown"
          value={`${best_global.max_drawdown.toFixed(1)}%`}
          colorMode="negative"
        />
        <MetricCard
          label="Profit Factor"
          value={best_global.profit_factor === Infinity ? '∞' : best_global.profit_factor.toFixed(2)}
          numericValue={best_global.profit_factor - 1}
        />
        <MetricCard
          label="Win Rate"
          value={`${best_global.win_rate.toFixed(1)}%`}
          numericValue={best_global.win_rate - 50}
        />
        <MetricCard
          label="Total Trades"
          value={best_global.n_trades}
          colorMode="neutral"
        />
      </div>

      {/* Full table */}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Regime</th>
              <th>Fast SMA</th>
              <th>Slow SMA</th>
              <th>ATR Mult</th>
              <th>Sharpe</th>
              <th>Net Profit</th>
              <th>Max DD</th>
              <th>Profit Factor</th>
              <th>Win Rate</th>
              <th>Trades</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>
                  <span
                    className="regime-badge"
                    style={{
                      backgroundColor: `${row.color}20`,
                      color: row.color,
                      border: `1px solid ${row.color}40`,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: '50%',
                        background: row.color,
                        display: 'inline-block',
                      }}
                    />
                    {row.label}
                  </span>
                </td>
                <td>{row.fast_sma}</td>
                <td>{row.slow_sma}</td>
                <td>{row.atr_mult}</td>
                <td style={{ color: row.sharpe_ratio > 0 ? '#00d97e' : '#ef4444' }}>
                  {row.sharpe_ratio.toFixed(3)}
                </td>
                <td style={{ color: row.net_profit > 0 ? '#00d97e' : '#ef4444' }}>
                  ${row.net_profit.toLocaleString()}
                </td>
                <td style={{ color: '#ef4444' }}>{row.max_drawdown.toFixed(1)}%</td>
                <td>
                  {row.profit_factor === Infinity ? '∞' : row.profit_factor.toFixed(2)}
                </td>
                <td>{row.win_rate.toFixed(1)}%</td>
                <td>{row.n_trades}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
