"""
╔══════════════════════════════════════════════════════════════════════╗
║   APEX INSTITUTIONAL ARCHITECT — Phase 4: Research Framework        ║
║  Walk-Forward · Alpha Robustness · CVaR Lab · Institutional Report  ║
╚══════════════════════════════════════════════════════════════════════╝

This module implements institutional-level research infrastructure:
  - Rolling walk-forward optimization
  - Alpha robustness testing (noise injection, feature ablation)
  - Advanced risk decomposition
  - Institutional-grade performance attribution report
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis, t as t_dist
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable
import warnings
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
#  SECTION 1 — ROLLING WALK-FORWARD OPTIMIZATION
# ══════════════════════════════════════════════════════════════════

@dataclass
class WalkForwardWindow:
    window_id      : int
    train_start    : str
    train_end      : str
    test_start     : str
    test_end       : str
    train_sharpe   : float = 0.0
    test_sharpe    : float = 0.0
    train_wr       : float = 0.0
    test_wr        : float = 0.0
    train_n_trades : int   = 0
    test_n_trades  : int   = 0
    degradation    : float = 0.0   # (test_metric - train_metric) / train_metric
    is_robust      : bool  = False


def rolling_walk_forward(
    returns_by_date  : pd.Series,   # strategy daily returns with DatetimeIndex
    strategy_fn      : Callable,    # function(train_df) → (params); applied to test
    train_months     : int  = 12,
    test_months      : int  = 3,
    min_degradation  : float = -0.30,  # max 30% performance drop OOS
    ann_factor       : int  = 252,
) -> Dict:
    """
    Rolling Walk-Forward Validation.

    Splits the strategy period into overlapping train/test windows.
    For each window, measures in-sample vs out-of-sample Sharpe ratio.

    Stability test: A robust strategy should show:
        degradation = (SR_test - SR_train) / SR_train ≥ min_degradation
        i.e., OOS performance ≥ 70% of in-sample performance.

    Args:
        returns_by_date: Daily return series (DatetimeIndex)
        strategy_fn    : Function that accepts a return slice and returns
                         (sharpe, win_rate, n_trades). Pass your backtest runner.
        train_months   : Training window in months
        test_months    : Out-of-sample test window in months

    Note:
        strategy_fn is a stub here — wire it to your actual backtest in
        portfolio_simulator_v4.run_simulation() per the patterns used there.
    """
    if returns_by_date.empty or len(returns_by_date) < 60:
        return {"error": "Insufficient data for walk-forward (min 60 observations)"}

    dates    = returns_by_date.index
    start    = dates[0]
    end      = dates[-1]

    windows : List[WalkForwardWindow] = []
    window_id = 0

    current = start
    while True:
        train_end  = current + pd.DateOffset(months=train_months)
        test_end   = train_end + pd.DateOffset(months=test_months)

        if test_end > end:
            break

        # Slice returns — exclusive boundary to prevent data leak (H5 fix)
        train_r = returns_by_date[current:train_end - pd.Timedelta(days=1)]
        test_r  = returns_by_date[train_end:test_end]

        if len(train_r) < 20 or len(test_r) < 5:
            current += pd.DateOffset(months=test_months)
            window_id += 1
            continue

        # Compute metrics from return series (strategy_fn or simple SR)
        def _sr_from_returns(r):
            if len(r) < 2 or r.std() == 0: return 0.0
            return float(r.mean() / r.std() * np.sqrt(ann_factor))

        train_sr = strategy_fn(train_r) if callable(strategy_fn) else _sr_from_returns(train_r)
        test_sr  = strategy_fn(test_r)  if callable(strategy_fn) else _sr_from_returns(test_r)

        degradation = (
            (test_sr - train_sr) / abs(train_sr)
            if train_sr != 0 else 0.0
        )

        wf = WalkForwardWindow(
            window_id    = window_id,
            train_start  = str(current.date()),
            train_end    = str(train_end.date()),
            test_start   = str(train_end.date()),
            test_end     = str(test_end.date()),
            train_sharpe = round(train_sr, 4),
            test_sharpe  = round(test_sr, 4),
            degradation  = round(degradation, 4),
            is_robust    = degradation >= min_degradation,
        )
        windows.append(wf)

        current += pd.DateOffset(months=test_months)
        window_id += 1

    n_total   = len(windows)
    n_robust  = sum(1 for w in windows if w.is_robust)
    avg_train = float(np.mean([w.train_sharpe for w in windows])) if windows else 0
    avg_test  = float(np.mean([w.test_sharpe  for w in windows])) if windows else 0

    return {
        "n_windows"       : n_total,
        "n_robust"        : n_robust,
        "robust_rate"     : round(n_robust / max(n_total, 1), 4),
        "avg_train_sharpe": round(avg_train, 4),
        "avg_test_sharpe" : round(avg_test, 4),
        "avg_degradation" : round(float(np.mean([w.degradation for w in windows])) if windows else 0, 4),
        "windows"         : [
            {
                "id"          : w.window_id,
                "train"       : f"{w.train_start} → {w.train_end}",
                "test"        : f"{w.test_start} → {w.test_end}",
                "train_sr"    : w.train_sharpe,
                "test_sr"     : w.test_sharpe,
                "degradation" : round(w.degradation * 100, 2),
                "robust"      : w.is_robust,
            }
            for w in windows
        ],
        "verdict": (
            f"✅ ROBUST: {n_robust}/{n_total} windows passed OOS test (>{min_degradation*-100:.0f}% tolerance)."
            if n_robust >= n_total * 0.70
            else f"❌ NOT ROBUST: Only {n_robust}/{n_total} windows passed. Strategy likely overfit."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 2 — ALPHA ROBUSTNESS TESTING
# ══════════════════════════════════════════════════════════════════

def noise_injection_test(
    returns        : np.ndarray,
    signal_fn      : Callable[[np.ndarray], float],  # takes noisy returns → metric
    noise_levels   : List[float] = [0.01, 0.05, 0.10, 0.20],
    n_runs         : int = 200,
    seed           : int = 42,
) -> Dict:
    """
    Noise Injection Robustness Test.

    Injects Gaussian noise into the return series at increasing levels
    and measures how much the strategy metric degrades.

    Robust alpha should maintain >70% of baseline performance under
    moderate noise (σ_noise = 5% of σ_returns).

    Institutional use: validates that signal is not spuriously correlated
    with specific data quirks or microstructure noise.

    Args:
        signal_fn: Function that accepts a return series and returns
                   a scalar performance metric (Sharpe, WR, etc.)
    """
    np.random.seed(seed)
    baseline    = signal_fn(returns)
    sig_returns = float(np.std(returns))

    results = {}
    for level in noise_levels:
        noise_std     = sig_returns * level
        trial_metrics = []
        for _ in range(n_runs):
            noise   = np.random.normal(0, noise_std, size=len(returns))
            noisy_r = returns + noise
            try:
                m = signal_fn(noisy_r)
                if np.isfinite(m):
                    trial_metrics.append(m)
            except Exception:
                continue

        if not trial_metrics:
            continue

        arr          = np.array(trial_metrics)
        retention    = float(np.mean(arr)) / abs(baseline) if baseline != 0 else 0.0
        ci_lo        = float(np.percentile(arr, 2.5))
        ci_hi        = float(np.percentile(arr, 97.5))

        results[f"noise_{int(level*100)}pct"] = {
            "noise_sigma_pct"     : level * 100,
            "mean_metric"         : round(float(np.mean(arr)), 4),
            "metric_retention_pct": round(retention * 100, 2),
            "ci_95_lower"         : round(ci_lo, 4),
            "ci_95_upper"         : round(ci_hi, 4),
            "passes_70pct_test"   : retention >= 0.70,
        }

    n_pass = sum(1 for v in results.values() if v.get("passes_70pct_test"))
    n_tot  = len(results)

    return {
        "baseline_metric"  : round(baseline, 4),
        "signal_vol"       : round(sig_returns, 6),
        "noise_results"    : results,
        "levels_tested"    : n_tot,
        "levels_passed"    : n_pass,
        "verdict"          : (
            f"✅ Signal robust: passes {n_pass}/{n_tot} noise injection levels."
            if n_pass >= n_tot * 0.75
            else f"⚠️ Signal fragile: only {n_pass}/{n_tot} levels passed."
        )
    }


def parameter_stability_test(
    param_grid      : Dict[str, List],     # {"rsi_period": [10,14,20], "atr_mult": [1,1.5,2]}
    backtest_fn     : Callable[[Dict], float],  # params → Sharpe
    base_params     : Dict,
    sensitivity_threshold: float = 0.30,  # flag if metric changes >30% from baseline
) -> Dict:
    """
    Parameter Perturbation / Sensitivity Analysis.

    Tests how sensitive the strategy is to small parameter changes.
    Fragile strategies (high sensitivity) are likely overfit.

    For each parameter:
        1. Hold all others at base_params
        2. Vary the parameter across param_grid values
        3. Compute metric sensitivity

    A robust strategy should show:
        |metric(param_perturb) - metric(base)| / metric(base) < sensitivity_threshold
    """
    baseline = backtest_fn(base_params)

    param_results = {}
    for param_name, values in param_grid.items():
        metrics = {}
        for val in values:
            test_params = dict(base_params)
            test_params[param_name] = val
            try:
                m = backtest_fn(test_params)
                metrics[val] = round(m, 4) if np.isfinite(m) else None
            except Exception:
                metrics[val] = None

        valid_m = [v for v in metrics.values() if v is not None]
        if not valid_m:
            continue

        sensitivity = (max(valid_m) - min(valid_m)) / abs(baseline) if baseline != 0 else 0
        stable      = sensitivity < sensitivity_threshold

        param_results[param_name] = {
            "values"         : list(metrics.keys()),
            "metrics"        : list(metrics.values()),
            "min"            : round(min(valid_m), 4),
            "max"            : round(max(valid_m), 4),
            "range"          : round(max(valid_m) - min(valid_m), 4),
            "sensitivity_pct": round(sensitivity * 100, 2),
            "is_stable"      : stable,
        }

    n_stable   = sum(1 for v in param_results.values() if v["is_stable"])
    n_total    = len(param_results)

    return {
        "baseline"         : round(baseline, 4),
        "params_tested"    : n_total,
        "params_stable"    : n_stable,
        "stability_score"  : round(n_stable / max(n_total, 1) * 100, 1),
        "per_parameter"    : param_results,
        "verdict"          : (
            f"✅ Parameters stable: {n_stable}/{n_total} within {sensitivity_threshold*100:.0f}% tolerance."
            if n_stable >= n_total * 0.75
            else f"❌ Overfit risk: {n_total - n_stable}/{n_total} params show high sensitivity."
        )
    }


def feature_ablation_test(
    features        : Dict[str, np.ndarray],  # feature_name → signal array
    performance_fn  : Callable[[Dict[str, np.ndarray]], float],
) -> Dict:
    """
    Feature Ablation Study.

    Measures the marginal contribution of each signal feature by
    removing it from the model and computing performance degradation.

    Features with POSITIVE ablation (removal improves performance)
    are ANTI-SIGNALS and should be removed (as was the case with
    RSI and volume in the original portfolio_simulator.py).

    Args:
        features      : Dict of signal arrays contributing to decisions
        performance_fn: Accepts feature dict → scalar metric
    """
    baseline  = performance_fn(features)
    ablations = {}

    for feature_name in features:
        # Run with this feature removed
        ablated = {k: v for k, v in features.items() if k != feature_name}
        try:
            score = performance_fn(ablated)
        except Exception:
            score = baseline

        delta          = score - baseline
        contribution   = -delta  # positive = removing hurts = feature is helpful
        is_anti_signal = delta > 0  # removing IMPROVES → feature was hurting

        ablations[feature_name] = {
            "baseline_score"   : round(baseline, 4),
            "ablated_score"    : round(score, 4),
            "delta"            : round(delta, 4),
            "feature_contribution": round(contribution, 4),
            "is_anti_signal"   : is_anti_signal,
            "verdict"          : (
                "❌ ANTI-SIGNAL — removing improves performance. DISCARD this feature."
                if is_anti_signal
                else "✅ Positive contribution. Keep feature."
            )
        }

    # Rank by contribution
    ranked = sorted(ablations.items(), key=lambda x: x[1]["feature_contribution"], reverse=True)
    anti_signals = [k for k, v in ablations.items() if v["is_anti_signal"]]

    return {
        "baseline"        : round(baseline, 4),
        "anti_signals"    : anti_signals,
        "feature_ranking" : [{"feature": k, **v} for k, v in ranked],
        "verdict"         : (
            f"Found {len(anti_signals)} anti-signal(s): {anti_signals}. Remove immediately."
            if anti_signals
            else "No anti-signals detected. All features contribute positively."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 3 — ADVANCED RISK LABORATORY
# ══════════════════════════════════════════════════════════════════

def advanced_risk_decomposition(
    returns         : np.ndarray,   # strategy returns (daily)
    factor_returns  : Optional[Dict[str, np.ndarray]] = None,
    confidence_levels: List[float] = [0.90, 0.95, 0.99],
    ann_factor      : int = 252,
) -> Dict:
    """
    Institutional risk decomposition report.

    Computes:
      1. CVaR at multiple confidence levels (95%, 99%)
      2. Tail Ratio (upside 95th pct / downside 5th pct abs value)
      3. Conditional Drawdown at Risk (CDaR)
      4. Skewness & Excess Kurtosis monitoring
      5. Regime-based risk decomposition (if factor returns provided)
    """
    r      = np.asarray(returns)
    n      = len(r)
    ann_r  = float(np.mean(r) * ann_factor)
    ann_v  = float(np.std(r) * np.sqrt(ann_factor))

    # VaR and CVaR at each confidence level
    var_cvar = {}
    for cl in confidence_levels:
        alpha  = 1 - cl
        var_v  = float(np.percentile(r, alpha * 100))
        tail   = r[r <= var_v]
        cvar_v = float(tail.mean()) if len(tail) > 0 else var_v
        var_cvar[f"{int(cl*100)}pct"] = {
            "var_pct"  : round(-var_v * 100, 4),
            "cvar_pct" : round(-cvar_v * 100, 4),
        }

    # Tail Ratio (Lempérière et al. 2014)
    # = P95 upside / |P5 downside|
    p95_up   = float(np.percentile(r, 95))
    p5_down  = abs(float(np.percentile(r, 5)))
    tail_ratio = p95_up / max(p5_down, 1e-10)

    # Conditional Drawdown at Risk (CDaR)
    cum_ret    = np.exp(np.cumsum(r))
    running    = np.maximum.accumulate(cum_ret)
    drawdowns  = (cum_ret - running) / running
    var_dd_95  = float(np.percentile(drawdowns, 5))  # 5th pct (worst 5%)
    cdar_95    = float(drawdowns[drawdowns <= var_dd_95].mean()) if (drawdowns <= var_dd_95).any() else var_dd_95
    max_dd     = float(drawdowns.min() * 100)

    # Distribution moments
    sk = float(skew(r))
    kt = float(kurtosis(r))   # excess kurtosis

    # Ulcer Index: RMS of drawdown depth
    ulcer_idx = float(np.sqrt(np.mean(drawdowns**2)) * 100)

    # Omega Ratio (return above threshold 0% / return below 0%)
    positive_r  = r[r > 0].sum()
    negative_r  = abs(r[r < 0].sum())
    omega_ratio = positive_r / max(negative_r, 1e-10)

    out = {
        "annualized_return_pct"  : round(ann_r * 100, 4),
        "annualized_vol_pct"     : round(ann_v * 100, 4),
        "var_cvar"               : var_cvar,
        "tail_ratio"             : round(tail_ratio, 4),
        "cdar_95_pct"            : round(cdar_95 * 100, 4),
        "max_drawdown_pct"       : round(max_dd, 4),
        "ulcer_index"            : round(ulcer_idx, 4),
        "omega_ratio"            : round(omega_ratio, 4),
        "skewness"               : round(sk, 4),
        "excess_kurtosis"        : round(kt, 4),
        "fat_tail_present"       : kt > 3.0,
        "negative_skew_warning"  : sk < -0.5,
        "n_observations"         : n,
    }

    # Regime-based risk decomposition (if factors provided)
    if factor_returns:
        regime_risk = {}
        for fname, fr in factor_returns.items():
            aligned_n = min(len(r), len(fr))
            r_a, f_a  = r[-aligned_n:], np.asarray(fr[-aligned_n:])
            # Beta to factor
            cov = float(np.cov(r_a, f_a)[0, 1])
            var = float(np.var(f_a))
            beta = cov / max(var, 1e-12)
            # Contribution to vol
            factor_vol_contrib = abs(beta) * float(np.std(f_a) * np.sqrt(ann_factor))
            regime_risk[fname] = {
                "beta"              : round(beta, 4),
                "vol_contribution"  : round(factor_vol_contrib * 100, 4),
            }
        out["regime_risk_decomposition"] = regime_risk

    return out


# ══════════════════════════════════════════════════════════════════
#  SECTION 4 — MONTE CARLO EQUITY RESHUFFLING
# ══════════════════════════════════════════════════════════════════

def monte_carlo_equity_reshuffling(
    trade_returns   : np.ndarray,    # per-trade P&L as % of capital
    n_simulations   : int = 10_000,
    initial_capital : float = 100_000,
    seed            : int   = 42,
) -> Dict:
    """
    Monte Carlo equity reshuffling (10,000 permutations).

    Randomly reshuffles the order of observed trades to generate
    a distribution of possible equity curves given the same trades.

    This does NOT assume any return distribution — it uses the
    empirical trade outcomes (non-parametric).

    Provides:
      - Distribution of final capital
      - Max drawdown distribution
      - Probability of ruin (−50% drawdown)
      - 5th/95th percentile equity paths

    Advantage over GBM simulation: uses actual observed returns,
    capturing real skewness and kurtosis of the strategy.
    """
    np.random.seed(seed)
    n  = len(trade_returns)
    r  = np.asarray(trade_returns, dtype=float) / 100.0  # convert pct to decimal

    final_caps    = np.zeros(n_simulations)
    max_dds       = np.zeros(n_simulations)
    ruin_flags    = np.zeros(n_simulations, dtype=bool)

    for i in range(n_simulations):
        shuffled = np.random.permutation(r)
        equity   = initial_capital * np.cumprod(1 + shuffled)
        final_caps[i] = float(equity[-1])

        # Max drawdown
        running = np.maximum.accumulate(equity)
        dd      = (equity - running) / running
        max_dds[i] = float(dd.min())

        # Ruin: ever drops below 50% of initial
        ruin_flags[i] = bool(equity.min() < initial_capital * 0.50)

    pnl_pcts = (final_caps / initial_capital - 1) * 100

    return {
        "n_simulations"        : n_simulations,
        "n_trades"             : n,
        "initial_capital"      : initial_capital,
        "final_capital": {
            "p5"    : round(float(np.percentile(final_caps, 5)), 2),
            "p25"   : round(float(np.percentile(final_caps, 25)), 2),
            "median": round(float(np.median(final_caps)), 2),
            "p75"   : round(float(np.percentile(final_caps, 75)), 2),
            "p95"   : round(float(np.percentile(final_caps, 95)), 2),
        },
        "return_pct": {
            "p5"    : round(float(np.percentile(pnl_pcts, 5)), 2),
            "median": round(float(np.median(pnl_pcts)), 2),
            "p95"   : round(float(np.percentile(pnl_pcts, 95)), 2),
            "mean"  : round(float(np.mean(pnl_pcts)), 2),
        },
        "max_drawdown_distribution": {
            "mean_pct"    : round(float(np.mean(max_dds) * 100), 2),
            "worst_5pct"  : round(float(np.percentile(max_dds, 5) * 100), 2),
            "worst_1pct"  : round(float(np.percentile(max_dds, 1) * 100), 2),
        },
        "risk_of_ruin_pct"     : round(float(ruin_flags.mean() * 100), 2),
        "prob_profit_pct"      : round(float(np.mean(pnl_pcts > 0) * 100), 2),
        "prob_return_gt_10pct" : round(float(np.mean(pnl_pcts > 10) * 100), 2),
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 5 — INSTITUTIONAL PERFORMANCE ATTRIBUTION REPORT
# ══════════════════════════════════════════════════════════════════

def generate_institutional_report(
    strategy_name   : str,
    returns         : np.ndarray,
    trade_returns   : Optional[np.ndarray] = None,
    factor_returns  : Optional[Dict[str, np.ndarray]] = None,
    n_trials_tested : int  = 1,
    ann_factor      : int  = 252,
    risk_free       : float = 0.04,
    initial_capital : float = 100_000,
) -> Dict:
    """
    Master institutional performance report. Aggregates all modules.

    Sections:
      1. Performance Summary (return, SR, Calmar)
      2. Statistical Validity (t-stat, p-value, DSR, bootstrap SR CI)
      3. Risk Attribution (CVaR, tail ratio, CDaR, drawdown dist)
      4. Monte Carlo equity reshuffling (if trade returns provided)
      5. Factor exposure decomposition (if factor returns provided)
      6. Overall verdict: DEPLOY / RESEARCH / DISCARD
    """
    from .apex_systematic_trader import (
        lo_autocorrelation_adjusted_sharpe,
        deflated_sharpe_ratio,
        bootstrap_sharpe_ci,
        calculate_risk_of_ruin,
    )

    r   = np.asarray(returns, dtype=float)
    n   = len(r)
    mu  = float(np.mean(r))
    sig = float(np.std(r, ddof=1))

    ann_ret = mu * ann_factor
    ann_vol = sig * np.sqrt(ann_factor)
    raw_sr  = (ann_ret - risk_free) / max(ann_vol, 1e-10)

    # 1. Lo (2002) adjusted Sharpe
    lo_result  = lo_autocorrelation_adjusted_sharpe(r, ann_factor)
    adj_sr     = lo_result.get("adjusted_sharpe_lo2002", raw_sr)

    # 2. Deflated Sharpe
    dsr_result = deflated_sharpe_ratio(adj_sr, n_trials_tested, n)

    # 3. Bootstrap Sharpe CI
    boot_result = bootstrap_sharpe_ci(r, n_bootstrap=5_000)

    # 4. Statistical significance
    se      = sig / np.sqrt(n) * np.sqrt(ann_factor)  # SE of annualized mean
    t_stat  = (ann_ret - risk_free) / max(se, 1e-10)
    p_value = float(t_dist.sf(t_stat, df=n - 1))

    # 5. Max drawdown
    cum     = np.exp(np.cumsum(r))
    peak    = np.maximum.accumulate(cum)
    dd_arr  = (cum - peak) / peak
    mdd     = float(dd_arr.min() * 100)
    calmar  = ann_ret / abs(mdd / 100) if mdd < 0 else 0

    # 6. CVaR 95 & 99
    risk_decomp = advanced_risk_decomposition(r, factor_returns, [0.95, 0.99])

    # 7. Monte Carlo (if trade returns given)
    mc_result = None
    if trade_returns is not None and len(trade_returns) >= 10:
        mc_result = monte_carlo_equity_reshuffling(
            trade_returns, n_simulations=10_000, initial_capital=initial_capital
        )

    # 8. Overall verdict
    checks_pass = 0
    checks_pass += int(adj_sr >= 1.5)
    checks_pass += int(abs(mdd) <= 25)
    checks_pass += int(p_value <= 0.05)
    checks_pass += int(dsr_result.get("is_significant_05", False))
    checks_pass += int(boot_result.get("prob_sr_above_1", 0) >= 60)

    if checks_pass == 5:
        overall = "✅ DEPLOY"
    elif checks_pass >= 3 and p_value <= 0.10:
        overall = "🔬 RESEARCH"
    else:
        overall = "❌ DISCARD"

    return {
        "strategy"              : strategy_name,
        "report_timestamp"      : pd.Timestamp.now().isoformat(),
        "overall_verdict"       : overall,
        "checks_passed"         : f"{checks_pass}/5",

        "performance_summary": {
            "annualized_return_pct"   : round(ann_ret * 100, 4),
            "annualized_vol_pct"      : round(ann_vol * 100, 4),
            "raw_sharpe"              : round(raw_sr, 4),
            "lo_adjusted_sharpe"      : round(adj_sr, 4),
            "calmar_ratio"            : round(calmar, 4),
            "max_drawdown_pct"        : round(mdd, 4),
            "n_observations"          : n,
        },

        "statistical_validity": {
            "t_statistic"             : round(t_stat, 4),
            "p_value"                 : round(p_value, 4),
            "is_significant_05"       : p_value <= 0.05,
            "deflated_sharpe_ratio"   : dsr_result,
            "bootstrap_sharpe_95ci"   : {
                "lower" : boot_result.get("ci_lower"),
                "upper" : boot_result.get("ci_upper"),
                "prob_sr_above_1": boot_result.get("prob_sr_above_1"),
            },
            "lo2002_autocorr_adj"     : lo_result,
        },

        "risk_attribution"          : risk_decomp,
        "monte_carlo"               : mc_result,

        "capital_allocation_note": (
            "Strategy passed statistical and risk targets. "
            "Recommend 5% initial capital allocation with 3-month live monitoring."
            if overall == "✅ DEPLOY"
            else "Do not deploy. Continue research or discard strategy."
        )
    }


# ══════════════════════════════════════════════════════════════════
#  SECTION 6 — STRESS TEST SCENARIO TABLE
# ══════════════════════════════════════════════════════════════════

def stress_test_portfolio(
    weights         : np.ndarray,
    tickers         : List[str],
    portfolio_value : float,
    scenarios       : Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict:
    """
    Apply historical stress test scenarios to current portfolio.

    Each scenario specifies % shock per asset class.
    If tickers not in scenario, 0% shock assumed.

    Built-in scenarios from historical crises.

    Args:
        weights        : Portfolio weights (sum to 1)
        tickers        : Corresponding ticker list
        portfolio_value: Total portfolio value in USD
        scenarios      : Optional custom scenarios (name → ticker → shock_pct)
    """
    BUILTIN_SCENARIOS = {
        "covid_crash_2020": {
            "description" : "COVID-19 crash (Feb-Mar 2020)",
            "duration_days": 33,
            "equity_shock" : -0.34,
            "crypto_shock" : -0.50,
            "bond_shock"   : +0.05,
            "gold_shock"   : -0.12,
        },
        "gfc_2008": {
            "description" : "Global Financial Crisis 2008",
            "duration_days": 365,
            "equity_shock" : -0.57,
            "crypto_shock" : None,
            "bond_shock"   : +0.10,
            "gold_shock"   : +0.05,
        },
        "dot_com_2000": {
            "description" : "Dot-com bust 2000-2002",
            "duration_days": 730,
            "equity_shock" : -0.49,
            "crypto_shock" : None,
            "bond_shock"   : +0.08,
            "gold_shock"   : +0.05,
        },
        "crypto_bear_2022": {
            "description" : "Crypto bear market 2022",
            "duration_days": 365,
            "equity_shock" : -0.20,
            "crypto_shock" : -0.77,
            "bond_shock"   : -0.15,
            "gold_shock"   : -0.02,
        },
        "rate_shock_1994": {
            "description" : "Fed rate shock 1994",
            "duration_days": 180,
            "equity_shock" : -0.08,
            "crypto_shock" : None,
            "bond_shock"   : -0.10,
            "gold_shock"   : -0.05,
        },
    }

    def _classify_ticker(t: str) -> str:
        tu = t.upper()
        # Check crypto by suffix to avoid substring false positives (M4 fix)
        if tu.endswith("USDT") or tu.endswith("-USD") and any(c in tu for c in ["BTC", "ETH", "SOL", "BNB", "DOGE", "XRP", "ADA"]):
            return "crypto"
        if any(x in tu for x in ["GLD", "GC=F", "GOLD", "IAU"]):
            return "gold"
        if any(x in tu for x in ["TLT", "IEF", "BND", "BOND"]):
            return "bond"
        return "equity"

    results = {}
    for s_name, s_params in BUILTIN_SCENARIOS.items():
        portfolio_shock = 0.0
        asset_shocks    = {}
        for i, ticker in enumerate(tickers):
            w       = float(weights[i]) if i < len(weights) else 0.0
            cls     = _classify_ticker(ticker)
            shock   = s_params.get(f"{cls}_shock")
            if shock is None:
                shock = s_params.get("equity_shock", -0.20)
            asset_shocks[ticker]  = round(shock * 100, 2)
            portfolio_shock      += w * shock

        loss_usd = portfolio_value * portfolio_shock
        results[s_name] = {
            "description"       : s_params.get("description", s_name),
            "duration_days"     : s_params.get("duration_days", 0),
            "portfolio_shock_pct": round(portfolio_shock * 100, 2),
            "loss_usd"          : round(loss_usd, 2),
            "survival_pct"      : round((1 + portfolio_shock) * 100, 2),
            "asset_shocks_pct"  : asset_shocks,
        }

    # Sort by worst loss first
    sorted_results = dict(
        sorted(results.items(), key=lambda x: x[1]["portfolio_shock_pct"])
    )

    worst_scenario = list(sorted_results.keys())[0]
    worst_loss     = sorted_results[worst_scenario]["portfolio_shock_pct"]

    return {
        "portfolio_value"   : portfolio_value,
        "n_tickers"         : len(tickers),
        "scenarios"         : sorted_results,
        "worst_scenario"    : worst_scenario,
        "worst_loss_pct"    : worst_loss,
        "verdict"           : (
            f"✅ Portfolio survives worst scenario ({worst_scenario}: {worst_loss:.1f}%) above -30%."
            if worst_loss >= -30
            else f"⚠️ Worst scenario ({worst_scenario}: {worst_loss:.1f}%) exceeds -30% threshold."
        )
    }