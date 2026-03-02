"""
╔══════════════════════════════════════════════════════════════════╗
║           APEX STATISTICS & PROBABILITY ENGINE                   ║
║   Z-Score · Std Dev · Monte Carlo · VaR · CVaR · Drawdown Sim   ║
╚══════════════════════════════════════════════════════════════════╝

Modul ini mengubah prediksi "halu" AI menjadi angka keras berbasis:
  1. Z-Score Detection    → Deteksi harga ekstrem secara statistik
  2. Monte Carlo Sim      → Simulasi 10,000+ skenario masa depan
  3. Parametric VaR/CVaR  → Worst-case loss pada confidence level tertentu
  4. Regime Detection     → Deteksi market trending vs sideways
  5. Bootstrapped Returns → Non-parametric confidence dari data nyata
"""

import numpy as np
import pandas as pd
from scipy.stats import norm, skew, kurtosis, jarque_bera
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. Z-SCORE & STATISTICAL EXTREMES
# ─────────────────────────────────────────────────────────────────

def calculate_zscore_analysis(df: pd.DataFrame, window: int = 20) -> Dict:
    """
    Hitung Z-Score harga untuk deteksi kondisi overbought/oversold secara statistik.

    Z = (X - μ) / σ
      |Z| > 2 = Signifikan (5% kemungkinan)
      |Z| > 3 = Sangat Ekstrem (0.3% kemungkinan) — area reversal potensial

    Args:
        df     : DataFrame dengan kolom 'Close'
        window : Rolling window untuk μ dan σ (default 20 hari)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna()
    rolling_mean = close.rolling(window=window).mean()
    rolling_std  = close.rolling(window=window).std()

    zscore = (close - rolling_mean) / rolling_std

    current_z     = float(zscore.iloc[-1])
    current_price = float(close.iloc[-1])
    current_mean  = float(rolling_mean.iloc[-1])
    current_std   = float(rolling_std.iloc[-1])

    # Probability: P(price ≥ current) berdasarkan normal distribution
    prob_above = float(norm.sf(current_z) * 100)   # Survival Function
    prob_below = float(norm.cdf(current_z) * 100)  # CDF

    # Signal
    if current_z > 2.5:
        signal = "STRONG_OVERBOUGHT"
        description = f"Harga {current_z:.2f}σ di atas rata-rata. Probabilitas reversal down: {prob_above:.1f}%"
    elif current_z > 1.5:
        signal = "OVERBOUGHT"
        description = f"Harga elevated {current_z:.2f}σ. Zona premium, pertimbangkan profit-taking."
    elif current_z < -2.5:
        signal = "STRONG_OVERSOLD"
        description = f"Harga {abs(current_z):.2f}σ di bawah rata-rata. Probabilitas reversal up: {prob_below:.1f}%"
    elif current_z < -1.5:
        signal = "OVERSOLD"
        description = f"Harga discounted {abs(current_z):.2f}σ. Zona diskon, potensi akumulasi."
    else:
        signal = "NEUTRAL"
        description = f"Harga dalam range normal ({current_z:.2f}σ dari mean)."

    # Historical Z-Score distribution (last 252 sessions)
    recent_z = zscore.dropna().tail(252)
    
    return {
        "current_zscore"    : round(current_z, 4),
        "current_price"     : current_price,
        "rolling_mean"      : round(current_mean, 4),
        "rolling_std"       : round(current_std, 4),
        "window"            : window,
        "signal"            : signal,
        "description"       : description,
        "prob_price_higher_pct": round(prob_above, 4),
        "prob_price_lower_pct" : round(prob_below, 4),
        "upper_2sigma"      : round(current_mean + 2 * current_std, 4),
        "lower_2sigma"      : round(current_mean - 2 * current_std, 4),
        "upper_3sigma"      : round(current_mean + 3 * current_std, 4),
        "lower_3sigma"      : round(current_mean - 3 * current_std, 4),
        "zscore_history"    : [round(z, 4) for z in recent_z.tolist()],
        "dates"             : df.index[-len(recent_z):].strftime('%Y-%m-%d').tolist()
    }


# ─────────────────────────────────────────────────────────────────
#  2. MONTE CARLO SIMULATION
# ─────────────────────────────────────────────────────────────────

def run_monte_carlo(
    df           : pd.DataFrame,
    days         : int   = 30,
    simulations  : int   = 10_000,
    account_size : float = 30_000,
    risk_per_trade: float = 0.02,
    confidence   : float = 0.95,
    seed         : Optional[int] = 42
) -> Dict:
    """
    Simulasi Monte Carlo untuk proyeksi harga & drawdown masa depan.

    Menggunakan Geometric Brownian Motion (GBM):
      S(t) = S(0) * exp((μ - σ²/2)t + σ√t * Z)
    Dimana Z ~ N(0,1)

    Args:
        df            : DataFrame harga historis
        days          : Berapa hari ke depan yang disimulasikan
        simulations   : Jumlah path simulasi (10,000 = standar industri)
        account_size  : Modal trading
        risk_per_trade: Persentase risiko per trade
        confidence    : Level confidence untuk VaR/CVaR
        seed          : Random seed untuk reproducibility
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    if seed is not None:
        np.random.seed(seed)

    close    = df['Close'].dropna()
    log_ret  = np.log(close / close.shift(1)).dropna()

    mu    = float(log_ret.mean())
    sigma = float(log_ret.std())

    # Jarque-Bera test → apakah distribusi normal?
    jb_stat, jb_p = jarque_bera(log_ret)
    is_normal = bool(jb_p > 0.05)

    # GBM Simulation
    S0          = float(close.iloc[-1])
    dt          = 1  # daily
    drift       = mu - 0.5 * sigma**2
    shock_mat   = np.random.normal(0, 1, (simulations, days))
    daily_ret   = np.exp(drift * dt + sigma * np.sqrt(dt) * shock_mat)

    # Build price paths
    price_paths = np.zeros((simulations, days + 1))
    price_paths[:, 0] = S0
    for d in range(1, days + 1):
        price_paths[:, d] = price_paths[:, d-1] * daily_ret[:, d-1]

    final_prices = price_paths[:, -1]

    # ── Percentile Analysis ──
    pct_5   = float(np.percentile(final_prices, 5))
    pct_25  = float(np.percentile(final_prices, 25))
    pct_50  = float(np.percentile(final_prices, 50))
    pct_75  = float(np.percentile(final_prices, 75))
    pct_95  = float(np.percentile(final_prices, 95))

    # ── Probability Analysis ──
    prob_profit  = float(np.mean(final_prices > S0) * 100)
    prob_loss_10 = float(np.mean(final_prices < S0 * 0.90) * 100)
    prob_gain_10 = float(np.mean(final_prices > S0 * 1.10) * 100)

    # ── Max Drawdown per Path ──
    running_max   = np.maximum.accumulate(price_paths, axis=1)
    drawdowns     = (price_paths - running_max) / running_max * 100
    max_drawdowns = drawdowns.min(axis=1)

    mdd_mean = float(np.mean(max_drawdowns))
    mdd_worst_5pct = float(np.percentile(max_drawdowns, 5))

    # ── Dollar-based VaR (untuk akun trading) ──
    pnl_pct   = (final_prices / S0 - 1) * 100
    var_dollar = account_size * risk_per_trade * float(np.percentile(pnl_pct, (1 - confidence) * 100)) / 100
    cvar       = account_size * risk_per_trade * float(pnl_pct[pnl_pct <= np.percentile(pnl_pct, (1-confidence)*100)].mean()) / 100

    # ── Sample Paths untuk Visualisasi (50 paths) ──
    sample_idx   = np.random.choice(simulations, 50, replace=False)
    sample_paths = price_paths[sample_idx].tolist()

    return {
        "simulation_params": {
            "simulations"     : simulations,
            "days_forward"    : days,
            "current_price"   : round(S0, 4),
            "daily_mu"        : round(mu, 6),
            "daily_sigma"     : round(sigma, 6),
            "annualized_vol"  : round(sigma * np.sqrt(252), 4),
            "return_is_normal": is_normal,
            "jarque_bera_pval": round(float(jb_p), 4)
        },
        "price_projections": {
            "worst_5pct"     : round(pct_5, 4),
            "worst_25pct"    : round(pct_25, 4),
            "median_50pct"   : round(pct_50, 4),
            "best_75pct"     : round(pct_75, 4),
            "best_5pct"      : round(pct_95, 4),
        },
        "probability_analysis": {
            "prob_profit_pct"  : round(prob_profit, 2),
            "prob_loss_10pct"  : round(prob_loss_10, 2),
            "prob_gain_10pct"  : round(prob_gain_10, 2),
        },
        "drawdown_analysis": {
            "avg_max_drawdown_pct"   : round(mdd_mean, 2),
            "worst_5pct_drawdown"    : round(mdd_worst_5pct, 2),
            "expected_max_dd_pct"    : round(mdd_mean, 2),
        },
        "risk_dollar_analysis": {
            "var_dollar"    : round(var_dollar, 2),
            "cvar_dollar"   : round(cvar, 2),
            "confidence_pct": confidence * 100,
            "account_size"  : account_size,
        },
        "sample_paths": [[round(p, 4) for p in path] for path in sample_paths]
    }


# ─────────────────────────────────────────────────────────────────
#  3. VALUE AT RISK (VaR) & CONDITIONAL VaR (CVaR / ES)
# ─────────────────────────────────────────────────────────────────

def calculate_var_cvar(
    df          : pd.DataFrame,
    confidence  : float = 0.95,
    horizon_days: int   = 1,
    method      : str   = "parametric"
) -> Dict:
    """
    Hitung VaR dan CVaR (Expected Shortfall) dengan dua metode.

    Args:
        confidence   : Level confidence (default 0.95 = 95%)
        horizon_days : Horizon waktu (1 hari, 5 hari, dll)
        method       : 'parametric' (asumsi normal) atau 'historical'
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna()
    log_ret = np.log(close / close.shift(1)).dropna()

    if method == "parametric":
        mu    = float(log_ret.mean())
        sigma = float(log_ret.std())
        # Scale ke horizon
        mu_h    = mu * horizon_days
        sigma_h = sigma * np.sqrt(horizon_days)
        # VaR
        var_pct = float(-norm.ppf(1 - confidence, mu_h, sigma_h) * 100)
        # CVaR (Expected Shortfall): E[loss | loss > VaR]
        cvar_pct = float(-(norm.pdf(norm.ppf(1 - confidence)) / (1 - confidence)) * sigma_h * 100)

    else:  # Historical Simulation
        scaled   = log_ret.values * np.sqrt(horizon_days)
        var_pct  = float(-np.percentile(scaled, (1 - confidence) * 100) * 100)
        tail     = scaled[scaled <= np.percentile(scaled, (1 - confidence) * 100)]
        cvar_pct = float(-tail.mean() * 100) if len(tail) > 0 else var_pct

    return {
        "method"          : method,
        "confidence_pct"  : confidence * 100,
        "horizon_days"    : horizon_days,
        "var_pct"         : round(var_pct, 4),
        "cvar_pct"        : round(cvar_pct, 4),
        "var_description" : f"Dalam {horizon_days} hari ke depan, kerugian tidak akan melebihi {var_pct:.2f}% dengan probabilitas {confidence*100:.0f}%.",
        "cvar_description": f"Jika VaR terlampaui, rata-rata kerugian yang diharapkan adalah {cvar_pct:.2f}% (Expected Shortfall).",
        "return_skewness" : round(float(skew(log_ret)), 4),
        "return_kurtosis" : round(float(kurtosis(log_ret)), 4),  # excess kurtosis
        "fat_tails_warning": bool(kurtosis(log_ret) > 1.5)
    }


# ─────────────────────────────────────────────────────────────────
#  4. MARKET REGIME DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_market_regime(df: pd.DataFrame) -> Dict:
    """
    Deteksi apakah market sedang Trending, Ranging, atau Volatile
    menggunakan ADX equivalent dan Hurst Exponent.

    Hurst Exponent (H):
      H > 0.55 → Trending (Mean-Aversion)
      H ≈ 0.50 → Random Walk (Sideways/Efficient)
      H < 0.45 → Mean-Reverting (Range-bound)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna()
    log_ret = np.log(close / close.shift(1)).dropna()

    # ── Hurst Exponent via R/S Analysis ──
    hurst = _calculate_hurst(close.values)

    # ── Volatility Regime ──
    realized_vol_30 = float(log_ret.tail(30).std() * np.sqrt(252) * 100)
    realized_vol_90 = float(log_ret.tail(90).std() * np.sqrt(252) * 100) if len(log_ret) >= 90 else realized_vol_30
    vol_regime = "HIGH" if realized_vol_30 > 40 else "MEDIUM" if realized_vol_30 > 20 else "LOW"

    # ── Trend Strength via EMA separation ──
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()
    trend_strength_pct = float(((ema20.iloc[-1] - ema50.iloc[-1]) / ema50.iloc[-1]) * 100)

    if hurst > 0.6:
        regime = "STRONG_TREND"
        regime_desc = "Market sedang dalam tren kuat. Strategi trend-following lebih efektif."
    elif hurst > 0.53:
        regime = "TRENDING"
        regime_desc = "Market cenderung trending. Gunakan pullback untuk entry."
    elif hurst > 0.47:
        regime = "RANDOM_WALK"
        regime_desc = "Market efisien/sideways. Tidak ada edge yang jelas."
    else:
        regime = "MEAN_REVERTING"
        regime_desc = "Market mean-reverting. Strategi range trading / counter-trend lebih efektif."

    return {
        "hurst_exponent"      : round(hurst, 4),
        "market_regime"       : regime,
        "regime_description"  : regime_desc,
        "vol_30d_annualized"  : round(realized_vol_30, 2),
        "vol_90d_annualized"  : round(realized_vol_90, 2),
        "volatility_regime"   : vol_regime,
        "vol_ratio_30_90"     : round(realized_vol_30 / realized_vol_90, 3) if realized_vol_90 > 0 else 1.0,
        "ema20_vs_ema50_pct"  : round(trend_strength_pct, 4),
        "trend_direction"     : "BULLISH" if trend_strength_pct > 0 else "BEARISH"
    }


# ─────────────────────────────────────────────────────────────────
#  5. FULL STATISTICAL SUMMARY
# ─────────────────────────────────────────────────────────────────

def get_full_statistics(df: pd.DataFrame, account_size: float = 30_000) -> Dict:
    """
    One-call function: Jalankan semua analisis statistik sekaligus.
    """
    return {
        "zscore"       : calculate_zscore_analysis(df),
        "var_cvar"     : calculate_var_cvar(df, method="historical"),
        "monte_carlo"  : run_monte_carlo(df, days=30, simulations=5000, account_size=account_size),
        "regime"       : detect_market_regime(df)
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _calculate_hurst(prices: np.ndarray) -> float:
    """
    Hitung Hurst Exponent via Rescaled Range (R/S) Analysis.
    Algoritma: Peters (1994)
    """
    try:
        n = len(prices)
        if n < 20:
            return 0.5

        log_ret = np.log(prices[1:] / prices[:-1])
        lags    = range(10, min(n // 2, 100), 5)
        rs_list = []
        lag_list = []

        for lag in lags:
            sub = log_ret[:lag]
            mean_adj = sub - sub.mean()
            cumsum   = np.cumsum(mean_adj)
            R        = cumsum.max() - cumsum.min()
            S        = sub.std()
            if S > 0 and R > 0:
                rs_list.append(np.log(R / S))
                lag_list.append(np.log(lag))

        if len(rs_list) < 2:
            return 0.5

        # OLS regression: log(R/S) = H * log(n) + C
        hurst = np.polyfit(lag_list, rs_list, 1)[0]
        return float(np.clip(hurst, 0, 1))
    except Exception:
        return 0.5