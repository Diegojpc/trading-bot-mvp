/* ═══════════════════════════════════════════════════════════════════════
   LivePortfolio.tsx — Real-time portfolio snapshot with P&L and trade log.
   ═══════════════════════════════════════════════════════════════════════ */

import { useCallback, useEffect, useState } from 'react';
import { getPortfolioSummary } from '../api/client';
import type { PortfolioSummary } from '../types';

interface Props {
  refreshTrigger?: number; // increment to force a refresh from the parent
}

export default function LivePortfolio({ refreshTrigger }: Props) {
  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const summary = await getPortfolioSummary('spot');
      setData(summary);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err.message || 'Failed to load portfolio');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on mount and when a tick completes
  useEffect(() => { refresh(); }, [refresh, refreshTrigger]);

  const pnl = data?.performance.unrealized_pnl_usd ?? null;
  const pnlPct = data?.performance.unrealized_pnl_pct ?? null;
  const pnlColor = pnl === null ? 'var(--text-secondary)' : pnl >= 0 ? '#00d97e' : '#ef4444';
  const pnlSign = pnl !== null && pnl >= 0 ? '+' : '';

  const lastUpdatedStr = lastUpdated
    ? lastUpdated.toLocaleTimeString('es-CO', { timeZone: 'America/Bogota', hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <div className="card fade-in-up" style={{ marginBottom: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>📊 Live Portfolio</h3>
          {lastUpdatedStr && (
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
              Updated at {lastUpdatedStr} (Colombia)
            </div>
          )}
        </div>
        <button
          className="btn btn--sm"
          onClick={refresh}
          disabled={loading}
          style={{ fontSize: '0.75rem', minWidth: '80px' }}
        >
          {loading ? '⏳ ...' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ color: '#ef4444', fontSize: '0.85rem', marginBottom: '1rem' }}>
          ❌ {error}
        </div>
      )}

      {data && (
        <>
          {/* Metrics grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.75rem',
            marginBottom: '1.5rem',
          }}>
            <Metric
              label="Total Value"
              value={`$${data.balances.total_usd.toFixed(2)}`}
              color="#ffffff"
            />
            <Metric
              label="BTC Held"
              value={data.balances.btc.toFixed(8)}
              sub={`≈ $${data.balances.btc_value_usd.toFixed(2)}`}
              color="#f7931a"
            />
            <Metric
              label="Free USDT"
              value={`$${data.balances.usdt.toFixed(4)}`}
              color="#00d97e"
            />
            <Metric
              label="BTC Price"
              value={`$${data.market.btc_price.toLocaleString('en-US')}`}
              color="#3b82f6"
            />
            {data.performance.avg_entry_price !== null && (
              <Metric
                label="Avg Entry Price"
                value={`$${data.performance.avg_entry_price.toLocaleString('en-US')}`}
                color="var(--text-primary)"
              />
            )}
            {pnl !== null && (
              <Metric
                label="Unrealized P&L"
                value={`${pnlSign}$${pnl.toFixed(4)}`}
                sub={pnlPct !== null ? `${pnlSign}${pnlPct.toFixed(2)}%` : undefined}
                color={pnlColor}
              />
            )}
            <Metric
              label="Total Invested"
              value={`$${data.performance.total_invested_usd.toFixed(4)}`}
              color="var(--text-secondary)"
            />
            <Metric
              label="Trades"
              value={`${data.performance.total_buys}B / ${data.performance.total_sells}S`}
              sub="Buys / Sells"
              color="var(--text-secondary)"
            />
          </div>

          {/* Trade history table */}
          {data.recent_trades.length > 0 ? (
            <>
              <div style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: '0.6rem',
              }}>
                Trade History (newest first)
              </div>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
                      {['Date & Time (COL)', 'Side', 'BTC Amount', 'Price (USDT)', 'Total (USDT)', 'Fee'].map(h => (
                        <th key={h} style={{
                          textAlign: 'left',
                          padding: '0.4rem 0.75rem',
                          color: 'var(--text-secondary)',
                          fontWeight: 500,
                          whiteSpace: 'nowrap',
                        }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_trades.map((t) => {
                      const dt = new Date(t.datetime);
                      const col = dt.toLocaleString('es-CO', {
                        timeZone: 'America/Bogota',
                        year: 'numeric', month: '2-digit', day: '2-digit',
                        hour: '2-digit', minute: '2-digit',
                      });
                      const isBuy = t.side === 'buy';
                      return (
                        <tr key={t.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                          <td style={{ padding: '0.45rem 0.75rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{col}</td>
                          <td style={{ padding: '0.45rem 0.75rem' }}>
                            <span style={{
                              color: isBuy ? '#00d97e' : '#ef4444',
                              fontWeight: 700,
                              fontSize: '0.72rem',
                              textTransform: 'uppercase',
                              background: isBuy ? 'rgba(0,217,126,0.1)' : 'rgba(239,68,68,0.1)',
                              padding: '0.1rem 0.4rem',
                              borderRadius: '0.25rem',
                            }}>
                              {t.side}
                            </span>
                          </td>
                          <td style={{ padding: '0.45rem 0.75rem', fontFamily: 'monospace' }}>{t.amount.toFixed(8)}</td>
                          <td style={{ padding: '0.45rem 0.75rem' }}>${t.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                          <td style={{ padding: '0.45rem 0.75rem', fontWeight: 600 }}>{t.cost.toFixed(4)}</td>
                          <td style={{ padding: '0.45rem 0.75rem', color: 'var(--text-secondary)', fontFamily: 'monospace', fontSize: '0.72rem' }}>
                            {t.fee_amount.toFixed(8)} {t.fee_currency}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textAlign: 'center', padding: '1rem' }}>
              No bot trades found yet. Run the daily tick to place your first order.
            </div>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Loading portfolio...</div>
      )}
    </div>
  );
}

function Metric({
  label, value, sub, color,
}: {
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.05)',
      borderRadius: '0.5rem',
      padding: '0.75rem 1rem',
    }}>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', marginBottom: '0.3rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
      <div style={{ fontSize: '1rem', fontWeight: 700, color, lineHeight: 1.2 }}>{value}</div>
      {sub && <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>{sub}</div>}
    </div>
  );
}
