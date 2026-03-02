"""
╔══════════════════════════════════════════════════════════════════╗
║           APEX DATA QUALITY ENGINE v1.0                         ║
║  Missing Tick · Outlier · Spoof Detection · Exchange Anomaly    ║
╚══════════════════════════════════════════════════════════════════╝

Layer 8 — EXTREMELY INSTITUTIONAL
Semua model quant bergantung pada data yang bersih.
"Garbage in, garbage out" adalah kematian quant strategy.

Fungsi:
  1. Missing Tick Detection   → Identifikasi gap data yang abnormal
  2. Statistical Outlier Det. → Z-Score based outlier flagging
  3. Liquidity Spoof Detection → Volume anomaly yang mencurigakan
  4. Exchange Anomaly         → Deteksi data error dari exchange
  5. Full Quality Report      → Single comprehensive quality score
"""

import numpy as np
import pandas as pd
from scipy.stats import zscore as scipy_zscore, iqr
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. MISSING TICK DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_missing_ticks(df: pd.DataFrame, expected_interval: str = "1D") -> Dict:
    """
    Deteksi gap dalam data time series yang tidak seharusnya ada.

    Untuk data daily: gap lebih dari 3 hari berurutan di hari kerja = anomali
    Untuk data intraday: gap lebih dari 2x interval = anomali

    Args:
        df                : OHLCV DataFrame dengan DatetimeIndex
        expected_interval : '1D', '1H', '15m', '1m'
    """
    if df is None or df.empty:
        return {"error": "DataFrame kosong"}

    if not isinstance(df.index, pd.DatetimeIndex):
        return {"error": "Index harus DatetimeIndex"}

    # Hapus duplikat index
    df_clean = df[~df.index.duplicated(keep='first')]
    idx      = df_clean.index.sort_values()
    diffs    = pd.Series(idx).diff().dropna()

    # Mapping interval ke durasi expected
    interval_map = {
        "1D" : pd.Timedelta(days=1),
        "1H" : pd.Timedelta(hours=1),
        "4H" : pd.Timedelta(hours=4),
        "15m": pd.Timedelta(minutes=15),
        "5m" : pd.Timedelta(minutes=5),
        "1m" : pd.Timedelta(minutes=1),
    }
    expected_delta = interval_map.get(expected_interval, pd.Timedelta(days=1))

    # Threshold: gap > 3x expected interval = missing tick
    threshold = expected_delta * (4 if expected_interval == "1D" else 3)

    gap_locations = diffs[diffs > threshold]
    gap_list      = []
    for loc_idx, gap_size in gap_locations.items():
        ts = idx[loc_idx - 1].isoformat() if loc_idx > 0 else "start"
        gap_list.append({
            "after_date"    : ts,
            "gap_duration"  : str(gap_size),
            "expected_max"  : str(expected_delta * 3),
            "gap_severity"  : "CRITICAL" if gap_size > expected_delta * 7 else "WARNING"
        })

    total_rows    = len(df_clean)
    missing_pct   = (len(gap_list) / max(total_rows, 1)) * 100
    completeness  = max(0, 100 - missing_pct * 10)

    return {
        "total_rows"        : total_rows,
        "gap_count"         : len(gap_list),
        "critical_gaps"     : sum(1 for g in gap_list if g["gap_severity"] == "CRITICAL"),
        "warning_gaps"      : sum(1 for g in gap_list if g["gap_severity"] == "WARNING"),
        "completeness_score": round(completeness, 2),
        "gap_details"       : gap_list[:10],  # Top 10 gaps
        "assessment"        : "CLEAN" if len(gap_list) == 0 else "MINOR_GAPS" if len(gap_list) < 5 else "SIGNIFICANT_GAPS",
        "recommendation"    : (
            "Data bersih dari missing ticks." if len(gap_list) == 0
            else f"Ditemukan {len(gap_list)} gap. Pertimbangkan interpolasi atau exclude period tersebut."
        )
    }


# ─────────────────────────────────────────────────────────────────
#  2. STATISTICAL OUTLIER DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_price_outliers(df: pd.DataFrame, zscore_threshold: float = 3.5) -> Dict:
    """
    Deteksi outlier harga menggunakan metode statistik:
      1. Z-Score Method (asumsi normal distribution)
      2. IQR (Interquartile Range) Method (non-parametric)
      3. Rolling Z-Score (contextual outlier dalam window waktu)

    Outlier bisa disebabkan oleh:
      - Flash crash / spike (legit market event)
      - Data error dari exchange (harus di-filter)
      - Low liquidity period (wide bid-ask)
    """
    required = {'Open', 'High', 'Low', 'Close'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data OHLCV diperlukan"}

    close = df['Close'].dropna()
    log_ret = np.log(close / close.shift(1)).dropna()

    # ── Method 1: Z-Score on Log Returns ─────────────────────────
    z_scores  = scipy_zscore(log_ret)
    z_outliers = np.where(np.abs(z_scores) > zscore_threshold)[0]
    z_outlier_dates = [str(log_ret.index[i]) for i in z_outliers]
    z_outlier_vals  = [float(log_ret.iloc[i] * 100) for i in z_outliers]

    # ── Method 2: IQR Method ─────────────────────────────────────
    q1   = float(log_ret.quantile(0.25))
    q3   = float(log_ret.quantile(0.75))
    iqr_ = q3 - q1
    iqr_lower = q1 - 2.5 * iqr_
    iqr_upper = q3 + 2.5 * iqr_
    iqr_outliers = log_ret[(log_ret < iqr_lower) | (log_ret > iqr_upper)]

    # ── Method 3: OHLC Consistency Check ─────────────────────────
    # High harus >= max(Open, Close), Low harus <= min(Open, Close)
    ohlc_errors = []
    for idx, row in df.iterrows():
        o, h, l, c = float(row['Open']), float(row['High']), float(row['Low']), float(row['Close'])
        if h < max(o, c) or l > min(o, c) or h < l:
            ohlc_errors.append({
                "date"  : str(idx),
                "open"  : o, "high": h, "low": l, "close": c,
                "issue" : "OHLC_INCONSISTENCY"
            })

    # ── Method 4: High/Low Spread Anomaly ────────────────────────
    hl_ratio = (df['High'] / df['Low']).dropna()
    hl_mean  = float(hl_ratio.mean())
    hl_std   = float(hl_ratio.std())
    hl_anomalies = hl_ratio[hl_ratio > hl_mean + 3 * hl_std]

    total_outliers = len(z_outliers) + len(ohlc_errors)
    outlier_pct    = (total_outliers / max(len(df), 1)) * 100
    cleanliness    = max(0, 100 - outlier_pct * 5)

    return {
        "zscore_outliers": {
            "count"     : int(len(z_outliers)),
            "dates"     : z_outlier_dates[:10],
            "returns_pct": z_outlier_vals[:10],
            "threshold" : zscore_threshold
        },
        "iqr_outliers": {
            "count"      : int(len(iqr_outliers)),
            "iqr_bounds" : {"lower_pct": round(iqr_lower * 100, 4), "upper_pct": round(iqr_upper * 100, 4)}
        },
        "ohlc_errors"  : {
            "count"  : len(ohlc_errors),
            "details": ohlc_errors[:5]
        },
        "hl_spread_anomalies": {
            "count"  : int(len(hl_anomalies)),
            "mean_hl_ratio": round(hl_mean, 4)
        },
        "data_cleanliness_score": round(cleanliness, 2),
        "assessment" : (
            "CLEAN" if total_outliers == 0
            else "MINOR_ANOMALIES" if total_outliers < 5
            else "SIGNIFICANT_ANOMALIES" if total_outliers < 20
            else "SEVERELY_CONTAMINATED"
        ),
        "recommendation": (
            "Data bersih — siap digunakan." if total_outliers == 0
            else f"Ditemukan {total_outliers} outlier. Pertimbangkan winsorize atau Hampel filter sebelum analisis."
        )
    }


# ─────────────────────────────────────────────────────────────────
#  3. LIQUIDITY SPOOF DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_volume_spoofing(df: pd.DataFrame) -> Dict:
    """
    Deteksi anomali volume yang mencurigakan — potensial spoofing atau
    wash trading oleh market manipulator.

    Indikasi Spoof:
      1. Volume spike ekstrem TANPA pergerakan harga signifikan
         → Wash trading / phantom volume
      2. High volume + tiny price move (vol-price divergence extreme)
         → Potential manipulation
      3. Volume tiba-tiba drop ke near-zero (liquidity withdrawal)
         → Market maker withdrawal (pre-crash signal)

    Catatan: Deteksi ini adalah FLAG, bukan konfirmasi manipulasi.
    """
    required = {'Close', 'Volume'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data Close + Volume diperlukan"}

    close  = df['Close'].dropna()
    volume = df['Volume'].dropna()
    ret    = close.pct_change().abs().dropna()

    # Align
    common = close.index.intersection(volume.index).intersection(ret.index)
    close  = close.loc[common]
    volume = volume.loc[common]
    ret    = ret.loc[common]

    vol_mean = float(volume.mean())
    vol_std  = float(volume.std())
    ret_mean = float(ret.mean())
    ret_std  = float(ret.std())

    suspicious_flags = []

    # Flag 1: High volume + tiny price move (Vol > 3σ, Return < 0.5× average)
    for i in range(len(common)):
        v = float(volume.iloc[i])
        r = float(ret.iloc[i])
        if v > vol_mean + 3 * vol_std and r < ret_mean * 0.5:
            suspicious_flags.append({
                "date"     : str(common[i]),
                "type"     : "HIGH_VOL_NO_PRICE_MOVE",
                "volume"   : round(v, 2),
                "vol_zscore": round((v - vol_mean) / max(vol_std, 1), 4),
                "return_pct": round(r * 100, 4),
                "severity" : "HIGH"
            })

    # Flag 2: Near-zero volume (liquidity withdrawal)
    low_vol_threshold = vol_mean * 0.1
    for i in range(len(common)):
        v = float(volume.iloc[i])
        if v < low_vol_threshold and v > 0:
            suspicious_flags.append({
                "date"    : str(common[i]),
                "type"    : "LIQUIDITY_WITHDRAWAL",
                "volume"  : round(v, 2),
                "pct_of_avg": round((v / vol_mean) * 100, 2),
                "severity": "MEDIUM"
            })

    # Flag 3: Extreme volume spike (> 5σ above mean) — possible wash trade or news event
    for i in range(len(common)):
        v = float(volume.iloc[i])
        z = (v - vol_mean) / max(vol_std, 1)
        if z > 5:
            suspicious_flags.append({
                "date"     : str(common[i]),
                "type"     : "EXTREME_VOLUME_SPIKE",
                "volume"   : round(v, 2),
                "vol_zscore": round(z, 4),
                "severity" : "HIGH" if z > 8 else "MEDIUM"
            })

    high_flags   = [f for f in suspicious_flags if f.get("severity") == "HIGH"]
    medium_flags = [f for f in suspicious_flags if f.get("severity") == "MEDIUM"]

    return {
        "total_suspicious_events": len(suspicious_flags),
        "high_severity_count"    : len(high_flags),
        "medium_severity_count"  : len(medium_flags),
        "spoof_risk_level"       : (
            "HIGH" if len(high_flags) > 3
            else "MEDIUM" if len(high_flags) > 0 or len(medium_flags) > 5
            else "LOW"
        ),
        "suspicious_events"      : suspicious_flags[:10],
        "volume_baseline"        : {
            "mean" : round(vol_mean, 2),
            "std"  : round(vol_std, 2),
            "cv"   : round(vol_std / max(vol_mean, 1), 4)  # Coefficient of variation
        },
        "recommendation": (
            "Volume pattern bersih." if len(suspicious_flags) == 0
            else f"Terdeteksi {len(suspicious_flags)} event mencurigakan. Validasi dengan exchange data asli sebelum mengambil keputusan besar."
        )
    }


# ─────────────────────────────────────────────────────────────────
#  4. EXCHANGE ANOMALY DETECTION
# ─────────────────────────────────────────────────────────────────

def detect_exchange_anomalies(df: pd.DataFrame) -> Dict:
    """
    Deteksi anomali yang biasanya berasal dari error data exchange:
      1. Duplicate timestamps
      2. Price reversal yang mustahil (harga teleport)
      3. Open = High = Low = Close (candle tidak valid)
      4. Negative volume
      5. Price di luar range wajar (terlalu extreme untuk satu candle)
    """
    if df is None or df.empty:
        return {"error": "DataFrame kosong"}

    anomalies = []

    # 1. Duplicate timestamps
    dups = df.index.duplicated().sum()
    if dups > 0:
        anomalies.append({
            "type"   : "DUPLICATE_TIMESTAMPS",
            "count"  : int(dups),
            "impact" : "HIGH",
            "fix"    : "Gunakan df[~df.index.duplicated(keep='first')]"
        })

    # 2. Price teleport (single candle move > 30%)
    if 'Close' in df.columns:
        ret = df['Close'].pct_change().abs()
        teleports = ret[ret > 0.30]
        if len(teleports) > 0:
            anomalies.append({
                "type"   : "PRICE_TELEPORT",
                "count"  : len(teleports),
                "max_pct": round(float(teleports.max()) * 100, 2),
                "dates"  : [str(d) for d in teleports.index[:5]],
                "impact" : "CRITICAL",
                "fix"    : "Filter atau cap return di ±30% per candle"
            })

    # 3. Doji anomaly (Open=High=Low=Close — hanya 1 price, tidak ada perdagangan)
    if all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        true_doji = df[(df['High'] == df['Low']) & (df['Open'] == df['Close']) & (df['High'] == df['Open'])]
        if len(true_doji) > 0:
            anomalies.append({
                "type"  : "ZERO_RANGE_CANDLE",
                "count" : len(true_doji),
                "impact": "MEDIUM",
                "fix"   : "Exclude atau interpolate candle ini"
            })

    # 4. Negative volume
    if 'Volume' in df.columns:
        neg_vol = (df['Volume'] < 0).sum()
        if neg_vol > 0:
            anomalies.append({
                "type"  : "NEGATIVE_VOLUME",
                "count" : int(neg_vol),
                "impact": "CRITICAL",
                "fix"   : "Data error — ganti dengan df['Volume'].abs() atau drop baris"
            })

    # 5. Zero Close price
    if 'Close' in df.columns:
        zero_prices = (df['Close'] == 0).sum()
        if zero_prices > 0:
            anomalies.append({
                "type"  : "ZERO_CLOSE_PRICE",
                "count" : int(zero_prices),
                "impact": "CRITICAL",
                "fix"   : "Drop atau forward-fill baris dengan Close=0"
            })

    critical_count = sum(1 for a in anomalies if a.get("impact") == "CRITICAL")
    high_count     = sum(1 for a in anomalies if a.get("impact") == "HIGH")
    is_usable      = critical_count == 0

    return {
        "total_anomalies"   : len(anomalies),
        "critical_anomalies": critical_count,
        "high_anomalies"    : high_count,
        "is_data_usable"    : is_usable,
        "data_integrity"    : "RELIABLE" if len(anomalies) == 0 else "QUESTIONABLE" if critical_count == 0 else "COMPROMISED",
        "anomaly_details"   : anomalies,
        "overall_verdict"   : (
            "✅ Data exchange bersih." if len(anomalies) == 0
            else f"⚠️ {len(anomalies)} anomali exchange terdeteksi. Perbaiki sebelum analisis."
            if critical_count == 0
            else f"⛔ {critical_count} anomali KRITIS. Data tidak reliable untuk trading decisions."
        )
    }


# ─────────────────────────────────────────────────────────────────
#  5. FULL DATA QUALITY REPORT
# ─────────────────────────────────────────────────────────────────

def generate_data_quality_report(
    df               : pd.DataFrame,
    expected_interval: str = "1D"
) -> Dict:
    """
    Laporan kualitas data komprehensif — satu panggilan, semua pengecekan.
    Output digunakan oleh Model Confidence Engine untuk menilai data quality score.
    """
    ticks     = detect_missing_ticks(df, expected_interval)
    outliers  = detect_price_outliers(df)
    spoof     = detect_volume_spoofing(df)
    exchange  = detect_exchange_anomalies(df)

    # Composite Quality Score (0-100)
    tick_score     = ticks.get("completeness_score", 50) if "error" not in ticks else 50
    clean_score    = outliers.get("data_cleanliness_score", 50) if "error" not in outliers else 50
    spoof_ok       = 100 if spoof.get("spoof_risk_level") == "LOW" else 60 if spoof.get("spoof_risk_level") == "MEDIUM" else 20
    exchange_ok    = 100 if exchange.get("data_integrity") == "RELIABLE" else 60 if exchange.get("data_integrity") == "QUESTIONABLE" else 10

    composite = (tick_score * 0.25 + clean_score * 0.30 + spoof_ok * 0.20 + exchange_ok * 0.25)

    if composite >= 85:
        quality_label = "INSTITUTIONAL_GRADE"
        quality_action = "Data siap untuk analisis institusional penuh."
    elif composite >= 65:
        quality_label = "ACCEPTABLE"
        quality_action = "Data cukup baik. Beberapa isu minor perlu diperhatikan."
    elif composite >= 40:
        quality_label = "MARGINAL"
        quality_action = "Data marginal. Perlu cleaning sebelum digunakan."
    else:
        quality_label = "UNRELIABLE"
        quality_action = "⛔ Data TIDAK RELIABLE. Jangan gunakan untuk trading decisions."

    # Auto-cleaning suggestions
    suggestions = []
    if ticks.get("gap_count", 0) > 0:
        suggestions.append("Forward-fill atau interpolate missing periods")
    if outliers.get("zscore_outliers", {}).get("count", 0) > 5:
        suggestions.append("Winsorize returns di ±5% sebelum model fitting")
    if exchange.get("critical_anomalies", 0) > 0:
        suggestions.append("Drop atau repair critical data errors sebelum analisis")
    if spoof.get("high_severity_count", 0) > 0:
        suggestions.append("Flag high-vol no-move candles — exclude dari signal generation")

    return {
        "composite_quality_score": round(composite, 2),
        "quality_label"          : quality_label,
        "quality_action"         : quality_action,
        "component_scores"       : {
            "tick_completeness" : round(tick_score, 2),
            "price_cleanliness" : round(clean_score, 2),
            "volume_authenticity": round(spoof_ok, 2),
            "exchange_integrity" : round(exchange_ok, 2)
        },
        "cleaning_suggestions"   : suggestions,
        "detail_reports"         : {
            "missing_ticks"    : ticks,
            "price_outliers"   : outliers,
            "volume_spoof"     : spoof,
            "exchange_anomaly" : exchange
        }
    }
