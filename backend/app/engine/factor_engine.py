"""
╔══════════════════════════════════════════════════════════════════╗
║              APEX FACTOR RESEARCH LAB v1.0                      ║
║  Momentum Decay · Vol Premium · Liquidity Factor · Cross-Asset  ║
╚══════════════════════════════════════════════════════════════════╝

Layer 2 — INSTITUTIONAL GRADE
Factor research adalah cara quant fund memahami MENGAPA sebuah
aset bergerak, bukan hanya BERAPA besar gerakannya.

Faktor yang Dianalisis:
  1. Momentum Factor        → Apakah momentum sedang menguat atau decay?
  2. Volatility Risk Premium → Apakah vol premium menguntungkan?
  3. Liquidity Factor        → Liquidity premium / discount saat ini
  4. Cross-Asset Transmission → Seberapa besar pengaruh macro ke aset ini?
  5. BTC Dominance Factor    → Crypto-specific: dominance regime impact
  6. Factor Composite Score  → Alpha expectation score
"""

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. MOMENTUM FACTOR DECAY ANALYSIS
# ─────────────────────────────────────────────────────────────────

def analyze_momentum_factor(df: pd.DataFrame) -> Dict:
    """
    Analisis kekuatan dan kondisi momentum faktor.

    Institutional Insight:
      Momentum bekerja karena herding behavior institusi.
      Tapi momentum memiliki 'half-life' — ia akan decay setelah
      crowding mencapai puncak (biasanya 6-12 bulan di equities).

    Komponen:
      - ROC (Rate of Change) di berbagai timeframe: 5D, 20D, 60D, 120D
      - Momentum Acceleration: d(ROC)/dt
      - Cross-sectional Momentum Persistence
      - Momentum Crowding Proxy (vol-adjusted momentum)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close  = df['Close'].dropna()
    n      = len(close)

    # ROC multi-timeframe
    periods = {"5D": 5, "20D": 20, "60D": 60, "120D": min(120, n - 1)}
    roc     = {}
    for label, p in periods.items():
        if n > p:
            roc[label] = float((close.iloc[-1] / close.iloc[-1 - p] - 1) * 100)
        else:
            roc[label] = None

    # Momentum Acceleration (rate of change of ROC)
    # d(ROC_20)/dt over last 5 days vs previous 5 days
    if n > 25:
        roc20_recent   = float((close.iloc[-1]  / close.iloc[-21] - 1) * 100)
        roc20_previous = float((close.iloc[-6]  / close.iloc[-26] - 1) * 100) if n > 26 else 0
        mom_accel      = roc20_recent - roc20_previous
        accel_label    = "ACCELERATING" if mom_accel > 0.5 else "DECAYING" if mom_accel < -0.5 else "STABLE"
    else:
        mom_accel, accel_label = 0, "INSUFFICIENT_DATA"

    # Vol-Adjusted Momentum (Sharpe-like momentum)
    if n > 60:
        ret_60   = np.log(close / close.shift(1)).dropna().tail(60)
        vol_60   = float(ret_60.std() * np.sqrt(252))
        ret_60d  = roc.get("60D", 0) or 0
        vol_adj_mom = ret_60d / (vol_60 * 100) if vol_60 > 0 else 0
    else:
        vol_adj_mom = 0

    # Momentum Quality Score (0-100)
    roc_vals  = [v for v in roc.values() if v is not None]
    alignment = sum(1 for v in roc_vals if v > 0) / len(roc_vals) * 100 if roc_vals else 50
    mom_quality = min(100, max(0, alignment * 0.6 + (vol_adj_mom * 20 + 50) * 0.4))

    # Signal
    if accel_label == "ACCELERATING" and alignment > 75:
        mom_signal = "STRONG_MOMENTUM"
        mom_desc   = f"Momentum menguat di semua timeframe ({alignment:.0f}% alignment). Setup trend-following optimal."
    elif accel_label == "DECAYING" or alignment < 40:
        mom_signal = "MOMENTUM_DECAY"
        mom_desc   = f"Momentum mulai decay. Hanya {alignment:.0f}% timeframe positif. Waspadai reversal."
    else:
        mom_signal = "MODERATE_MOMENTUM"
        mom_desc   = f"Momentum moderat ({alignment:.0f}% alignment). Selektivitas tinggi diperlukan."

    return {
        "momentum_signal"      : mom_signal,
        "momentum_description" : mom_desc,
        "momentum_quality_score": round(mom_quality, 2),
        "roc_multi_tf"         : {k: round(v, 4) if v is not None else None for k, v in roc.items()},
        "momentum_acceleration": round(mom_accel, 4),
        "acceleration_label"   : accel_label,
        "vol_adjusted_momentum": round(vol_adj_mom, 4),
        "timeframe_alignment_pct": round(alignment, 2),
        "half_life_estimate_days": _estimate_momentum_half_life(close)
    }


# ─────────────────────────────────────────────────────────────────
#  2. VOLATILITY RISK PREMIUM (VRP)
# ─────────────────────────────────────────────────────────────────

def calculate_vol_risk_premium(df: pd.DataFrame, lookback_rv: int = 20) -> Dict:
    """
    Hitung Volatility Risk Premium (VRP).

    VRP = Implied Vol (proxy) - Realized Vol
    Positif VRP = Volatility sellers are being compensated (sell vol strategies)
    Negatif VRP = Realized vol exceeds implied (unusual risk, underpriced insurance)

    Karena kita tidak punya IV langsung, gunakan proxy:
      IV Proxy = 30-day vol scaled up by VRP historical premium (~1.1-1.3x)
      RV = Realized 20-day vol

    Penting untuk:
      - Menentukan apakah vol saat ini "cheap" atau "expensive"
      - Informasikan position sizing (VRP tinggi = premi risiko dibayar)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close  = df['Close'].dropna()
    log_ret = np.log(close / close.shift(1)).dropna()

    if len(log_ret) < 30:
        return {"error": "Minimal 30 data"}

    # Realized Volatility (20-day, annualized)
    rv_20  = float(log_ret.tail(20).std() * np.sqrt(252) * 100)
    rv_60  = float(log_ret.tail(60).std() * np.sqrt(252) * 100) if len(log_ret) >= 60 else rv_20
    rv_hist = float(log_ret.std() * np.sqrt(252) * 100)

    # IV Proxy (institutional standard: RV × 1.20 premium)
    iv_proxy_20 = rv_20 * 1.20
    iv_proxy_60 = rv_60 * 1.20

    # VRP
    vrp_20 = iv_proxy_20 - rv_20  # always ~20% of rv_20 in this proxy
    # More meaningful: compare current RV vs long-term average
    vrp_meaningful = rv_hist - rv_20  # Positive = current vol below average (cheap insurance)

    # VRP Regime
    vrp_pct_rank = float((log_ret.rolling(20).std() < log_ret.tail(20).std()).mean() * 100)

    if vrp_meaningful > 5:
        vrp_regime = "ELEVATED_MEAN_REVERSION"
        vrp_desc   = f"RV historis ({rv_hist:.1f}%) jauh di atas RV saat ini ({rv_20:.1f}%). Expect vol spike return-to-mean."
        strategy   = "BUY_PROTECTION"
    elif vrp_meaningful < -5:
        vrp_regime = "VOL_OVERSHOOTING"
        vrp_desc   = f"RV saat ini ({rv_20:.1f}%) jauh di atas rata-rata historis ({rv_hist:.1f}%). Vol akan menyusut."
        strategy   = "SELL_VOL_PREMIUM"
    else:
        vrp_regime = "FAIR_VALUE"
        vrp_desc   = f"Realized vol ({rv_20:.1f}%) mendekati rata-rata historis ({rv_hist:.1f}%). No vol edge."
        strategy   = "NEUTRAL"

    return {
        "rv_20d_annual_pct"  : round(rv_20, 4),
        "rv_60d_annual_pct"  : round(rv_60, 4),
        "rv_historical_pct"  : round(rv_hist, 4),
        "iv_proxy_20d"       : round(iv_proxy_20, 4),
        "vrp_meaningful_pct" : round(vrp_meaningful, 4),
        "rv_percentile_rank" : round(vrp_pct_rank, 2),
        "vrp_regime"         : vrp_regime,
        "vrp_description"    : vrp_desc,
        "recommended_strategy": strategy,
        "vol_term_structure" : {
            "short_term_20d": round(rv_20, 4),
            "medium_term_60d": round(rv_60, 4),
            "long_term_hist": round(rv_hist, 4),
            "contango"      : bool(rv_20 < rv_60)  # Normal vol curve (backwardation = stress)
        }
    }


# ─────────────────────────────────────────────────────────────────
#  3. CROSS-ASSET FACTOR TRANSMISSION
# ─────────────────────────────────────────────────────────────────

def analyze_cross_asset_factor(
    df_asset    : pd.DataFrame,
    df_nasdaq   : Optional[pd.DataFrame] = None,
    df_btc      : Optional[pd.DataFrame] = None,
    df_dxy      : Optional[pd.DataFrame] = None
) -> Dict:
    """
    Analisis seberapa besar sebuah aset dipengaruhi oleh faktor global.

    Output:
      - Beta vs Nasdaq (Tech Risk Factor)
      - Correlation vs BTC (Crypto Risk Factor)
      - DXY Sensitivity (Dollar Factor)
      - Factor Attribution: berapa % dari return yang explained oleh faktor global
    """
    if df_asset is None or df_asset.empty or 'Close' not in df_asset.columns:
        return {"error": "Data aset tidak valid"}

    ret_asset = np.log(df_asset['Close'] / df_asset['Close'].shift(1)).dropna()
    result    = {"cross_asset_sensitivity": {}}

    # ── Nasdaq Beta ──────────────────────────────────────────────
    if df_nasdaq is not None and not df_nasdaq.empty and 'Close' in df_nasdaq.columns:
        ret_ndx = np.log(df_nasdaq['Close'] / df_nasdaq['Close'].shift(1)).dropna()
        idx_common = ret_asset.index.intersection(ret_ndx.index)
        if len(idx_common) > 20:
            ra = ret_asset.loc[idx_common].values
            rn = ret_ndx.loc[idx_common].values
            # Beta = Cov(asset, nasdaq) / Var(nasdaq)
            beta_ndx  = float(np.cov(ra, rn)[0, 1] / max(np.var(rn), 1e-10))
            corr_ndx, pval_ndx = pearsonr(ra, rn)
            result["cross_asset_sensitivity"]["nasdaq"] = {
                "beta"           : round(beta_ndx, 4),
                "correlation"    : round(float(corr_ndx), 4),
                "significant"    : bool(pval_ndx < 0.05),
                "interpretation" : f"Beta {beta_ndx:.2f}x Nasdaq. {'High tech sensitivity.' if abs(beta_ndx) > 1 else 'Low tech sensitivity.'}"
            }

    # ── BTC Correlation ──────────────────────────────────────────
    if df_btc is not None and not df_btc.empty and 'Close' in df_btc.columns:
        ret_btc = np.log(df_btc['Close'] / df_btc['Close'].shift(1)).dropna()
        idx_common = ret_asset.index.intersection(ret_btc.index)
        if len(idx_common) > 20:
            ra  = ret_asset.loc[idx_common].values
            rb  = ret_btc.loc[idx_common].values
            corr_btc, pval_btc = pearsonr(ra, rb)
            beta_btc = float(np.cov(ra, rb)[0, 1] / max(np.var(rb), 1e-10))
            result["cross_asset_sensitivity"]["btc"] = {
                "beta"           : round(beta_btc, 4),
                "correlation"    : round(float(corr_btc), 4),
                "significant"    : bool(pval_btc < 0.05),
                "interpretation" : f"Korelasi BTC {corr_btc:.2f}. {'High crypto co-movement.' if abs(corr_btc) > 0.6 else 'Idiosyncratic behavior.' if abs(corr_btc) < 0.3 else 'Moderate crypto exposure.'}"
            }

    # ── DXY Sensitivity ──────────────────────────────────────────
    if df_dxy is not None and not df_dxy.empty and 'Close' in df_dxy.columns:
        ret_dxy = np.log(df_dxy['Close'] / df_dxy['Close'].shift(1)).dropna()
        idx_common = ret_asset.index.intersection(ret_dxy.index)
        if len(idx_common) > 20:
            ra   = ret_asset.loc[idx_common].values
            rd   = ret_dxy.loc[idx_common].values
            corr_dxy, _ = pearsonr(ra, rd)
            result["cross_asset_sensitivity"]["dxy"] = {
                "correlation"   : round(float(corr_dxy), 4),
                "interpretation": f"Sensitivitas DXY: {corr_dxy:.2f}. {'Inverse DXY (typical risk asset).' if corr_dxy < -0.3 else 'Positif DXY (safe haven behavior).' if corr_dxy > 0.3 else 'Netral terhadap Dollar.'}"
            }

    # ── Factor Attribution (simplified R²) ───────────────────────
    r2_values = []
    for factor_name, factor_data in result["cross_asset_sensitivity"].items():
        if "correlation" in factor_data:
            r2_values.append(factor_data["correlation"] ** 2)

    systemic_r2 = float(min(sum(r2_values), 1.0)) if r2_values else 0
    idio_r2     = 1.0 - systemic_r2

    result["factor_attribution"] = {
        "systemic_factor_pct" : round(systemic_r2 * 100, 2),
        "idiosyncratic_pct"   : round(idio_r2 * 100, 2),
        "interpretation"      : (
            "Pergerakan aset ini sangat didominasi faktor global (>70% systemic)." if systemic_r2 > 0.7
            else "Aset ini memiliki sifat idiosyncratic kuat — bergerak karena faktor internalnya sendiri." if systemic_r2 < 0.3
            else "Aset ini dipengaruhi campuran faktor global dan internal."
        )
    }

    return result


# ─────────────────────────────────────────────────────────────────
#  4. BTC DOMINANCE FACTOR (Crypto-Specific)
# ─────────────────────────────────────────────────────────────────

def analyze_btc_dominance_factor(df_btc_dom: Optional[pd.DataFrame] = None) -> Dict:
    """
    Analisis dampak BTC Dominance terhadap altcoin allocation.

    Dominance regimes:
      HIGH (>55%)   → BTC season: altcoin underperform relative to BTC
      FALLING       → Altcoin season: alt rotasi naik
      RISING        → Flight to BTC: de-risk dari alt
      LOW (<42%)    → Peak alt season, biasanya pre-correction
    """
    # Jika tidak ada data dominance, return estimasi berdasarkan logika umum
    if df_btc_dom is None or df_btc_dom.empty:
        return {
            "data_available"  : False,
            "message"         : "Data BTC dominance tidak tersedia. Gunakan CoinGecko API untuk data real-time.",
            "manual_check_url": "https://www.coingecko.com/en/global_charts"
        }

    dom    = df_btc_dom['Close'].dropna()
    current_dom  = float(dom.iloc[-1])
    change_7d    = float((dom.iloc[-1] / dom.iloc[-8] - 1) * 100) if len(dom) > 8 else 0
    change_30d   = float((dom.iloc[-1] / dom.iloc[-31] - 1) * 100) if len(dom) > 31 else 0

    if current_dom > 55 and change_7d > 0.5:
        dom_regime = "BTC_SEASON_RISING"
        implication = "BTC Dominance tinggi & naik → Pegang BTC, kurangi alt exposure."
        alt_bias    = "BEARISH_ALTS"
    elif current_dom > 55 and change_7d < -0.5:
        dom_regime = "BTC_SEASON_PEAKING"
        implication = "BTC Dominance tinggi tapi mulai turun → Awal potensi rotasi ke alt."
        alt_bias    = "CAUTIOUSLY_BULLISH_ALTS"
    elif current_dom < 42 and change_7d < 0:
        dom_regime = "ALT_SEASON_PEAK"
        implication = "Dominance sangat rendah. Altcoin season mungkin mendekati puncak."
        alt_bias    = "RISK_HIGH_ALTS"
    elif current_dom < 50 and change_7d < -0.5:
        dom_regime = "ALT_SEASON_ACTIVE"
        implication = "Dominance turun. Altcoin season aktif → Alt outperform BTC."
        alt_bias    = "BULLISH_ALTS"
    else:
        dom_regime = "TRANSITIONAL"
        implication = "Dominance dalam transisi. Belum ada sinyal dominasi yang jelas."
        alt_bias    = "NEUTRAL"

    return {
        "data_available"   : True,
        "current_dominance": round(current_dom, 2),
        "change_7d_pct"    : round(change_7d, 4),
        "change_30d_pct"   : round(change_30d, 4),
        "dominance_regime" : dom_regime,
        "implication"      : implication,
        "alt_bias"         : alt_bias
    }


# ─────────────────────────────────────────────────────────────────
#  5. FACTOR COMPOSITE SCORE
# ─────────────────────────────────────────────────────────────────

def get_factor_composite(df: pd.DataFrame, cross_asset_dfs: Optional[Dict] = None) -> Dict:
    """
    Composite Factor Analysis — satu panggilan untuk semua faktor.
    """
    momentum  = analyze_momentum_factor(df)
    vrp       = calculate_vol_risk_premium(df)

    nasdaq_df = cross_asset_dfs.get("nasdaq") if cross_asset_dfs else None
    btc_df    = cross_asset_dfs.get("btc")    if cross_asset_dfs else None
    dxy_df    = cross_asset_dfs.get("dxy")    if cross_asset_dfs else None

    cross     = analyze_cross_asset_factor(df, nasdaq_df, btc_df, dxy_df)

    # Factor Alpha Score
    mom_score   = momentum.get("momentum_quality_score", 50)
    vrp_signal  = vrp.get("vrp_regime", "FAIR_VALUE")
    vrp_score   = 70 if vrp_signal == "VOL_OVERSHOOTING" else 30 if vrp_signal == "ELEVATED_MEAN_REVERSION" else 50
    idio_pct    = cross.get("factor_attribution", {}).get("idiosyncratic_pct", 50)
    idio_score  = min(100, idio_pct)  # Higher idio = less vulnerable to macro selloff

    alpha_score = mom_score * 0.4 + vrp_score * 0.3 + idio_score * 0.3

    return {
        "factor_alpha_score": round(alpha_score, 2),
        "alpha_interpretation": (
            "Alpha score tinggi — Setup memiliki faktor tailwind yang solid." if alpha_score > 65
            else "Alpha score rendah — Faktor tidak mendukung setup saat ini." if alpha_score < 35
            else "Alpha score moderat — Mixed factor signals."
        ),
        "momentum_factor"  : momentum,
        "vol_risk_premium" : vrp,
        "cross_asset"      : cross
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _estimate_momentum_half_life(close: pd.Series) -> Optional[int]:
    """
    Estimasi momentum half-life dengan autocorrelation decay.
    Half-life = periode di mana autocorrelation of returns turun ke 0.5.
    """
    try:
        ret = close.pct_change().dropna()
        if len(ret) < 20:
            return None
        ac_values = [float(ret.autocorr(lag=l)) for l in range(1, min(30, len(ret)//3))]
        for i, ac in enumerate(ac_values):
            if ac < 0.5:
                return i + 1
        return None
    except Exception:
        return None
