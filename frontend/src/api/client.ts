/* ═══════════════════════════════════════════════════════════════════════
   API Client — typed fetch wrapper for the Trading Bot backend.
   ═══════════════════════════════════════════════════════════════════════ */

import type {
  AnalysisStatus,
  AssetsResponse,
  EquityResults,
  HeatmapResults,
  RegimeResults,
  SweepResults,
} from '../types';

const API_BASE = 'http://localhost:8000/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ── Endpoints ─────────────────────────────────────────────────────────

export async function getHealth(): Promise<{ status: string; message: string }> {
  return fetchJSON(`${API_BASE}/health`);
}

export async function getAssets(): Promise<AssetsResponse> {
  return fetchJSON(`${API_BASE}/assets`);
}

export async function startAnalysis(
  ticker: string,
  productionMode = false,
  forceRefresh = false
): Promise<{ status: string; ticker: string }> {
  return fetchJSON(
    `${API_BASE}/analyze?ticker=${encodeURIComponent(ticker)}&production_mode=${productionMode}&force_refresh=${forceRefresh}`,
    { method: 'POST' }
  );
}

export async function getStatus(): Promise<AnalysisStatus> {
  return fetchJSON(`${API_BASE}/status`);
}

export async function getRegimeResults(): Promise<RegimeResults> {
  return fetchJSON(`${API_BASE}/results/regimes`);
}

export async function getSweepResults(): Promise<SweepResults> {
  return fetchJSON(`${API_BASE}/results/sweep`);
}

export async function getEquityResults(): Promise<EquityResults> {
  return fetchJSON(`${API_BASE}/results/equity`);
}

export async function getHeatmapResults(): Promise<HeatmapResults> {
  return fetchJSON(`${API_BASE}/results/heatmap`);
}

// ── Execution Endpoints ───────────────────────────────────────────────

export async function getLiveBalance(marketType = 'spot'): Promise<{ status: string; free_usdt: number; btc_held: number; market_type: string }> {
  return fetchJSON(`${API_BASE}/execution/balance?market_type=${marketType}`);
}

export async function runDailyTick(
  ticker: string,
  marketType = 'spot',
  testnet = false
): Promise<any> {
  return fetchJSON(
    `${API_BASE}/execution/tick?ticker=${encodeURIComponent(ticker)}&market_type=${marketType}&testnet=${testnet}`,
    { method: 'POST' }
  );
}
