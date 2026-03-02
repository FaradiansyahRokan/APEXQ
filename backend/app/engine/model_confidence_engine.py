"""
╔══════════════════════════════════════════════════════════════════╗
║    APEX MODEL CONFIDENCE + META STRATEGY ENGINE v1.0            ║
║  Signal Quality · Model Stability · Strategy Selector           ║
╚══════════════════════════════════════════════════════════════════╝

Layer 5 + 6 — SUPER RARE / QUANT FUND LEVEL

Model Confidence Engine:
  Institutional quant TIDAK PERNAH blind trust sinyal model.
  Mereka selalu tanya: "Seberapa valid sinyal ini di kondisi sekarang?"

Meta Strategy Engine:
  Strategy adalah fungsi dari regime.
  IF regime = trending → activate momentum model
  IF regime = chop     → activate mean reversion
  IF regime = panic    → activate vol breakout / cash
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
#  PART A: MODEL CONFIDENCE ENGINE
# ══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
#  1. SIGNAL CONFIDENCE SCORE
# ─────────────────────────────────────────────────────────────────

def calculate_signal_confidence(
    apex_score      : float,
    ict_bias        : str,
    kelly_edge      : str,
    zscore_signal   : str,
    regime          : str,
    vol_regime      : str,
    liq_regime      : str,
    prob_profit     : float,
    n_data_points   : int,
    sortino         : float
) -> Dict:
    """
    Hitung Signal Confidence Score (0-100) berdasarkan KUALITAS sinyal,
    bukan hanya arah sinyal.

    Faktor yang dinilai:
      1. Consensus Score     → Berapa banyak sinyal yang agree satu sama lain
      2. Model Validity      → Apakah model valid di kondisi regime saat ini
      3. Data Quality Proxy  → Apakah ada cukup data untuk sinyal ini reliable
      4. Regime Alignment    → Apakah strategi cocok dengan regime aktif

    Output:
      confidence_score : 0-100
      confidence_label : LOW / MODERATE / HIGH / VERY_HIGH
      trade_gate       : OPEN / RESTRICTED / CLOSED
    """
    scores  = []
    reasons = []

    # ── 1. APEX Score contribution (normalized ke 0-1) ────────────
    apex_norm = min(max((apex_score - 40) / 60, 0), 1)  # 40=min meaningful, 100=max
    scores.append(apex_norm)
    reasons.append(f"APEX Score {apex_score}/100 (weight: 25%)")

    # ── 2. Kelly Edge Quality ─────────────────────────────────────
    edge_score = {"STRONG": 1.0, "MODERATE": 0.7, "WEAK": 0.3, "NO_EDGE": 0.0, "UNKNOWN": 0.3}
    ks = edge_score.get(kelly_edge, 0.3)
    scores.append(ks)
    reasons.append(f"Kelly Edge '{kelly_edge}' (weight: 20%)")

    # ── 3. Signal Consensus (ICT + APEX agree?) ───────────────────
    apex_dir = "BULLISH" if apex_score > 55 else "BEARISH" if apex_score < 45 else "NEUTRAL"
    agree = ict_bias == apex_dir
    consensus = 1.0 if agree else 0.4
    scores.append(consensus)
    reasons.append(f"Signal consensus {'AGREE' if agree else 'DISAGREE'} (APEX={apex_dir}, ICT={ict_bias})")

    # ── 4. Regime Model Validity ──────────────────────────────────
    # Tidak semua model valid di semua regime
    regime_valid_map = {
        ("LOW_VOL_BULLISH", "LOW") : 1.0,    # Perfect conditions
        ("LOW_VOL_BULLISH", "NORMAL"): 0.9,
        ("SIDEWAYS_CHOP", "NORMAL"): 0.8,    # Good for mean reversion
        ("HIGH_VOL_BEARISH", "HIGH"): 0.5,   # Directional but risky
        ("HIGH_VOL_BEARISH", "CRISIS"): 0.1, # Model breakdown
        ("SIDEWAYS_CHOP", "HIGH"): 0.4,
    }
    regime_validity = regime_valid_map.get((regime, vol_regime), 0.5)
    scores.append(regime_validity)
    reasons.append(f"Regime validity: HMM={regime}, Vol={vol_regime} → {regime_validity*100:.0f}%")

    # ── 5. Liquidity Gate ─────────────────────────────────────────
    liq_score_map = {"ABUNDANT": 1.0, "NORMAL": 0.8, "THIN": 0.4, "STRESSED": 0.0}
    lq = liq_score_map.get(liq_regime, 0.5)
    scores.append(lq)
    reasons.append(f"Liquidity regime '{liq_regime}' → execution risk {'LOW' if lq > 0.7 else 'HIGH'}")

    # ── 6. Monte Carlo probability ────────────────────────────────
    mc_score = max(0, min((prob_profit - 40) / 60, 1))  # 40% = 0, 100% = 1
    scores.append(mc_score)
    reasons.append(f"Monte Carlo profit probability: {prob_profit:.1f}%")

    # ── 7. Data Quality Proxy ─────────────────────────────────────
    data_score = 1.0 if n_data_points > 250 else 0.7 if n_data_points > 60 else 0.3
    scores.append(data_score)
    reasons.append(f"Data points available: {n_data_points} ({'Sufficient' if data_score > 0.7 else 'Limited'})")

    # ── 8. Sortino quality ────────────────────────────────────────
    sort_score = min(max((sortino + 0.5) / 2, 0), 1)  # -0.5 = 0, 1.5 = 1
    scores.append(sort_score)
    reasons.append(f"Sortino ratio: {sortino:.3f} ({'Strong risk-adjusted return' if sort_score > 0.7 else 'Weak'})")

    # ── Weighted Average ─────────────────────────────────────────
    weights = [0.20, 0.20, 0.15, 0.15, 0.10, 0.10, 0.05, 0.05]
    confidence = sum(s * w for s, w in zip(scores, weights)) * 100

    # Classification
    if confidence >= 75:
        label = "VERY_HIGH"
        gate  = "OPEN"
        gate_desc = f"✅ Signal confidence {confidence:.1f}% — Setup qualified untuk eksekusi penuh."
    elif confidence >= 55:
        label = "HIGH"
        gate  = "OPEN"
        gate_desc = f"✅ Signal confidence {confidence:.1f}% — Eksekusi dengan size standar."
    elif confidence >= 40:
        label = "MODERATE"
        gate  = "RESTRICTED"
        gate_desc = f"⚠️ Signal confidence {confidence:.1f}% — Kurangi size 50%, konfirmasi lebih lanjut."
    else:
        label = "LOW"
        gate  = "CLOSED"
        gate_desc = f"⛔ Signal confidence {confidence:.1f}% — Setup tidak memenuhi threshold minimum. STAND CLEAR."

    return {
        "signal_confidence_score": round(confidence, 2),
        "confidence_label"       : label,
        "trade_gate"             : gate,
        "gate_description"       : gate_desc,
        "component_scores"       : {
            "apex_normalized"    : round(apex_norm, 4),
            "kelly_edge"         : round(ks, 4),
            "signal_consensus"   : round(consensus, 4),
            "regime_validity"    : round(regime_validity, 4),
            "liquidity_quality"  : round(lq, 4),
            "mc_probability"     : round(mc_score, 4),
            "data_quality"       : round(data_score, 4),
            "sortino_quality"    : round(sort_score, 4),
        },
        "reasoning"              : reasons
    }


# ─────────────────────────────────────────────────────────────────
#  2. MODEL STABILITY SCORE
#     Seberapa stabil sinyal model ini dari waktu ke waktu?
# ─────────────────────────────────────────────────────────────────

def calculate_model_stability(df: pd.DataFrame, window: int = 20) -> Dict:
    """
    Ukur stabilitas model dengan rolling signal variance.

    Intuisi: Jika sinyal berubah-ubah setiap hari dengan cepat,
    model tidak stabil dan tidak reliable untuk real trading.

    Ukuran stabilitas:
      1. Signal Flip Rate      → Berapa sering sinyal ganti arah dalam N hari
      2. Indicator Variance    → Variance dari RSI, Z-Score rolling
      3. Prediction Consistency → Autocorrelation sinyal (tinggi = stabil)
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close   = df['Close'].dropna()
    log_ret = np.log(close / close.shift(1)).dropna()

    # Rolling Z-Score stability
    roll_mean = close.rolling(window).mean()
    roll_std  = close.rolling(window).std().replace(0, np.nan)
    zscore    = (close - roll_mean) / roll_std

    # Signal flip rate (how often signal changes direction)
    zscore_signal  = (zscore > 0).astype(int)  # 1 = above mean, 0 = below
    signal_changes = (zscore_signal.diff().abs()).dropna()
    flip_rate_60d  = float(signal_changes.tail(60).mean()) if len(signal_changes) >= 60 else float(signal_changes.mean())

    # RSI rolling
    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))

    rsi_std_20d = float(rsi.tail(20).std()) if len(rsi.dropna()) >= 20 else 50.0
    zscore_std  = float(zscore.tail(60).std()) if len(zscore.dropna()) >= 60 else 1.0

    # Signal autocorrelation (higher = more stable/persistent signals)
    if len(zscore_signal.dropna()) > 10:
        signal_ac = float(zscore_signal.dropna().autocorr(lag=1))
    else:
        signal_ac = 0.5

    # Stability Score (0-100, higher = more stable)
    stability = max(0, min(100,
        (1 - flip_rate_60d) * 40 +          # Flip rate (0% flips = 40 points)
        max(0, (1 - rsi_std_20d / 30)) * 30 + # RSI variance
        max(0, min(signal_ac, 1)) * 30        # Signal autocorrelation
    ))

    if stability >= 70:
        stability_label = "STABLE"
        stability_desc  = "Model sangat konsisten. Sinyal dapat dipercaya."
    elif stability >= 50:
        stability_label = "MODERATE"
        stability_desc  = "Model cukup stabil. Gunakan konfirmasi tambahan."
    else:
        stability_label = "UNSTABLE"
        stability_desc  = "Model tidak stabil. Sinyal sering flip — HIGH FALSE POSITIVE RATE."

    return {
        "model_stability_score": round(stability, 2),
        "stability_label"      : stability_label,
        "stability_description": stability_desc,
        "signal_flip_rate_60d" : round(flip_rate_60d * 100, 2),
        "rsi_variance_20d"     : round(rsi_std_20d, 4),
        "zscore_variance_60d"  : round(zscore_std, 4),
        "signal_autocorrelation": round(signal_ac, 4),
    }


# ─────────────────────────────────────────────────────────────────
#  3. DATA QUALITY SCORE (fast version, detail di data_quality_engine)
# ─────────────────────────────────────────────────────────────────

def quick_data_quality_check(df: pd.DataFrame) -> Dict:
    """
    Quick check kualitas data — apakah data layak untuk analisis?
    """
    if df is None or df.empty:
        return {"data_quality_score": 0, "label": "UNUSABLE", "issues": ["DataFrame kosong"]}

    issues = []
    score  = 100

    # Missing values
    if 'Close' in df.columns:
        missing_pct = float(df['Close'].isna().mean() * 100)
        if missing_pct > 5:
            issues.append(f"Missing values: {missing_pct:.1f}%")
            score -= 30
        elif missing_pct > 0:
            issues.append(f"Minor missing values: {missing_pct:.1f}%")
            score -= 10

    # Data recency
    try:
        last_date = df.index[-1]
        import datetime
        now = pd.Timestamp.now(tz='UTC') if df.index.tz else pd.Timestamp.now()
        staleness_days = (now - last_date).days
        if staleness_days > 5:
            issues.append(f"Data stale: {staleness_days} hari sejak update terakhir")
            score -= 20
    except Exception:
        pass

    # Sufficient data
    n = len(df)
    if n < 30:
        issues.append(f"Insufficient data: hanya {n} baris (minimum 30)")
        score -= 40
    elif n < 100:
        issues.append(f"Limited data: {n} baris (ideal >252)")
        score -= 15

    # Zero prices
    if 'Close' in df.columns:
        zero_prices = int((df['Close'] == 0).sum())
        if zero_prices > 0:
            issues.append(f"Zero prices detected: {zero_prices} baris")
            score -= 25

    score = max(0, score)
    label = "EXCELLENT" if score >= 90 else "GOOD" if score >= 70 else "ACCEPTABLE" if score >= 50 else "POOR"

    return {
        "data_quality_score": score,
        "data_quality_label": label,
        "n_rows"            : n,
        "issues"            : issues,
        "is_usable"         : score >= 50
    }


# ══════════════════════════════════════════════════════════════════
#  PART B: META STRATEGY ENGINE
# ══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────
#  4. META STRATEGY SELECTOR
# ─────────────────────────────────────────────────────────────────

# Strategy Library — parameter tiap strategy
STRATEGY_LIBRARY = {
    "TREND_FOLLOWING": {
        "description"        : "EMA Crossover + Momentum. Optimal di trending, low-vol market.",
        "best_regimes"       : ["LOW_VOL_BULLISH"],
        "best_vol_regimes"   : ["LOW", "NORMAL"],
        "entry_logic"        : "Entry pullback ke EMA20. Konfirmasi volume dan MACD.",
        "sl_logic"           : "SL di bawah last swing low atau batas Order Block.",
        "tp_logic"           : "TP bertahap di 1R, 2R, 3R. Trail SL setelah 2R.",
        "sizing_factor"      : 1.0,
        "max_concurrent_trades": 3,
        "timeframe"          : ["1H", "4H", "1D"],
    },
    "MEAN_REVERSION": {
        "description"        : "RSI Oversold/Overbought + Bollinger Band. Optimal di choppy market.",
        "best_regimes"       : ["SIDEWAYS_CHOP"],
        "best_vol_regimes"   : ["LOW", "NORMAL"],
        "entry_logic"        : "Entry di RSI <30 (long) atau >70 (short). Konfirmasi di lower BB.",
        "sl_logic"           : "SL di luar Bollinger Band ±1 ATR.",
        "tp_logic"           : "TP di mean (middle BB). RR minimal 1.5:1.",
        "sizing_factor"      : 0.75,
        "max_concurrent_trades": 2,
        "timeframe"          : ["15m", "1H"],
    },
    "VOLATILITY_BREAKOUT": {
        "description"        : "Breakout dari range setelah volatility compression. Optimal di regime transisi.",
        "best_regimes"       : ["HIGH_VOL_BEARISH", "SIDEWAYS_CHOP"],
        "best_vol_regimes"   : ["HIGH"],
        "entry_logic"        : "Entry breakout dari konsolidasi. Volume konfirmasi wajib.",
        "sl_logic"           : "SL di dalam range (center). Tight SL karena high vol.",
        "tp_logic"           : "TP 1.5x lebar range. Jangan hold lebih dari 2R.",
        "sizing_factor"      : 0.5,
        "max_concurrent_trades": 1,
        "timeframe"          : ["1H", "4H"],
    },
    "DEFENSIVE_HEDGE": {
        "description"        : "Preserve capital. Kurangi semua exposure, hedge dengan stablecoin.",
        "best_regimes"       : ["HIGH_VOL_BEARISH"],
        "best_vol_regimes"   : ["HIGH", "CRISIS"],
        "entry_logic"        : "Tidak ada new long entry. Pertimbangkan short hanya di resistance kuat.",
        "sl_logic"           : "SL sangat ketat: 1-2% dari entry.",
        "tp_logic"           : "TP cepat: 1R saja. Jangan tamak di risk-off.",
        "sizing_factor"      : 0.25,
        "max_concurrent_trades": 1,
        "timeframe"          : ["4H", "1D"],
    },
    "CASH_PRESERVATION": {
        "description"        : "STOP ALL TRADING. Pindah ke stablecoin/cash.",
        "best_regimes"       : ["HIGH_VOL_BEARISH"],
        "best_vol_regimes"   : ["CRISIS"],
        "entry_logic"        : "TIDAK ADA ENTRY. Semua posisi dikurangi atau ditutup.",
        "sl_logic"           : "N/A",
        "tp_logic"           : "N/A",
        "sizing_factor"      : 0.0,
        "max_concurrent_trades": 0,
        "timeframe"          : [],
    }
}


def select_active_strategy(
    hmm_regime   : str,
    vol_regime   : str,
    liq_regime   : str,
    macro_regime : str,
    apex_score   : float,
    signal_confidence: float
) -> Dict:
    """
    Meta-strategy selector: pilih strategi yang paling cocok berdasarkan
    keseluruhan regime environment.

    Rule Engine:
      CRISIS conditions → CASH_PRESERVATION (override all)
      RISK_OFF macro    → DEFENSIVE_HEDGE
      Trending + low vol + risk-on → TREND_FOLLOWING
      Chop + normal vol → MEAN_REVERSION
      High vol bearish  → VOLATILITY_BREAKOUT
    """
    # ── Emergency overrides ──────────────────────────────────────
    if vol_regime == "CRISIS" or liq_regime == "STRESSED":
        selected   = "CASH_PRESERVATION"
        override   = True
        override_reason = f"EMERGENCY OVERRIDE: {vol_regime} vol + {liq_regime} liquidity"
    elif macro_regime in ("RISK_OFF", "STAGFLATION_RISK") and vol_regime in ("HIGH", "CRISIS"):
        selected   = "DEFENSIVE_HEDGE"
        override   = True
        override_reason = f"MACRO OVERRIDE: {macro_regime} environment"
    elif signal_confidence < 40:
        selected   = "DEFENSIVE_HEDGE"
        override   = True
        override_reason = f"LOW CONFIDENCE OVERRIDE: Signal confidence {signal_confidence:.1f}% < 40%"
    else:
        override   = False
        override_reason = None

        # Normal regime-based selection
        if hmm_regime == "LOW_VOL_BULLISH" and vol_regime in ("LOW", "NORMAL"):
            selected = "TREND_FOLLOWING"
        elif hmm_regime == "SIDEWAYS_CHOP" and vol_regime in ("LOW", "NORMAL"):
            selected = "MEAN_REVERSION"
        elif vol_regime == "HIGH" and hmm_regime == "HIGH_VOL_BEARISH":
            selected = "VOLATILITY_BREAKOUT"
        elif hmm_regime == "HIGH_VOL_BEARISH":
            selected = "DEFENSIVE_HEDGE"
        else:
            selected = "MEAN_REVERSION"  # Default safe option

    strategy = STRATEGY_LIBRARY.get(selected, {})

    # Adjust sizing based on signal confidence
    base_size = strategy.get("sizing_factor", 0.5)
    conf_mult = signal_confidence / 100
    adj_size  = round(base_size * conf_mult, 4)

    return {
        "active_strategy"    : selected,
        "override_applied"   : override,
        "override_reason"    : override_reason,
        "strategy_details"   : {
            "description"    : strategy.get("description", "N/A"),
            "entry_logic"    : strategy.get("entry_logic", "N/A"),
            "sl_logic"       : strategy.get("sl_logic", "N/A"),
            "tp_logic"       : strategy.get("tp_logic", "N/A"),
            "timeframes"     : strategy.get("timeframe", []),
            "max_trades"     : strategy.get("max_concurrent_trades", 0),
        },
        "sizing": {
            "base_factor"    : base_size,
            "confidence_mult": round(conf_mult, 4),
            "adjusted_factor": adj_size,
            "description"    : f"Sizing = {base_size} × {conf_mult:.2f} confidence = {adj_size} dari Kelly allocation"
        },
        "regime_context": {
            "hmm"  : hmm_regime,
            "vol"  : vol_regime,
            "liq"  : liq_regime,
            "macro": macro_regime
        }
    }


# ─────────────────────────────────────────────────────────────────
#  5. MASTER CONFIDENCE REPORT (one-call)
# ─────────────────────────────────────────────────────────────────

def get_master_confidence_report(
    df              : pd.DataFrame,
    apex_score      : float,
    ict_bias        : str,
    kelly_edge      : str,
    zscore_signal   : str,
    regime          : str,
    vol_regime      : str,
    liq_regime      : str,
    macro_regime    : str,
    prob_profit     : float,
    sortino         : float
) -> Dict:
    """
    Satu fungsi yang menghasilkan laporan confidence lengkap.
    Dipanggil dari /api/apex-full endpoint.
    """
    n_data  = len(df) if df is not None and not df.empty else 0

    sig_conf = calculate_signal_confidence(
        apex_score=apex_score, ict_bias=ict_bias, kelly_edge=kelly_edge,
        zscore_signal=zscore_signal, regime=regime, vol_regime=vol_regime,
        liq_regime=liq_regime, prob_profit=prob_profit,
        n_data_points=n_data, sortino=sortino
    )

    model_stab = calculate_model_stability(df)
    data_qual  = quick_data_quality_check(df)

    meta_strat = select_active_strategy(
        hmm_regime=regime, vol_regime=vol_regime, liq_regime=liq_regime,
        macro_regime=macro_regime, apex_score=apex_score,
        signal_confidence=sig_conf.get("signal_confidence_score", 50)
    )

    # Overall System Score (governance score)
    gov_score = (
        sig_conf.get("signal_confidence_score", 0) * 0.5 +
        model_stab.get("model_stability_score", 0) * 0.3 +
        data_qual.get("data_quality_score", 0) * 0.2
    )

    return {
        "governance_score"   : round(gov_score, 2),
        "signal_confidence"  : sig_conf,
        "model_stability"    : model_stab,
        "data_quality"       : data_qual,
        "active_strategy"    : meta_strat,
        "final_trade_gate"   : sig_conf.get("trade_gate", "CLOSED"),
        "final_gate_reason"  : sig_conf.get("gate_description", ""),
        "executive_verdict"  : _governance_verdict(gov_score, sig_conf.get("trade_gate", "CLOSED"))
    }


def _governance_verdict(score: float, gate: str) -> str:
    if gate == "CLOSED":
        return f"⛔ SYSTEM GATE CLOSED — Governance score {score:.1f}. Trade diblokir oleh sistem."
    elif gate == "RESTRICTED":
        return f"⚠️ RESTRICTED MODE — Governance score {score:.1f}. Half-size only, konfirmasi manual wajib."
    elif score >= 70:
        return f"✅ FULL CLEARANCE — Governance score {score:.1f}. Sistem memberikan lampu hijau penuh."
    else:
        return f"✅ CONDITIONAL CLEARANCE — Governance score {score:.1f}. Lanjutkan dengan manajemen risiko ketat."
