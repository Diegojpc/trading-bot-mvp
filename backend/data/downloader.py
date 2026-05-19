"""
Data acquisition — download OHLCV from yfinance with local parquet caching.
"""

import logging
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from backend.config import CACHE_DIR, AssetConfig

logger = logging.getLogger("trading_bot")


def _cache_path(ticker: str) -> str:
    """Return the parquet cache file path for a given ticker."""
    safe_name = ticker.replace("^", "").replace("=", "").replace("-", "_")
    return str(CACHE_DIR / f"{safe_name}_daily.parquet")


def download_ohlcv(
    asset_config: AssetConfig,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Download daily OHLCV data for the configured asset.

    Caches to local parquet. Returns a clean DataFrame indexed by Date with
    columns: Open, High, Low, Close, Volume.

    Parameters
    ----------
    asset_config : AssetConfig
        The asset to download.
    force_refresh : bool
        If True, re-download even if cache exists.

    Returns
    -------
    pd.DataFrame
        OHLCV data with DatetimeIndex.

    Raises
    ------
    ValueError
        If the downloaded data is empty or too short.
    """
    ticker = asset_config.ticker
    cache_file = _cache_path(ticker)
    logger.info("download_ohlcv called — ticker=%s, force_refresh=%s", ticker, force_refresh)

    # ── Try cache first ──────────────────────────────────────────────────
    if not force_refresh:
        try:
            df = pd.read_parquet(cache_file)
            if len(df) > 100:
                last_date = df.index.max()
                # Check if cache is reasonably fresh (last date is within 2 days)
                if (datetime.now() - last_date).days <= 2:
                    logger.info(
                        "Cache hit for %s — %d rows, %s to %s",
                        ticker, len(df),
                        df.index.min().strftime("%Y-%m-%d"),
                        df.index.max().strftime("%Y-%m-%d"),
                    )
                    return df
                else:
                    logger.info("Cache for %s is stale (last date: %s). Re-downloading.", ticker, last_date.strftime("%Y-%m-%d"))
        except FileNotFoundError:
            logger.debug("No cache found for %s, will download.", ticker)
        except Exception as exc:
            logger.warning("Cache read failed for %s: %s — re-downloading.", ticker, exc)

    # ── Download from yfinance ───────────────────────────────────────────
    # yfinance end date is exclusive, so add 1 day to capture today's data
    end_date = datetime.now() + timedelta(days=1)
    start_date = end_date - timedelta(days=asset_config.years_of_data * 365)

    logger.info(
        "Downloading %s from %s to %s via yfinance...",
        ticker,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
    )

    try:
        raw = yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
    except Exception as exc:
        logger.error("yfinance download failed for %s: %s", ticker, exc, exc_info=True)
        raise ValueError(f"Failed to download data for {ticker}: {exc}") from exc

    if raw is None or raw.empty:
        logger.error("Empty data returned for %s", ticker)
        raise ValueError(f"No data available for ticker '{ticker}'. Check the symbol.")

    # ── Clean the DataFrame ──────────────────────────────────────────────
    # yfinance may return MultiIndex columns for single ticker — flatten
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.droplevel("Ticker")

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index.name = "Date"
    df = df.sort_index()

    # Drop any fully-NaN rows
    before_len = len(df)
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    dropped = before_len - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with NaN OHLC values for %s", dropped, ticker)

    # Validate minimum data
    min_rows = 252  # at least ~1 year of daily data
    if len(df) < min_rows:
        logger.error("Only %d rows for %s — need at least %d", len(df), ticker, min_rows)
        raise ValueError(
            f"Insufficient data for {ticker}: {len(df)} rows (minimum {min_rows})"
        )

    # Check for large gaps
    date_diffs = df.index.to_series().diff().dt.days
    max_gap = date_diffs.max()
    if max_gap and max_gap > 10:
        logger.warning(
            "Large gap detected in %s data: %d calendar days. "
            "This may affect analysis quality.",
            ticker, max_gap,
        )

    # ── Cache to parquet ─────────────────────────────────────────────────
    try:
        df.to_parquet(cache_file, engine="pyarrow")
        logger.info("Cached %d rows to %s", len(df), cache_file)
    except Exception as exc:
        logger.warning("Failed to cache data: %s", exc)

    logger.info(
        "Download complete — %s: %d rows, %s to %s",
        ticker, len(df),
        df.index.min().strftime("%Y-%m-%d"),
        df.index.max().strftime("%Y-%m-%d"),
    )
    return df
