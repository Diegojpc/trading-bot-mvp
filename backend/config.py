"""
Application configuration — logging setup, constants, and per-asset strategy configs.
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured logging for the entire backend."""
    logger = logging.getLogger("trading_bot")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s.%(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    return logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# Asset configurations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssetConfig:
    """Per-asset strategy and data configuration."""
    ticker: str
    display_name: str
    asset_type: str                         # "equity" | "crypto"
    allow_short: bool                       # whether to trade short side
    default_fast_sma: list[int] = field(default_factory=lambda: [5, 10, 15, 20])
    default_slow_sma: list[int] = field(default_factory=lambda: [30, 50, 100, 200])
    default_atr_mult: list[float] = field(default_factory=lambda: [1.5, 2.0, 2.5, 3.0])
    slippage_pct: float = 0.001             # 0.1%
    commission_per_trade: float = 1.0       # $1 per round-trip
    years_of_data: int = 10
    rolling_window: int = 20               # window for feature engineering


# Pre-defined asset registry — add more assets here
ASSET_REGISTRY: dict[str, AssetConfig] = {
    "QQQ": AssetConfig(
        ticker="QQQ",
        display_name="NASDAQ 100 (QQQ)",
        asset_type="equity",
        allow_short=False,
    ),
    "BTC-USD": AssetConfig(
        ticker="BTC-USD",
        display_name="Bitcoin (BTC/USD)",
        asset_type="crypto",
        allow_short=True,
    ),
    "SPY": AssetConfig(
        ticker="SPY",
        display_name="S&P 500 (SPY)",
        asset_type="equity",
        allow_short=False,
    ),
    "ETH-USD": AssetConfig(
        ticker="ETH-USD",
        display_name="Ethereum (ETH/USD)",
        asset_type="crypto",
        allow_short=True,
    ),
}

# ---------------------------------------------------------------------------
# HMM defaults
# ---------------------------------------------------------------------------
HMM_MIN_STATES = 2
HMM_MAX_STATES = 5
HMM_N_SEEDS = 10          # random restarts per state count
HMM_COVARIANCE_TYPE = "full"
MIN_TRADES_FILTER = 30    # minimum trades to consider a param combo valid

# ---------------------------------------------------------------------------
# Regime colors — consistent across frontend and backend
# ---------------------------------------------------------------------------
REGIME_COLORS = ["#00d97e", "#3b82f6", "#f59e0b", "#ef4444", "#a855f7"]
REGIME_LABELS_PREFIX = ["Low Vol", "Med-Low Vol", "Medium Vol", "High Vol", "Crisis"]
