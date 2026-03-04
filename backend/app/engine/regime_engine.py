"""
╔══════════════════════════════════════════════════════════════════╗
║         APEX MARKET REGIME INTELLIGENCE ENGINE v1.0             ║
║  HMM · Vol Clustering · Liquidity Regime · Macro Tagging        ║
╚══════════════════════════════════════════════════════════════════╝

Layer 1 — INSTITUTIONAL GRADE
Quant funds tidak pernah pakai satu model untuk semua kondisi.
Mereka switch model berdasarkan regime.

Komponen:
  1. HMM Regime Detection        → State tersembunyi dari return distribution
  2. GARCH Volatility Clustering → Vol regime: calma/normal/crisis
  3. Liquidity Regime            → Bid-ask proxy + volume-price divergence
  4. Macro Tagging               → Risk-On / Risk-Off berdasarkan cross-asset
  5. Composite Regime Score      → Output tunggal yang bisa dikonsumsi engine lain
"""

import numpy as np
import pandas as pd
from scipy.stats import norm, jarque_bera
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────
#  1. HMM REGIME DETECTION (Pure NumPy — tanpa library HMM)
#     Implementasi Baum-Welch via EM sederhana
# ─────────────────────────────────────────────────────────────────

def detect_hmm_regime(df: pd.DataFrame, n_states: int = 3, n_iter: int = 80) -> Dict:
    """
    Hidden Markov Model untuk deteksi regime pasar tersembunyi.
    Diimplementasikan via Expectation-Maximization (EM) tanpa dependency hmmlearn.

    3 State Default:
      State 0 → HIGH_VOL_BEARISH  (mean return negatif, vol tinggi)
      State 1 → LOW_VOL_BULLISH   (mean return positif, vol rendah)
      State 2 → SIDEWAYS_CHOP     (mean ~0, vol medium)

    Returns:
      current_regime, confidence_pct, state_probabilities, regime_history
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna().values.astype(float)
    returns = np.diff(np.log(close))
    T       = len(returns)

    if T < 30:
        return {"error": "Minimal 30 data points untuk HMM"}

    # ── Inisialisasi parameter HMM ──────────────────────────────
    rng = np.random.default_rng(42)
    # Cluster awal via k-means sederhana (percentile-based)
    pct_low  = np.percentile(returns, 33)
    pct_high = np.percentile(returns, 66)

    # Initial means & variances per state
    mask_bear = returns <= pct_low
    mask_bull = returns >= pct_high
    mask_side = ~mask_bear & ~mask_bull

    means = np.array([
        returns[mask_bear].mean() if mask_bear.any() else -0.01,
        returns[mask_bull].mean() if mask_bull.any() else  0.01,
        returns[mask_side].mean() if mask_side.any() else  0.00
    ])
    vars_ = np.array([
        max(returns[mask_bear].var(), 1e-6) if mask_bear.any() else 0.01,
        max(returns[mask_bull].var(), 1e-6) if mask_bull.any() else 0.005,
        max(returns[mask_side].var(), 1e-6) if mask_side.any() else 0.007
    ])

    # Transition matrix (uniform start)
    A = np.full((n_states, n_states), 1.0 / n_states)
    # Initial state distribution
    pi = np.full(n_states, 1.0 / n_states)

    def _gaussian_pdf(x, mu, var):
        return norm.pdf(x, loc=mu, scale=np.sqrt(max(var, 1e-10)))

    # ── EM Loop ─────────────────────────────────────────────────
    for _ in range(n_iter):
        # E-Step: Forward-Backward
        B = np.column_stack([_gaussian_pdf(returns, means[s], vars_[s]) for s in range(n_states)])
        B = np.clip(B, 1e-300, None)

        # Forward
        alpha = np.zeros((T, n_states))
        alpha[0] = pi * B[0]
        alpha[0] /= alpha[0].sum() + 1e-300
        for t in range(1, T):
            alpha[t] = (alpha[t-1] @ A) * B[t]
            alpha[t] /= alpha[t].sum() + 1e-300

        # Backward
        beta = np.ones((T, n_states))
        for t in range(T - 2, -1, -1):
            for i in range(n_states):
                beta[t, i] = np.sum(A[i, :] * B[t+1, :] * beta[t+1, :])
            beta[t] /= beta[t].sum() + 1e-300

        # Gamma (posterior state probabilities)
        gamma = alpha * beta
        gamma /= gamma.sum(axis=1, keepdims=True) + 1e-300

        # Xi (joint state transition probabilities)
        xi = np.zeros((T-1, n_states, n_states))
        for t in range(T - 1):
            xi[t] = (alpha[t:t+1].T * A * B[t+1] * beta[t+1])
            xi[t] /= xi[t].sum() + 1e-300

        # M-Step: Update parameters
        pi      = gamma[0] / gamma[0].sum()
        A       = xi.sum(axis=0) / xi.sum(axis=0).sum(axis=1, keepdims=True).clip(1e-300)
        means   = (gamma * returns[:, None]).sum(axis=0) / gamma.sum(axis=0).clip(1e-300)
        vars_   = (gamma * (returns[:, None] - means)**2).sum(axis=0) / gamma.sum(axis=0).clip(1e-300)
        vars_   = np.clip(vars_, 1e-8, None)

    # ── Classify States ─────────────────────────────────────────
    # Sort by mean: index 0 = paling bearish, index 2 = paling bullish
    order  = np.argsort(means)
    labels = {order[0]: "HIGH_VOL_BEARISH", order[1]: "SIDEWAYS_CHOP", order[2]: "LOW_VOL_BULLISH"}

    current_state  = int(np.argmax(gamma[-1]))
    current_regime = labels[current_state]
    confidence_pct = float(gamma[-1, current_state] * 100)

    # Regime history (last 60 data points)
    regime_hist = [labels[int(np.argmax(gamma[t]))] for t in range(max(0, T-60), T)]

    # Persistence: berapa lama di regime saat ini
    current_streak = 1
    for i in range(len(regime_hist) - 2, -1, -1):
        if regime_hist[i] == current_regime:
            current_streak += 1
        else:
            break

    return {
        "current_regime"       : current_regime,
        "confidence_pct"       : round(confidence_pct, 2),
        "state_probs"          : {labels[s]: round(float(gamma[-1, s]) * 100, 2) for s in range(n_states)},
        "regime_history_60"    : regime_hist,
        "regime_persistence_days": current_streak,
        "state_means_annualized": {labels[s]: round(float(means[s]) * 252 * 100, 4) for s in range(n_states)},
        "state_vols_annualized" : {labels[s]: round(float(np.sqrt(vars_[s]) * np.sqrt(252)) * 100, 4) for s in range(n_states)},
        "model_type"           : "Gaussian HMM (EM)",
    }


# ─────────────────────────────────────────────────────────────────
#  2. GARCH VOLATILITY CLUSTERING
#     GARCH(1,1): σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
# ─────────────────────────────────────────────────────────────────

def detect_vol_clustering(df: pd.DataFrame) -> Dict:
    """
    Deteksi volatility clustering dengan GARCH(1,1) sederhana.
    GARCH efektif untuk identifikasi apakah market sedang di fase
    'calm before storm' atau 'crisis propagation'.

    Vol Regimes:
      ULTRA_LOW  → Percentile < 10%  (Calmest period, risk of VIX spike)
      LOW        → Percentile 10-30%
      NORMAL     → Percentile 30-70%
      HIGH       → Percentile 70-90%
      CRISIS     → Percentile > 90%  (Correlation breakdown, fat tails)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna().values.astype(float)
    returns = np.diff(np.log(close))
    T       = len(returns)

    if T < 20:
        return {"error": "Minimal 20 data"}

    # ── GARCH(1,1) via simple moment estimation ──────────────────
    mu      = returns.mean()
    eps     = returns - mu
    var_unc = eps.var()  # unconditional variance

    # Simplified GARCH(1,1): moment-matching from squared-residual autocorrelation
    eps2    = eps ** 2
    ac1     = float(pd.Series(eps2).autocorr(lag=1)) if T > 2 else 0.3
    ac1     = max(0.01, min(ac1, 0.98))  # clamp to valid range

    # Moment-matching: ac1 ≈ α + β for GARCH(1,1)
    # Split persistence into α (shock) and β (memory) via kurtosis proxy
    persistence = min(ac1, 0.98)   # stability constraint: α + β < 1
    kurt_ratio  = float(pd.Series(eps2).autocorr(lag=2)) / max(ac1, 0.01)
    kurt_ratio  = max(0.05, min(kurt_ratio, 0.95))
    alpha   = persistence * (1 - kurt_ratio)
    beta    = persistence * kurt_ratio
    omega   = max(var_unc * (1 - alpha - beta), 1e-10)

    # Propagate conditional variance
    sigma2  = np.zeros(T)
    sigma2[0] = var_unc
    for t in range(1, T):
        sigma2[t] = omega + alpha * eps[t-1]**2 + beta * sigma2[t-1]

    current_vol_daily = float(np.sqrt(sigma2[-1]))
    current_vol_ann   = current_vol_daily * np.sqrt(252) * 100

    # Historical percentile
    all_vol_ann = np.sqrt(sigma2) * np.sqrt(252) * 100
    pct_rank    = float((all_vol_ann < current_vol_ann).mean() * 100)

    # Regime classification
    if pct_rank < 10:
        vol_regime = "ULTRA_LOW"
        vol_desc   = "Volatilitas terendah secara historis. Potensi volatility spike signifikan."
        risk_implication = "COMPLACENCY_RISK"
    elif pct_rank < 30:
        vol_regime = "LOW"
        vol_desc   = "Volatilitas di bawah rata-rata. Kondisi pasar tenang."
        risk_implication = "CARRY_FAVORABLE"
    elif pct_rank < 70:
        vol_regime = "NORMAL"
        vol_desc   = "Volatilitas dalam range historis normal."
        risk_implication = "STANDARD_SIZING"
    elif pct_rank < 90:
        vol_regime = "HIGH"
        vol_desc   = "Volatilitas elevated. Kurangi position size 30-50%."
        risk_implication = "REDUCE_EXPOSURE"
    else:
        vol_regime = "CRISIS"
        vol_desc   = "Volatilitas di level tertinggi. Korelasi breakdown mungkin terjadi."
        risk_implication = "DEFENSIVE_MODE"

    # Vol of Vol (second moment)
    vol_of_vol = float(np.std(np.sqrt(sigma2)) * np.sqrt(252) * 100)

    # Jarque-Bera: fat tails?
    jb_stat, jb_pval = jarque_bera(returns)
    has_fat_tails = bool(jb_pval < 0.05)

    return {
        "current_vol_daily_pct" : round(current_vol_daily * 100, 4),
        "current_vol_annual_pct": round(current_vol_ann, 4),
        "vol_percentile_rank"   : round(pct_rank, 2),
        "vol_regime"            : vol_regime,
        "vol_description"       : vol_desc,
        "risk_implication"      : risk_implication,
        "vol_of_vol_annual_pct" : round(vol_of_vol, 4),
        "garch_alpha"           : round(alpha, 4),
        "garch_beta"            : round(beta, 4),
        "garch_persistence"     : round(alpha + beta, 4),
        "has_fat_tails"         : has_fat_tails,
        "fat_tails_jb_pval"     : round(float(jb_pval), 4),
        "sizing_multiplier"     : _vol_regime_to_sizing_mult(vol_regime),
        "model_type"            : "GARCH(1,1) Moment Estimation"
    }


# ─────────────────────────────────────────────────────────────────
#  3. LIQUIDITY REGIME DETECTOR
# ─────────────────────────────────────────────────────────────────

def detect_liquidity_regime(df: pd.DataFrame) -> Dict:
    """
    Identifikasi apakah likuiditas pasar sedang ABUNDANT, NORMAL, atau STRESSED.

    Proxy Likuiditas (tanpa bid-ask data):
      1. Amihud Illiquidity Ratio = |Return| / Volume (semakin tinggi = semakin illiquid)
      2. Volume-Price Divergence = harga naik tapi volume turun = distribusi terselubung
      3. Turnover Rate Trend = normalisasi volume terhadap rolling average
    """
    required = {'Close', 'Volume'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data Close + Volume diperlukan"}

    close  = df['Close'].dropna()
    volume = df['Volume'].dropna()
    ret    = close.pct_change().dropna()

    # Sejajarkan
    common = close.index.intersection(volume.index).intersection(ret.index)
    close  = close.loc[common]
    volume = volume.loc[common]
    ret    = ret.loc[common]

    # 1. Amihud Illiquidity Ratio (annualized basis)
    amihud = (ret.abs() / volume.replace(0, np.nan)).dropna()
    amihud_current = float(amihud.iloc[-1])
    amihud_mean    = float(amihud.mean())
    amihud_pct     = float((amihud < amihud_current).mean() * 100)

    # 2. Volume-Price Divergence (30-day window)
    vol_ma  = volume.rolling(30).mean()
    price_trend = close.pct_change(20)  # 20-day momentum
    vol_ratio   = (volume / vol_ma.replace(0, np.nan)).iloc[-1]
    price_trend_now = float(price_trend.iloc[-1])
    divergence  = bool(price_trend_now > 0 and float(vol_ratio) < 0.8)  # Price up, vol weak

    # 3. Turnover Trend (normalized)
    vol_z = (volume - volume.rolling(20).mean()) / volume.rolling(20).std().replace(0, np.nan)
    vol_z_current = float(vol_z.iloc[-1]) if not pd.isna(vol_z.iloc[-1]) else 0.0

    # Composite Liquidity Score (0-100, higher = more liquid)
    # Z-score normalized: combine Amihud percentile rank (inverted) with volume z-score
    amihud_z = (50 - amihud_pct) / 50   # [-1, 1]; higher = more liquid
    vol_z_clipped = max(-3, min(vol_z_current, 3)) / 3  # [-1, 1]; higher = more volume
    liq_score = max(0, min(100, 50 + 25 * amihud_z + 25 * vol_z_clipped))

    if liq_score > 65:
        liq_regime = "ABUNDANT"
        liq_desc   = "Likuiditas sangat baik. Market depth tinggi, slippage minimal."
    elif liq_score > 40:
        liq_regime = "NORMAL"
        liq_desc   = "Likuiditas dalam kondisi normal."
    elif liq_score > 20:
        liq_regime = "THIN"
        liq_desc   = "Likuiditas mulai menipis. Waspadai slippage dan gap."
    else:
        liq_regime = "STRESSED"
        liq_desc   = "Likuiditas KRITIS. Risiko slippage ekstrem dan forced liquidation."

    return {
        "liquidity_regime"      : liq_regime,
        "liquidity_score"       : round(liq_score, 2),
        "liquidity_description" : liq_desc,
        "amihud_illiquidity"    : round(amihud_current, 10),
        "amihud_percentile"     : round(amihud_pct, 2),
        "volume_z_score"        : round(vol_z_current, 4),
        "volume_vs_30d_avg_pct" : round((float(vol_ratio) - 1) * 100, 2) if not pd.isna(vol_ratio) else 0,
        "price_vol_divergence"  : divergence,
        "divergence_warning"    : "⚠️ Volume melemah saat harga naik — distribusi institusi potensial." if divergence else "OK"
    }


# ─────────────────────────────────────────────────────────────────
#  4. MACRO REGIME TAGGER (Risk-On / Risk-Off)
# ─────────────────────────────────────────────────────────────────

def tag_macro_regime(cross_asset_data: Dict) -> Dict:
    """
    Tentukan macro regime berdasarkan sinyal cross-asset.
    Input: output dari get_cross_asset_data() di macro_engine.py

    Logic Institusional:
      RISK_ON:  DXY turun + Nasdaq naik + Gold stabil
      RISK_OFF: DXY naik  + Nasdaq turun + Gold naik
      STAGFLATION: DXY naik + Nasdaq turun + Gold naik tinggi
      CONFUSED: Sinyal kontradiktif
    """
    dxy    = cross_asset_data.get("DXY", {})
    nasdaq = cross_asset_data.get("NASDAQ", {})
    gold   = cross_asset_data.get("GOLD", {})

    dxy_chg    = dxy.get("change_pct", 0)
    nasdaq_chg = nasdaq.get("change_pct", 0)
    gold_chg   = gold.get("change_pct", 0)

    # Score sistem: +1 = risk-on signal, -1 = risk-off signal
    score = 0
    reasons = []

    if dxy_chg < -0.3:
        score += 1; reasons.append(f"DXY turun {dxy_chg:.2f}% → Dollar melemah = likuiditas global bertambah")
    elif dxy_chg > 0.3:
        score -= 1; reasons.append(f"DXY naik {dxy_chg:.2f}% → Dollar menguat = likuiditas global menyusut")

    if nasdaq_chg > 0.5:
        score += 1; reasons.append(f"Nasdaq +{nasdaq_chg:.2f}% → Risk appetite tinggi, tech/growth outperform")
    elif nasdaq_chg < -0.5:
        score -= 1; reasons.append(f"Nasdaq {nasdaq_chg:.2f}% → Risk aversion, tech/growth dijual")

    if gold_chg > 1.0:
        score -= 1; reasons.append(f"Gold +{gold_chg:.2f}% → Safe haven demand tinggi, fear elevated")
    elif gold_chg < -0.5:
        score += 1; reasons.append(f"Gold {gold_chg:.2f}% → Safe haven demand turun, risk appetite naik")

    # Classification
    if score >= 2:
        macro_regime = "RISK_ON"
        macro_desc   = "Lingkungan RISK-ON. Crypto dan growth assets historically outperform."
        crypto_bias  = "BULLISH"
    elif score <= -2:
        macro_regime = "RISK_OFF"
        macro_desc   = "Lingkungan RISK-OFF. Safe haven (Gold, bonds, USD) outperform."
        crypto_bias  = "BEARISH"
    elif score == 1:
        macro_regime = "MILD_RISK_ON"
        macro_desc   = "Bias RISK-ON lemah. Sinyal campuran, selektivitas tinggi diperlukan."
        crypto_bias  = "CAUTIOUSLY_BULLISH"
    elif score == -1:
        macro_regime = "MILD_RISK_OFF"
        macro_desc   = "Bias RISK-OFF lemah. Waspadai rotasi ke defensive assets."
        crypto_bias  = "CAUTIOUSLY_BEARISH"
    else:
        macro_regime = "CONFUSED"
        macro_desc   = "Sinyal makro kontradiktif. Tidak ada edge yang jelas dari cross-asset."
        crypto_bias  = "NEUTRAL"

    # Stagflation check
    if dxy_chg > 0.5 and gold_chg > 1.5 and nasdaq_chg < -0.5:
        macro_regime = "STAGFLATION_RISK"
        macro_desc   = "Stagflation signal! DXY menguat + Gold naik tajam + Nasdaq turun."
        crypto_bias  = "HIGHLY_BEARISH"

    return {
        "macro_regime"     : macro_regime,
        "macro_description": macro_desc,
        "crypto_bias"      : crypto_bias,
        "composite_score"  : score,
        "max_score"        : 3,
        "reasoning"        : reasons,
        "cross_asset"      : {
            "DXY_change_pct"   : round(dxy_chg, 4),
            "NASDAQ_change_pct": round(nasdaq_chg, 4),
            "GOLD_change_pct"  : round(gold_chg, 4)
        }
    }


# ─────────────────────────────────────────────────────────────────
#  5. COMPOSITE REGIME ENGINE — SEMUA DALAM SATU OUTPUT
# ─────────────────────────────────────────────────────────────────

def get_full_regime_analysis(df: pd.DataFrame, cross_asset_data: Optional[Dict] = None) -> Dict:
    """
    Composite regime analysis: gabungkan HMM + GARCH + Liquidity + Macro.
    Output berupa SATU rekomendasi model yang harus digunakan.

    Model Switching Rule (Institutional Standard):
      TRENDING + LOW_VOL  → Trend-Following Models (EMA, Momentum)
      SIDEWAYS + NORMAL   → Mean-Reversion Models (RSI, Bollinger)
      CRISIS + HIGH_VOL   → Volatility Breakout / Cash preservation
      RISK_OFF + HIGH_VOL → Defensive: Reduce ALL exposure
    """
    hmm_result  = detect_hmm_regime(df)
    garch_result = detect_vol_clustering(df)
    liq_result  = detect_liquidity_regime(df)

    hmm_regime  = hmm_result.get("current_regime", "UNKNOWN")
    vol_regime  = garch_result.get("vol_regime", "UNKNOWN")
    liq_regime  = liq_result.get("liquidity_regime", "UNKNOWN")

    macro_result = tag_macro_regime(cross_asset_data) if cross_asset_data else {"macro_regime": "UNKNOWN", "crypto_bias": "NEUTRAL"}
    macro_regime = macro_result.get("macro_regime", "UNKNOWN")

    # ── Active Model Selector ────────────────────────────────────
    if vol_regime == "CRISIS" or liq_regime == "STRESSED":
        active_model   = "CASH_PRESERVATION"
        model_logic    = "Vol atau likuiditas dalam kondisi KRISIS. Tidak ada model yang reliabel. Preserve capital."
        sizing_factor  = 0.0
    elif macro_regime in ("RISK_OFF", "STAGFLATION_RISK"):
        active_model   = "DEFENSIVE_HEDGE"
        model_logic    = "Macro RISK-OFF terkonfirmasi. Kurangi semua exposure, hedge jika memungkinkan."
        sizing_factor  = 0.25
    elif hmm_regime == "LOW_VOL_BULLISH" and vol_regime in ("LOW", "NORMAL") and macro_regime in ("RISK_ON", "MILD_RISK_ON"):
        active_model   = "TREND_FOLLOWING"
        model_logic    = "HMM bullish, vol normal, macro risk-on. Momentum & trend strategies optimal."
        sizing_factor  = 1.0
    elif hmm_regime == "SIDEWAYS_CHOP" and vol_regime == "NORMAL":
        active_model   = "MEAN_REVERSION"
        model_logic    = "Market chop. Mean reversion dan range trading strategies optimal."
        sizing_factor  = 0.75
    elif hmm_regime == "HIGH_VOL_BEARISH" and vol_regime == "HIGH":
        active_model   = "VOLATILITY_BREAKOUT"
        model_logic    = "Regime bearish + vol tinggi. Strategi volatility breakout atau short-biased."
        sizing_factor  = 0.5
    else:
        active_model   = "SELECTIVE_DISCRETIONARY"
        model_logic    = "Sinyal mixed. Gunakan diskrasi ketat, size kecil, konfirmasi multi-timeframe."
        sizing_factor  = 0.5

    # ── Overall Risk Mode ────────────────────────────────────────
    risk_factors = sum([
        vol_regime in ("HIGH", "CRISIS"),
        liq_regime in ("THIN", "STRESSED"),
        hmm_regime == "HIGH_VOL_BEARISH",
        macro_regime in ("RISK_OFF", "STAGFLATION_RISK")
    ])

    if risk_factors == 0:
        risk_mode = "OFFENSIVE"
    elif risk_factors == 1:
        risk_mode = "STANDARD"
    elif risk_factors == 2:
        risk_mode = "DEFENSIVE"
    else:
        risk_mode = "PRESERVATION"

    return {
        "composite_regime": {
            "hmm_regime"   : hmm_regime,
            "hmm_confidence": hmm_result.get("confidence_pct", 0),
            "vol_regime"   : vol_regime,
            "liq_regime"   : liq_regime,
            "macro_regime" : macro_regime,
        },
        "active_model"     : active_model,
        "model_logic"      : model_logic,
        "risk_mode"        : risk_mode,
        "sizing_factor"    : sizing_factor,
        "risk_factor_count": risk_factors,
        "hmm_details"      : hmm_result,
        "garch_details"    : garch_result,
        "liquidity_details": liq_result,
        "macro_details"    : macro_result,
        "regime_summary"   : f"[{hmm_regime}] Vol:{vol_regime} | Liq:{liq_regime} | Macro:{macro_regime} → {active_model}"
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _vol_regime_to_sizing_mult(vol_regime: str) -> float:
    """Translate vol regime ke position sizing multiplier."""
    mapping = {
        "ULTRA_LOW": 1.25,  # Hati-hati: low vol = complacency risk
        "LOW"      : 1.0,
        "NORMAL"   : 1.0,
        "HIGH"     : 0.5,
        "CRISIS"   : 0.0
    }
    return mapping.get(vol_regime, 0.5)
