"""
╔══════════════════════════════════════════════════════════════════╗
║              APEX QUANT ENGINE v2.0                              ║
║  Fixed: Gaussian VaR → Historical + Cornish-Fisher               ║
║  Fixed: Sortino MAR 5% → 0% (correct benchmark)                 ║
║  Added: Calmar, Omega, Skewness, Excess Kurtosis, CVaR           ║
╠══════════════════════════════════════════════════════════════════╣
║  AUDIT FIXES:                                                    ║
║  [CRITICAL] VaR 95% sebelumnya pakai norm.ppf() → asumsi        ║
║    Gaussian. Equity/crypto returns punya fat-tail (kurtosis>3).  ║
║    Gaussian VaR understates tail risk 30-50%.                    ║
║    Fix: Historical simulation + Cornish-Fisher expansion.        ║
║                                                                  ║
║  [HIGH] Sortino pakai MAR=5% hardcoded. Untuk aset dengan         ║
║    ann_return < 5%, ini selalu negatif tanpa edge.               ║
║    Fix: MAR=0% (industry standard untuk strategy evaluation).    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from scipy.stats import norm, skew as scipy_skew, kurtosis as scipy_kurt
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────
#  INTERNAL: VaR / CVaR (replaces norm.ppf approach)
# ─────────────────────────────────────────────────────────────────

def _var_cvar(log_ret: np.ndarray, confidence: float = 0.95):
    """
    Dual-method VaR + CVaR:
      1. Historical simulation (non-parametric, no distribution assumption)
      2. Cornish-Fisher (adjusts for skewness + excess kurtosis)

    Returns (var_hist, cvar_hist, var_cf, cvar_cf) as daily decimals.
    Negative values = losses (e.g. -0.025 = -2.5% loss).
    """
    if len(log_ret) < 10:
        return 0.0, 0.0, 0.0, 0.0

    alpha = 1.0 - confidence
    sorted_r = np.sort(log_ret)

    # ── Historical ──────────────────────────────────────────────
    idx_h  = max(0, int(np.floor(alpha * len(log_ret))) - 1)
    var_h  = float(sorted_r[idx_h])
    tail_h = sorted_r[:idx_h + 1]
    cvar_h = float(tail_h.mean()) if len(tail_h) > 0 else var_h

    # ── Cornish-Fisher expansion ─────────────────────────────────
    mu_r = float(np.mean(log_ret))
    sg_r = float(np.std(log_ret))
    sk   = float(scipy_skew(log_ret))
    kt   = float(scipy_kurt(log_ret))    # excess kurtosis
    z    = norm.ppf(alpha)

    # CF adjusted quantile
    z_cf = (z
            + (z**2 - 1) * sk / 6
            + (z**3 - 3*z) * kt / 24
            - (2*z**3 - 5*z) * sk**2 / 36)

    var_cf  = float(mu_r + z_cf * sg_r)
    tail_cf = sorted_r[sorted_r <= var_cf]
    cvar_cf = float(tail_cf.mean()) if len(tail_cf) > 0 else var_cf

    return var_h, cvar_h, var_cf, cvar_cf


# ─────────────────────────────────────────────────────────────────
#  1. MAIN QUANT METRICS (drop-in replacement)
# ─────────────────────────────────────────────────────────────────

def calculate_quant_metrics(df, ticker: str = "") -> Dict:
    """
    Drop-in replacement for legacy calculate_quant_metrics().

    Output keys preserved for backward compatibility + new keys added:
      PRESERVED : volatility, sortino, max_drawdown, var_95, action
      NEW       : ann_return, calmar, var_95_hist, cvar_95, var_cf,
                  cvar_cf, skewness, excess_kurtosis, fat_tail, omega
    """
    default = {
        "volatility": 0, "sortino": 0, "max_drawdown": 0,
        "var_95": 0, "action": "WAIT",
        # new fields default
        "ann_return": 0, "calmar": 0,
        "var_95_hist": 0, "cvar_95": 0,
        "var_95_cf": 0, "cvar_95_cf": 0,
        "skewness": 0, "excess_kurtosis": 0,
        "fat_tail": False, "omega_ratio": 1.0,
    }

    try:
        if df is None or df.empty or "Close" not in df.columns:
            return default

        close = df["Close"].dropna()
        if len(close) < 10:
            return default

        log_ret = np.log(close / close.shift(1)).dropna().values
        if len(log_ret) < 10:
            return default

        ann   = 252
        vol   = float(np.std(log_ret, ddof=1) * np.sqrt(ann))
        mu    = float(np.mean(log_ret) * ann)

        # ── Sortino (MAR = 0%, not 5%) ──────────────────────────
        downside = log_ret[log_ret < 0]
        down_vol = float(np.std(downside, ddof=1) * np.sqrt(ann)) if len(downside) > 2 else vol
        sortino  = float(mu / down_vol) if down_vol > 0 else 0.0

        # ── Max Drawdown ─────────────────────────────────────────
        cum     = np.exp(np.cumsum(log_ret))
        rolling = np.maximum.accumulate(cum)
        dd      = (cum - rolling) / rolling
        mdd     = float(dd.min() * 100)

        # ── Calmar ───────────────────────────────────────────────
        calmar = float(mu / abs(mdd / 100)) if mdd < 0 else 0.0

        # ── VaR / CVaR (corrected) ───────────────────────────────
        var_h, cvar_h, var_cf, cvar_cf = _var_cvar(log_ret, 0.95)

        # ── Distribution moments ─────────────────────────────────
        sk = float(scipy_skew(log_ret))
        kt = float(scipy_kurt(log_ret))

        # ── Omega Ratio ──────────────────────────────────────────
        pos_r = log_ret[log_ret > 0]
        neg_r = log_ret[log_ret < 0]
        omega = float(pos_r.mean() / abs(neg_r.mean())) if len(neg_r) > 0 else 9999.0

        # ── Action signal ─────────────────────────────────────────
        action = "BULLISH" if sortino > 0.5 else "BEARISH" if sortino < -0.2 else "NEUTRAL"

        return {
            # backward-compat keys
            "volatility"       : round(vol * 100, 4),
            "sortino"          : round(sortino, 4),
            "max_drawdown"     : round(mdd, 2),
            "var_95"           : round(var_cf * 100, 4),   # now CF-adjusted (was Gaussian)
            "action"           : action,
            # new keys
            "ann_return_pct"   : round(mu * 100, 4),
            "calmar_ratio"     : round(calmar, 4),
            "var_95_hist_pct"  : round(var_h * 100, 4),
            "cvar_95_hist_pct" : round(cvar_h * 100, 4),
            "var_95_cf_pct"    : round(var_cf * 100, 4),
            "cvar_95_cf_pct"   : round(cvar_cf * 100, 4),
            "skewness"         : round(sk, 4),
            "excess_kurtosis"  : round(kt, 4),
            "fat_tail"         : kt > 3.0,
            "omega_ratio"      : round(omega, 4),
        }

    except Exception as e:
        return {**default, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
#  2. TECHNICALS (unchanged — no bugs found)
# ─────────────────────────────────────────────────────────────────

def calculate_technicals(df) -> Dict:
    if df is None or df.empty:
        return {}

    close = df["Close"]

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs    = gain / loss
    rsi   = 100 - (100 / (1 + rs))

    return {
        "ema20"  : ema20.dropna().tolist(),
        "ema50"  : ema50.dropna().tolist(),
        "rsi"    : rsi.dropna().tolist(),
        "volume" : df["Volume"].tolist() if "Volume" in df.columns else [],
        "dates"  : df.index.strftime("%Y-%m-%d").tolist(),
    }