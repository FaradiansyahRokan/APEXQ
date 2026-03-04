"""
╔══════════════════════════════════════════════════════════════════════╗
║        APEX QUANT FUND — Phase 3: Portfolio-Level Institutional     ║
║  Mean-Variance · Risk Parity · CVaR Optimization · Kelly Matrix     ║
╚══════════════════════════════════════════════════════════════════════╝

Architecture:
  - Multi-asset allocation (not single-ticker signals)
  - Factor-based diversification
  - Regime-conditional portfolio construction
  - Capacity/liquidity modeling
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import minimize, LinearConstraint, Bounds
from scipy.stats import norm
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
#  SECTION 1 — PORTFOLIO STATISTICS
# ══════════════════════════════════════════════════════════════════

def compute_portfolio_moments(
    returns_matrix : np.ndarray,   # shape (T, N): T observations, N assets
    expected_returns: Optional[np.ndarray] = None,
) -> Dict:
    """
    Compute annualized portfolio statistics: mu, covariance, correlation.

    Uses Ledoit-Wolf shrinkage for covariance estimation to reduce
    in-sample overfitting (Ledoit & Wolf 2004).

    Args:
        returns_matrix   : Daily log returns, shape (T, N)
        expected_returns : Optional override for forward-looking mu
    """
    T, N = returns_matrix.shape
    mu   = expected_returns if expected_returns is not None else returns_matrix.mean(axis=0) * 252

    # Sample covariance
    Sigma_raw = np.cov(returns_matrix.T) * 252

    # Ledoit-Wolf analytical shrinkage (Oracle Approximating Shrinkage - LW 2004)
    # Target: scaled identity matrix (F = mu_hat * I)
    trace_S  = np.trace(Sigma_raw)
    mu_hat   = trace_S / N

    # Estimate optimal shrinkage intensity via sample covariance matrix moments
    # rho* = min(sum_pi / sum_c, 1) where:
    #   sum_pi = sum of asymptotic variances of sample covariance entries
    #   sum_c  = sum of squared deviations from shrinkage target
    X_centered = (returns_matrix - returns_matrix.mean(axis=0)) * np.sqrt(252)
    sum_pi = 0.0
    for t_idx in range(T):
        x_t = X_centered[t_idx:t_idx+1, :]
        sum_pi += np.sum((x_t.T @ x_t - Sigma_raw) ** 2)
    sum_pi /= (T ** 2)

    Target   = mu_hat * np.eye(N)
    sum_c    = np.sum((Sigma_raw - Target) ** 2)
    rho      = min(max(sum_pi / max(sum_c, 1e-12), 0.0), 1.0)

    Sigma_lw = (1 - rho) * Sigma_raw + rho * Target  # Ledoit-Wolf shrunk covariance

    corr_matrix = Sigma_lw / np.sqrt(np.outer(np.diag(Sigma_lw), np.diag(Sigma_lw)))

    return {
        "mu_ann"         : mu,
        "cov_matrix"     : Sigma_lw,
        "corr_matrix"    : corr_matrix,
        "shrinkage_rho"  : round(rho, 4),
        "n_assets"       : N,
        "n_observations" : T,
        "vol_ann"        : np.sqrt(np.diag(Sigma_lw)),
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 2 — MEAN-VARIANCE OPTIMIZATION
# ══════════════════════════════════════════════════════════════════

def mean_variance_optimization(
    mu     : np.ndarray,       # Expected returns, annualized
    Sigma  : np.ndarray,       # Covariance matrix, annualized
    target_return    : Optional[float] = None,   # If None → maximize Sharpe
    long_only        : bool   = True,
    max_weight       : float  = 0.40,
    min_weight       : float  = 0.00,
    risk_free_rate   : float  = 0.04,
) -> Dict:
    """
    Mean-Variance Optimization (Markowitz 1952).

    Solves one of:
      1. Maximize Sharpe (default): max (w'μ - rf) / √(w'Σw)
      2. Minimize variance at target return: min w'Σw s.t. w'μ = target

    Constraints:
      - Sum of weights = 1
      - Long-only (w ≥ 0) if long_only=True
      - Max single-asset weight ≤ max_weight

    Statistical note:
      MVO is highly sensitive to mu estimation error. Use with
      Black-Litterman or robust estimation. Raw historical mu
      should be used cautiously — noise dominates for N > 10.
    """
    N = len(mu)
    w0 = np.ones(N) / N

    def sharpe_neg(w):
        port_ret = w @ mu
        port_vol = np.sqrt(w @ Sigma @ w)
        return -((port_ret - risk_free_rate) / max(port_vol, 1e-10))

    def min_var(w):
        return float(w @ Sigma @ w)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    if target_return is not None:
        constraints.append({"type": "eq", "fun": lambda w: w @ mu - target_return})

    lb = min_weight if long_only else -max_weight
    bounds = Bounds(lb=lb, ub=max_weight)

    obj = min_var if target_return is not None else sharpe_neg

    result = minimize(
        obj, w0, method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000}
    )

    if not result.success:
        # Fallback to equal weight
        w_opt = np.ones(N) / N
    else:
        w_opt = result.x.copy()
        if long_only:
            w_opt = np.maximum(w_opt, 0.0)  # enforce non-negative for long-only
        w_opt /= w_opt.sum() if w_opt.sum() != 0 else 1.0

    port_ret = float(w_opt @ mu)
    port_vol = float(np.sqrt(w_opt @ Sigma @ w_opt))
    sharpe   = (port_ret - risk_free_rate) / max(port_vol, 1e-10)

    return {
        "weights"         : w_opt.round(6).tolist(),
        "portfolio_return": round(port_ret * 100, 4),
        "portfolio_vol"   : round(port_vol * 100, 4),
        "sharpe_ratio"    : round(sharpe, 4),
        "optimization"    : "min_variance" if target_return else "max_sharpe",
        "converged"       : result.success,
        "max_weight"      : round(float(w_opt.max()), 4),
        "min_weight"      : round(float(w_opt[w_opt > 1e-4].min()) if (w_opt > 1e-4).any() else 0, 4),
        "herfindahl_idx"  : round(float(np.sum(w_opt**2)), 4),  # concentration measure
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 3 — RISK PARITY
# ══════════════════════════════════════════════════════════════════

def risk_parity_weights(
    Sigma          : np.ndarray,
    budget         : Optional[np.ndarray] = None,  # target risk budgets (equal if None)
    max_iter       : int   = 1000,
    tol            : float = 1e-8,
) -> Dict:
    """
    Risk Parity (Equal Risk Contribution) portfolio.

    Risk parity targets equal marginal contribution to portfolio variance
    from each asset, rather than equal dollar weights.

    Risk Contribution of asset i:
        RC_i = w_i × (Σw)_i / (w'Σw)

    Objective: min Σ_i Σ_j (RC_i - RC_j)²
    Alternatively: w_i × (Σw)_i = budget_i × w'Σw (Maillard et al. 2010)

    Statistical advantage over MVO:
      - No expected return estimation required
      - More stable out-of-sample
      - Less concentrated portfolios
    """
    N = Sigma.shape[0]
    if budget is None:
        budget = np.ones(N) / N  # equal risk budget

    budget = np.asarray(budget, dtype=float)
    budget /= budget.sum()

    def _risk_contributions(w):
        port_var  = float(w @ Sigma @ w)
        mrc       = Sigma @ w  # marginal risk contribution
        rc        = w * mrc / max(port_var, 1e-12)
        return rc

    def objective(log_w):
        w  = np.exp(log_w)
        w /= w.sum()
        rc = _risk_contributions(w)
        diff = rc - budget
        return float(np.sum(diff**2))

    # Initialize with equal weights in log space
    log_w0 = np.zeros(N)
    result = minimize(objective, log_w0, method="L-BFGS-B", tol=tol,
                      options={"maxiter": max_iter})

    w_opt = np.exp(result.x)
    w_opt /= w_opt.sum()

    rc_final  = _risk_contributions(w_opt)
    port_vol  = float(np.sqrt(w_opt @ Sigma @ w_opt))

    return {
        "weights"          : w_opt.round(6).tolist(),
        "risk_contributions": rc_final.round(6).tolist(),
        "target_budget"    : budget.round(6).tolist(),
        "rc_deviation"     : round(float(np.max(np.abs(rc_final - budget))), 6),
        "portfolio_vol_ann": round(port_vol * 100, 4),
        "max_weight"       : round(float(w_opt.max()), 4),
        "converged"        : result.success,
        "herfindahl_idx"   : round(float(np.sum(w_opt**2)), 4),
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 4 — CVAR PORTFOLIO OPTIMIZATION
# ══════════════════════════════════════════════════════════════════

def cvar_optimization(
    returns_matrix  : np.ndarray,   # (T, N) historical returns
    confidence      : float = 0.95,
    risk_free_rate  : float = 0.04,
    max_weight      : float = 0.40,
    min_weight      : float = 0.00,
) -> Dict:
    """
    CVaR (Conditional Value-at-Risk) portfolio optimization.

    Minimizes Expected Shortfall (CVaR) subject to weight constraints.
    Superior to MVO for fat-tailed return distributions because it
    directly optimizes the tail risk — not just variance.

    Linear programming formulation (Rockafellar-Uryasev 2000):
      min CVaR = VaR + (1/(T(1-α))) × Σ max(z_t - w'r_t - VaR, 0)

    This is a convex optimization: minimize mean CVaR across scenarios.
    """
    T, N  = returns_matrix.shape
    alpha = 1 - confidence

    def cvar_portfolio(w):
        port_returns = returns_matrix @ w
        var_lvl      = float(np.percentile(port_returns, alpha * 100))
        tail         = port_returns[port_returns <= var_lvl]
        cvar         = float(-tail.mean()) if len(tail) > 0 else 0.0
        return cvar

    w0 = np.ones(N) / N
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    bounds      = Bounds(lb=min_weight, ub=max_weight)

    result = minimize(
        cvar_portfolio, w0, method="SLSQP",
        bounds=bounds, constraints=constraints,
        options={"ftol": 1e-10, "maxiter": 2000}
    )

    w_opt = result.x if result.success else w0
    # Do NOT take abs() — preserve optimizer solution. For long-only, bounds handle it.
    w_opt = w_opt.copy()
    w_sum = w_opt.sum()
    if w_sum != 0:
        w_opt /= w_sum

    port_r    = returns_matrix @ w_opt
    var_95    = float(np.percentile(port_r, alpha * 100))
    tail      = port_r[port_r <= var_95]
    cvar_opt  = float(-tail.mean()) if len(tail) > 0 else 0.0
    port_vol  = float(np.std(port_r) * np.sqrt(252))
    port_ret  = float(np.mean(port_r) * 252)
    sharpe    = (port_ret - risk_free_rate) / max(port_vol, 1e-10)

    return {
        "weights"           : w_opt.round(6).tolist(),
        "portfolio_cvar_95" : round(cvar_opt * 100, 4),
        "portfolio_var_95"  : round(-var_95 * 100, 4),
        "portfolio_vol_ann" : round(port_vol * 100, 4),
        "portfolio_ret_ann" : round(port_ret * 100, 4),
        "sharpe_ratio"      : round(sharpe, 4),
        "converged"         : result.success,
        "confidence"        : confidence,
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 5 — KELLY CRITERION MATRIX (MULTI-ASSET)
# ══════════════════════════════════════════════════════════════════

def kelly_matrix_allocation(
    mu         : np.ndarray,    # Expected returns vector (annualized decimal)
    Sigma      : np.ndarray,    # Covariance matrix (annualized)
    risk_free  : float = 0.04,
    kelly_frac : float = 0.25,  # Fractional Kelly safety factor
    max_leverage: float = 2.0,
) -> Dict:
    """
    Multi-asset Kelly Criterion (Thorp 2006, MacLean-Ziemba 2011).

    Full Kelly for multiple assets:
        w* = Σ⁻¹ × (μ - rf × 1)

    This is the unconstrained optimal log-wealth growth portfolio.
    Apply fractional Kelly (× 0.25) for operational risk management.

    Relationship to MVO:
        Kelly weights = Sharpe-optimal MVO weights × (1/risk_aversion)
        where risk_aversion = 1 for log utility

    Warning: Kelly weights can be large (often >1 = leveraged).
    Always apply the fraction and leverage cap.
    """
    N = len(mu)
    excess_mu = mu - risk_free  # excess returns over risk-free

    try:
        # Regularize Sigma to prevent explosive weights from near-singular matrix
        # Add small eigenvalue floor: Sigma_reg = Sigma + epsilon * I
        min_eig = np.min(np.linalg.eigvalsh(Sigma))
        reg_eps = max(0, 1e-6 - min_eig)  # ensure minimum eigenvalue >= 1e-6
        Sigma_reg = Sigma + reg_eps * np.eye(N)
        Sigma_inv = np.linalg.inv(Sigma_reg)
    except np.linalg.LinAlgError:
        Sigma_inv = np.linalg.pinv(Sigma)

    # Full Kelly weights
    w_full   = Sigma_inv @ excess_mu
    # Fractional Kelly
    w_frac   = w_full * kelly_frac

    # Cap leverage
    total_lev = np.sum(np.abs(w_frac))
    if total_lev > max_leverage:
        w_frac = w_frac * max_leverage / total_lev

    port_ret = float(w_frac @ mu)
    port_vol = float(np.sqrt(w_frac @ Sigma @ w_frac))
    sharpe   = (port_ret - risk_free) / max(port_vol, 1e-10)

    # Growth rate estimate (Kelly objective)
    log_growth = float(w_frac @ excess_mu - 0.5 * (w_frac @ Sigma @ w_frac))

    return {
        "weights_full_kelly"    : w_full.round(6).tolist(),
        "weights_fractional"    : w_frac.round(6).tolist(),
        "kelly_fraction"        : kelly_frac,
        "total_leverage"        : round(float(np.sum(np.abs(w_frac))), 4),
        "leverage_capped"       : total_lev > max_leverage,
        "portfolio_return_ann"  : round(port_ret * 100, 4),
        "portfolio_vol_ann"     : round(port_vol * 100, 4),
        "sharpe_ratio"          : round(sharpe, 4),
        "log_growth_rate_ann"   : round(log_growth * 100, 4),
        "note": (
            "Kelly weights maximise log-wealth. Fractional Kelly reduces ruin probability."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 6 — FACTOR DECOMPOSITION (CORRECTED)
# ══════════════════════════════════════════════════════════════════

def factor_decomposition(
    asset_returns : np.ndarray,   # (T,) asset return series
    factor_returns: Dict[str, np.ndarray],  # factor name → (T,) return series
) -> Dict:
    """
    OLS factor model: r_asset = α + Σ β_i × f_i + ε

    Provides:
      - Alpha (unexplained return)
      - Factor betas (loadings)
      - R² (how much variance explained by factors)
      - Idiosyncratic vol (unexplained risk)

    Factors typically used:
      - "market" : Equity market return (CAPM beta)
      - "momentum": 12-1 momentum factor
      - "value"  : P/B or earnings yield
      - "size"   : Small vs large cap
      - "vol"    : Low volatility anomaly
    """
    n_factors = len(factor_returns)
    if n_factors == 0:
        return {"error": "No factors provided"}

    names = list(factor_returns.keys())
    F     = np.column_stack([factor_returns[n] for n in names])

    # Align lengths
    T = min(len(asset_returns), F.shape[0])
    y = asset_returns[-T:]
    X = np.column_stack([np.ones(T), F[-T:]])  # add intercept

    try:
        beta, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)
    except Exception as e:
        return {"error": str(e)}

    y_hat  = X @ beta
    ss_res = float(np.sum((y - y_hat)**2))
    ss_tot = float(np.sum((y - y.mean())**2))
    r2     = 1 - ss_res / max(ss_tot, 1e-12)

    # Idiosyncratic returns & vol
    eps          = y - y_hat
    idio_vol_ann = float(np.std(eps) * np.sqrt(252) * 100)

    # Annualized alpha
    alpha_daily = float(beta[0])
    alpha_ann   = alpha_daily * 252 * 100

    betas = {names[i]: round(float(beta[i+1]), 6) for i in range(n_factors)}

    return {
        "alpha_daily_pct"  : round(alpha_daily * 100, 6),
        "alpha_ann_pct"    : round(alpha_ann, 4),
        "factor_betas"     : betas,
        "r_squared"        : round(r2, 4),
        "idio_vol_ann_pct" : round(idio_vol_ann, 4),
        "factor_names"     : names,
        "observations"     : T,
        "interpretation"   : (
            f"R²={r2:.2%} of variance explained by factors. "
            f"Idiosyncratic alpha: {alpha_ann:.2f}% p.a."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 7 — LIQUIDITY STRESS TEST & CAPACITY MODEL
# ══════════════════════════════════════════════════════════════════

def liquidity_capacity_analysis(
    tickers       : List[str],
    adv_usd       : Dict[str, float],   # average daily volume in USD per ticker
    weights       : np.ndarray,
    portfolio_aum : float,
    max_participation: float = 0.05,    # max 5% of ADV
    days_to_unwind: int = 5,
) -> Dict:
    """
    Liquidity capacity model: estimates maximum AUM before slippage
    degrades returns, and liquidation time under stress.

    Almgren-Chriss (2000) capacity:
        max_position_usd = max_participation × ADV × days_to_liquidate

    Liquidity score: % of portfolio that can be liquidated in 1 day
    without exceeding max_participation.
    """
    results         = {}
    total_liq_1d    = 0.0
    max_aum_by_liq  = {}

    for i, ticker in enumerate(tickers):
        adv      = adv_usd.get(ticker, 0)
        weight   = float(weights[i]) if i < len(weights) else 0.0
        position = portfolio_aum * weight

        # Max position without exceeding participation
        max_pos  = adv * max_participation * days_to_unwind
        is_illiq = position > max_pos

        # Days to unwind at max participation
        unwind_d = position / (adv * max_participation) if adv > 0 else 999

        liq_1d_usd  = adv * max_participation
        liq_1d_pct  = min(1.0, liq_1d_usd / max(position, 1))
        total_liq_1d += liq_1d_pct * weight

        max_aum_by_liq[ticker] = max_pos / max(weight, 1e-6)

        results[ticker] = {
            "weight"            : round(weight, 4),
            "position_usd"      : round(position, 2),
            "adv_usd"           : round(adv, 2),
            "max_capacity_usd"  : round(max_pos, 2),
            "days_to_unwind"    : round(unwind_d, 2),
            "is_illiquid"       : is_illiq,
            "liq_1d_pct"        : round(liq_1d_pct * 100, 2),
        }

    max_aum  = min(max_aum_by_liq.values()) if max_aum_by_liq else 0
    liq_score = round(total_liq_1d * 100, 2)

    return {
        "portfolio_aum"          : portfolio_aum,
        "max_capacity_usd"       : round(max_aum, 2),
        "at_capacity"            : portfolio_aum >= max_aum * 0.80,
        "1day_liquidity_score"   : liq_score,
        "illiquid_tickers"       : [t for t, v in results.items() if v["is_illiquid"]],
        "per_ticker"             : results,
        "verdict"                : (
            f"✅ Portfolio within capacity at ${portfolio_aum:,.0f} AUM."
            if portfolio_aum < max_aum
            else f"⚠️ AUM ${portfolio_aum:,.0f} exceeds estimated capacity ${max_aum:,.0f}."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 8 — CORRELATION CLUSTERING (FACTOR DIVERSIFICATION)
# ══════════════════════════════════════════════════════════════════

def correlation_clustering(
    corr_matrix : np.ndarray,
    tickers     : List[str],
    threshold   : float = 0.70,
) -> Dict:
    """
    Hierarchical correlation clustering for factor diversification.

    Groups assets with pairwise correlation > threshold into clusters.
    Portfolio should have diversified exposure across clusters, not
    concentrated in one correlated group.

    Uses single-linkage clustering (fast, appropriate for risk management).
    """
    N = len(tickers)
    if N != corr_matrix.shape[0]:
        return {"error": "Dimension mismatch"}

    # Build adjacency: connected if |corr| > threshold
    clusters  = list(range(N))   # each asset starts in its own cluster
    labels    = {i: {i} for i in range(N)}

    for i in range(N):
        for j in range(i + 1, N):
            if abs(corr_matrix[i, j]) >= threshold:
                # Merge cluster of i into cluster of j
                ci, cj = clusters[i], clusters[j]
                if ci != cj:
                    # Update all members of ci to cj
                    for k in range(N):
                        if clusters[k] == ci:
                            clusters[k] = cj

    # Build cluster groups
    unique_clusters = {}
    for i, c in enumerate(clusters):
        unique_clusters.setdefault(c, []).append(tickers[i])

    cluster_list = list(unique_clusters.values())
    n_clusters   = len(cluster_list)

    # Diversification ratio: higher = better
    avg_corr = float(np.mean(np.abs(corr_matrix[np.triu_indices(N, k=1)])))

    return {
        "n_clusters"         : n_clusters,
        "clusters"           : cluster_list,
        "n_assets"           : N,
        "avg_abs_correlation": round(avg_corr, 4),
        "correlation_threshold": threshold,
        "diversification_score": round((1 - avg_corr) * 100, 1),
        "interpretation": (
            f"{n_clusters} independent clusters identified. "
            f"Avg |corr|={avg_corr:.2f}. "
            + ("Good diversification." if avg_corr < 0.4
               else "⚠️ High average correlation — concentrated factor risk.")
        )
    }