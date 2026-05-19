/* ═══════════════════════════════════════════════════════════════════════
   TypeScript interfaces for the Trading Bot API responses.
   ═══════════════════════════════════════════════════════════════════════ */

// ── API Status ────────────────────────────────────────────────────────
export interface AnalysisStatus {
  status: 'idle' | 'running' | 'complete' | 'error';
  progress: number;
  message: string;
  current_asset: string | null;
  error: string | null;
}

// ── Assets ────────────────────────────────────────────────────────────
export interface Asset {
  ticker: string;
  display_name: string;
  asset_type: 'equity' | 'crypto';
  allow_short: boolean;
}

export interface AssetsResponse {
  assets: Asset[];
}

// ── Regime Results ────────────────────────────────────────────────────
export interface TimeSeriesData {
  dates: string[];
  values: (number | null)[];
}

export interface RegimeTimeline {
  dates: string[];
  labels: number[];
}

export interface RegimeResults {
  n_states: number;
  state_names: string[];
  colors: string[];
  timeline: RegimeTimeline;
  distribution: Record<string, number>;
  transition_matrix: number[][];
  bic_scores: Record<string, number>;
  state_volatilities: number[];
  price_data: TimeSeriesData;
  split_date: string;
}

// ── Sweep Results ─────────────────────────────────────────────────────
export interface BestCombo {
  fast_sma: number;
  slow_sma: number;
  atr_mult: number;
  combo_key: string;
  sharpe_ratio: number;
  net_profit: number;
  max_drawdown: number;
  profit_factor: number;
  win_rate: number;
  n_trades: number;
  regime_id?: number;
  regime_name?: string;
  oos_sharpe_ratio: number | null;
  oos_net_profit: number | null;
  oos_max_drawdown?: number | null;
}

export interface SweepResults {
  best_global: BestCombo;
  best_per_regime: Record<string, BestCombo>;
  state_names: string[];
  colors: string[];
  total_combinations: number;
}

// ── Equity Curves ─────────────────────────────────────────────────────
export interface EquityResults {
  equity_curves: Record<string, TimeSeriesData>;
  price_data: TimeSeriesData;
  regime_bar: RegimeTimeline;
  state_names: string[];
  colors: string[];
  split_date: string;
}

// ── Heatmap ───────────────────────────────────────────────────────────
export interface HeatmapMatrix {
  fast_sma_values: number[];
  slow_sma_values: number[];
  sharpe_matrix: (number | null)[][];
}

export interface HeatmapResults {
  heatmap: {
    global: HeatmapMatrix;
    regimes: Record<string, HeatmapMatrix>;
  };
  state_names: string[];
  colors: string[];
}
