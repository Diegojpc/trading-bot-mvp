"""
Feature engineering for HMM regime detection.

Computes rolling volatility, cumulative returns, and momentum from OHLCV data.
All features are standardized before being fed to the HMM.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("trading_bot")


def compute_hmm_features(
    df: pd.DataFrame,
    window: int = 20,
) -> tuple[np.ndarray, pd.DatetimeIndex]:
    """
    Build the feature matrix for HMM training.

    Features (all rolling, window=20 by default):
      1. Rolling volatility — std of log returns
      2. Rolling cumulative return — sum of log returns
      3. Momentum — pct_change over the window

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV data with DatetimeIndex and 'Close' column.
    window : int
        Rolling window size in days.

    Returns
    -------
    features : np.ndarray
        Scaled feature matrix, shape (n_valid_rows, 3).
    valid_dates : pd.DatetimeIndex
        The dates corresponding to each row of the feature matrix.
    """
    logger.info(
        "compute_hmm_features — input shape: %s, window: %d",
        df.shape, window,
    )

    close = df["Close"].astype(float)

    # Log returns
    log_returns = np.log(close / close.shift(1))

    # Feature 1: Rolling volatility (std of log returns)
    rolling_vol = log_returns.rolling(window=window).std()

    # Feature 2: Rolling cumulative log return
    rolling_cum_ret = log_returns.rolling(window=window).sum()

    # Feature 3: Momentum (percentage change over the window)
    momentum = close.pct_change(periods=window)

    # Combine into a DataFrame
    features_df = pd.DataFrame(
        {
            "volatility": rolling_vol,
            "cum_return": rolling_cum_ret,
            "momentum": momentum,
        },
        index=df.index,
    )

    # Drop NaN rows from rolling window warmup
    valid_mask = features_df.notna().all(axis=1)
    features_clean = features_df[valid_mask]
    valid_dates = features_clean.index

    dropped = len(features_df) - len(features_clean)
    logger.info(
        "Features computed — %d valid rows, %d dropped (NaN from rolling warmup)",
        len(features_clean), dropped,
    )

    if len(features_clean) < 100:
        logger.error("Only %d valid feature rows — too few for HMM training", len(features_clean))
        raise ValueError(
            f"Insufficient data after feature computation: {len(features_clean)} rows"
        )

    # Standardize
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features_clean.values)

    logger.debug(
        "Feature stats after scaling — means: %s, stds: %s",
        np.round(features_scaled.mean(axis=0), 4),
        np.round(features_scaled.std(axis=0), 4),
    )

    return features_scaled, valid_dates
