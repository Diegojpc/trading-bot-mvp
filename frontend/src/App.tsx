/* ═══════════════════════════════════════════════════════════════════════
   App.tsx — Main dashboard assembling all analysis sections.
   ═══════════════════════════════════════════════════════════════════════ */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getAssets,
  getEquityResults,
  getHeatmapResults,
  getRegimeResults,
  getStatus,
  getSweepResults,
  startAnalysis,
} from './api/client';
import LoadingSpinner from './components/LoadingSpinner';
import Warning from './components/Warning';
import EquityCurves from './sections/EquityCurves';
import ParameterTable from './sections/ParameterTable';
import RegimeTimeline from './sections/RegimeTimeline';
import SharpeHeatmap from './sections/SharpeHeatmap';
import TransitionMatrix from './sections/TransitionMatrix';
import type {
  AnalysisStatus,
  Asset,
  EquityResults,
  HeatmapResults,
  RegimeResults,
  SweepResults,
} from './types';

type AppState = 'idle' | 'running' | 'complete' | 'error' | 'loading_results';

export default function App() {
  // ── State ────────────────────────────────────────────────────────
  const [appState, setAppState] = useState<AppState>('idle');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('QQQ');
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [productionMode, setProductionMode] = useState<boolean>(false);

  // Results
  const [regimeData, setRegimeData] = useState<RegimeResults | null>(null);
  const [sweepData, setSweepData] = useState<SweepResults | null>(null);
  const [equityData, setEquityData] = useState<EquityResults | null>(null);
  const [heatmapData, setHeatmapData] = useState<HeatmapResults | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Load assets on mount ─────────────────────────────────────────
  useEffect(() => {
    getAssets()
      .then((res) => {
        setAssets(res.assets);
        if (res.assets.length > 0) setSelectedTicker(res.assets[0].ticker);
      })
      .catch((err) => {
        console.error('Failed to load assets:', err);
        setError('Cannot connect to backend. Make sure the API is running on port 8000.');
      });

    // Check if there's already a completed analysis
    getStatus()
      .then((s) => {
        if (s.status === 'complete') {
          setAppState('loading_results');
          loadAllResults();
        } else if (s.status === 'running') {
          setAppState('running');
          setStatus(s);
          startPolling();
        }
      })
      .catch(() => {});

    return () => stopPolling();
  }, []);

  // ── Polling ──────────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getStatus();
        setStatus(s);

        if (s.status === 'complete') {
          stopPolling();
          setAppState('loading_results');
          await loadAllResults();
        } else if (s.status === 'error') {
          stopPolling();
          setAppState('error');
          setError(s.error || 'Analysis failed');
        }
      } catch {
        // Backend might be temporarily unavailable
      }
    }, 1500);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // ── Load results ─────────────────────────────────────────────────
  const loadAllResults = async () => {
    try {
      const [regimes, sweep, equity, heatmap] = await Promise.all([
        getRegimeResults(),
        getSweepResults(),
        getEquityResults(),
        getHeatmapResults(),
      ]);

      setRegimeData(regimes);
      setSweepData(sweep);
      setEquityData(equity);
      setHeatmapData(heatmap);
      setAppState('complete');
    } catch (err) {
      console.error('Failed to load results:', err);
      setError('Failed to load analysis results');
      setAppState('error');
    }
  };

  // ── Start analysis ──────────────────────────────────────────────
  const handleAnalyze = async () => {
    setError(null);
    setAppState('running');
    setRegimeData(null);
    setSweepData(null);
    setEquityData(null);
    setHeatmapData(null);

    try {
      await startAnalysis(selectedTicker, productionMode);
      setStatus({ status: 'running', progress: 0, message: 'Starting...', current_asset: selectedTicker, error: null });
      startPolling();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to start analysis';
      setError(message);
      setAppState('error');
    }
  };

  // ── Render ──────────────────────────────────────────────────────
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="app-header__title">
          <h1>🤖 AI Trading Bot</h1>
          <span className="app-header__subtitle">
            HMM Regime Analysis + SMA Parameter Optimization
          </span>
        </div>
        <div className="app-header__controls">
          <select
            id="asset-selector"
            className="select"
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            disabled={appState === 'running'}
          >
            {assets.map((a) => (
              <option key={a.ticker} value={a.ticker}>
                {a.display_name}
              </option>
            ))}
          </select>
          
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={productionMode}
              onChange={(e) => setProductionMode(e.target.checked)}
              disabled={appState === 'running'}
            />
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>100% Data (Production)</span>
          </label>

          <button
            id="analyze-button"
            className="btn btn--primary"
            onClick={handleAnalyze}
            disabled={appState === 'running' || !selectedTicker}
          >
            {appState === 'running' ? '⏳ Running...' : '🚀 Run Analysis'}
          </button>
        </div>
      </header>

      {/* Warning banner — always visible */}
      {regimeData?.production_mode ? (
        <div className="warning-banner fade-in-up" style={{ borderLeftColor: '#3b82f6', background: 'rgba(59, 130, 246, 0.05)', marginBottom: 'var(--space-xl)' }}>
          <div className="warning-banner__title" style={{ color: '#3b82f6' }}>
            🚀 Production Mode (100% Data Training)
          </div>
          <div className="warning-banner__text">
            <p>
              This model was trained on <strong>100% of the historical data</strong>. Out-Of-Sample validation has been intentionally disabled.
              This maximizes the accuracy of the HMM transition matrices and the SMA parameter sweep for deployment in live trading.
            </p>
          </div>
        </div>
      ) : (
        <Warning />
      )}

      {/* Error state */}
      {error && (
        <div
          className="card fade-in-up"
          style={{
            borderColor: 'rgba(239, 68, 68, 0.3)',
            background: 'rgba(239, 68, 68, 0.06)',
            marginBottom: 'var(--space-xl)',
          }}
        >
          <div style={{ color: '#ef4444', fontWeight: 600, marginBottom: '0.5rem' }}>
            ❌ Error
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{error}</div>
          <button
            className="btn btn--sm"
            style={{ marginTop: '1rem' }}
            onClick={() => {
              setError(null);
              setAppState('idle');
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Idle state */}
      {appState === 'idle' && !error && (
        <div className="card fade-in-up" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📉</div>
          <h2 style={{ marginBottom: '0.5rem' }}>Select an Asset and Run Analysis</h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '500px', margin: '0 auto' }}>
            Choose an asset from the dropdown above and click "Run Analysis" to start the
            HMM regime detection and parameter optimization pipeline.
          </p>
        </div>
      )}

      {/* Running state */}
      {appState === 'running' && (
        <LoadingSpinner
          progress={status?.progress ?? 0}
          message={status?.message ?? 'Initializing...'}
        />
      )}

      {/* Loading results state */}
      {appState === 'loading_results' && (
        <LoadingSpinner message="Loading results..." />
      )}

      {/* Complete state — show all sections */}
      {appState === 'complete' && (
        <div className="dashboard-grid">
          {regimeData && <RegimeTimeline data={regimeData} />}

          <div className="dashboard-grid dashboard-grid--two">
            {regimeData && <TransitionMatrix data={regimeData} />}
            {heatmapData && <SharpeHeatmap data={heatmapData} />}
          </div>

          {sweepData && <ParameterTable data={sweepData} />}
          {equityData && <EquityCurves data={equityData} />}
        </div>
      )}
    </div>
  );
}
