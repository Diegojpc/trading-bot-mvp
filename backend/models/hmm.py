"""
HMM regime detection — GaussianHMM training with BIC-based model selection.

Trains multiple HMMs (2–5 states), selects the best by BIC, sorts states by
ascending volatility, and produces regime labels + transition matrix.
"""

import logging
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

from backend.config import (
    HMM_COVARIANCE_TYPE,
    HMM_MAX_STATES,
    HMM_MIN_STATES,
    HMM_N_SEEDS,
    REGIME_LABELS_PREFIX,
)

logger = logging.getLogger("trading_bot")

# Suppress hmmlearn convergence warnings during model selection
warnings.filterwarnings("ignore", category=UserWarning, module="hmmlearn")


@dataclass
class HMMResult:
    """Container for HMM training results."""
    n_states: int
    regime_labels: np.ndarray          # shape (n_dates,), integer labels 0..n_states-1
    valid_dates: pd.DatetimeIndex      # dates aligned with regime_labels
    transition_matrix: np.ndarray      # shape (n_states, n_states)
    state_means: np.ndarray            # shape (n_states, n_features)
    state_volatilities: np.ndarray     # mean volatility per state
    state_names: list[str]             # human-readable state names
    bic_scores: dict[int, float]       # {n_states: bic_score}
    regime_distribution: dict[str, float]  # {state_name: fraction}


def _count_free_params(n_components: int, n_features: int, cov_type: str) -> int:
    """
    Count free parameters for a GaussianHMM model.

    Parameters for 'full' covariance:
        means:       n_components * n_features
        covariances: n_components * n_features * (n_features + 1) / 2
        transitions: n_components * (n_components - 1)
        start_probs: n_components - 1
    """
    k = n_components
    f = n_features

    n_mean_params = k * f

    if cov_type == "full":
        n_cov_params = k * f * (f + 1) // 2
    elif cov_type == "diag":
        n_cov_params = k * f
    elif cov_type == "spherical":
        n_cov_params = k
    elif cov_type == "tied":
        n_cov_params = f * (f + 1) // 2
    else:
        n_cov_params = k * f  # fallback to diag

    n_trans_params = k * (k - 1)
    n_start_params = k - 1

    total = n_mean_params + n_cov_params + n_trans_params + n_start_params
    return total


def _calculate_bic(model: GaussianHMM, X: np.ndarray) -> float:
    """
    Compute BIC for a fitted HMM.

    BIC = ln(n) * k - 2 * ln(L)

    where n = n_samples, k = free params, L = likelihood.
    """
    n_samples = X.shape[0]
    n_features = X.shape[1]
    k = _count_free_params(model.n_components, n_features, model.covariance_type)
    log_likelihood = model.score(X)  # total log-likelihood

    bic = np.log(n_samples) * k - 2 * log_likelihood
    return bic


def _fit_hmm_with_restarts(
    X: np.ndarray,
    n_components: int,
    n_seeds: int,
    cov_type: str,
) -> tuple[GaussianHMM | None, float]:
    """
    Fit GaussianHMM with multiple random restarts, return best model by log-likelihood.
    """
    best_model = None
    best_score = -np.inf

    for seed in range(n_seeds):
        try:
            model = GaussianHMM(
                n_components=n_components,
                covariance_type=cov_type,
                n_iter=200,
                random_state=seed * 42,
                tol=1e-4,
            )
            model.fit(X)
            score = model.score(X)

            if score > best_score:
                best_score = score
                best_model = model

        except Exception as exc:
            logger.debug(
                "HMM fit failed — n_components=%d, seed=%d: %s",
                n_components, seed, exc,
            )
            continue

    return best_model, best_score


def train_hmm(
    features: np.ndarray,
    valid_dates: pd.DatetimeIndex,
) -> HMMResult:
    """
    Train HMMs with 2–5 states, select best by BIC, sort by volatility.

    Parameters
    ----------
    features : np.ndarray
        Scaled feature matrix, shape (n_samples, n_features).
    valid_dates : pd.DatetimeIndex
        Dates aligned with the feature matrix.

    Returns
    -------
    HMMResult
        Complete regime detection results.
    """
    logger.info(
        "train_hmm — fitting HMMs with %d to %d states, %d seeds each",
        HMM_MIN_STATES, HMM_MAX_STATES, HMM_N_SEEDS,
    )

    bic_scores: dict[int, float] = {}
    models: dict[int, GaussianHMM] = {}

    for n_states in range(HMM_MIN_STATES, HMM_MAX_STATES + 1):
        model, score = _fit_hmm_with_restarts(
            features, n_states, HMM_N_SEEDS, HMM_COVARIANCE_TYPE,
        )
        if model is not None:
            bic = _calculate_bic(model, features)
            bic_scores[n_states] = bic
            models[n_states] = model
            logger.info(
                "  n_states=%d — log_likelihood=%.2f, BIC=%.2f",
                n_states, score, bic,
            )
        else:
            logger.warning("  n_states=%d — all seeds failed to converge", n_states)

    if not models:
        raise RuntimeError("All HMM fits failed. Check your data quality.")

    # Select best by lowest BIC
    best_n = min(bic_scores, key=bic_scores.get)  # type: ignore[arg-type]
    best_model = models[best_n]
    logger.info("Best model: %d states (BIC=%.2f)", best_n, bic_scores[best_n])

    # ── Predict regimes ──────────────────────────────────────────────────
    raw_labels = best_model.predict(features)

    # ── Sort states by ascending volatility ──────────────────────────────
    # The volatility feature is column 0 (before scaling, but the relative
    # ordering is preserved after scaling since it's a monotonic transform)
    state_mean_vols = np.array([
        features[raw_labels == s, 0].mean() for s in range(best_n)
    ])
    sort_order = np.argsort(state_mean_vols)  # ascending volatility

    # Create remapping: old_state -> new_state
    remap = np.zeros(best_n, dtype=int)
    for new_idx, old_idx in enumerate(sort_order):
        remap[old_idx] = new_idx

    # Apply remapping
    sorted_labels = remap[raw_labels]

    # Reorder transition matrix
    raw_transmat = best_model.transmat_
    sorted_transmat = raw_transmat[sort_order][:, sort_order]

    # Reorder means
    sorted_means = best_model.means_[sort_order]
    sorted_vols = state_mean_vols[sort_order]

    # State names
    state_names = REGIME_LABELS_PREFIX[:best_n]

    # Regime distribution
    unique, counts = np.unique(sorted_labels, return_counts=True)
    total = counts.sum()
    regime_dist = {
        state_names[int(s)]: float(counts[i] / total)
        for i, s in enumerate(unique)
    }

    logger.info("Regime distribution: %s", regime_dist)
    logger.info(
        "Transition matrix:\n%s",
        np.array2string(sorted_transmat, precision=3, suppress_small=True),
    )

    return HMMResult(
        n_states=best_n,
        regime_labels=sorted_labels,
        valid_dates=valid_dates,
        transition_matrix=sorted_transmat,
        state_means=sorted_means,
        state_volatilities=sorted_vols,
        state_names=state_names,
        bic_scores=bic_scores,
        regime_distribution=regime_dist,
    )
