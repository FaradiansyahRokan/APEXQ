"""
╔══════════════════════════════════════════════════════════════════╗
║           APEX SATIN SCREENER ENGINE v1.0                        ║
║   Auto-scan Watchlist · Score · Rank · Flag Satin-Ready Tickers  ║
╚══════════════════════════════════════════════════════════════════╝

Filosofi:
  Daripada cari satu-satu sampai nemu yang bagus,
  biarkan Screener yang kerja keras — kamu tinggal ambil
  yang sudah di-flag SATIN_READY di atas.

Cara Kerja:
  1. Iterasi daftar ticker dari watchlist (IDX / US / Crypto / Semua)
  2. Fetch data + jalankan 5 engine ringan secara paralel
  3. Scoring 0–100 per ticker berdasarkan 5 dimensi
  4. Ranking: SATIN_READY (≥70) · MARGINAL (50–69) · REJECTED (<50)

Scoring Dimensions (Total 100 poin):
  [30 pts] Sortino Ratio      → Risk-adjusted return quality
  [25 pts] Regime (HMM)       → Apakah regime mendukung entry?
  [20 pts] Momentum (ROC 20D) → Apakah trend sedang menguat?
  [15 pts] Z-Score            → Apakah harga sudah tidak overbought?
  [10 pts] Volatility Grade   → Apakah vol dalam batas yang sehat?
"""

import numpy as np
import pandas as pd
import yfinance as yf
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from datetime import datetime
import time
import warnings
from app.collectors.hyperliquid_collector import get_hl_crypto_data
warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════
#  WATCHLIST REGISTRY
# ══════════════════════════════════════════════════════════════════

WATCHLISTS = {
    "IDX": [
        # Blue chips + likuid IDX
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
        "BYAN.JK", "TPIA.JK", "ICBP.JK", "UNVR.JK", "KLBF.JK",
        "BSDE.JK", "CPIN.JK", "INDF.JK", "MIKA.JK", "HMSP.JK",
        "SIDO.JK", "PTBA.JK", "ADRO.JK", "MDKA.JK", "GOTO.JK",
    ],
    "US": [
        # Mega-cap + high-beta tech + ETF proxy
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
        "AMD", "AVGO", "ORCL", "CRM", "NFLX", "PLTR", "COIN",
        "SPY", "QQQ", "SMCI", "ARM", "MSTR", "RDDT",
    ],
    "CRYPTO": [
        # Top crypto via yFinance (fallback ke Binance di endpoint)
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
        "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "DOT-USD",
        "PEPE-USD", "SUI-USD", "NEAR-USD", "APT-USD", "INJ-USD",
    ],
}


# ══════════════════════════════════════════════════════════════════
#  DATA FETCHER (ringan, hanya ambil 90 hari)
# ══════════════════════════════════════════════════════════════════

def _fetch_df_screener(ticker: str) -> Optional[pd.DataFrame]:
    """
    Fetch data OHLCV dengan fitur Auto-Retry untuk menghindari API Rate Limit.
    """
    is_crypto = ticker.endswith('-USD') or ticker.endswith('USDT')

    if is_crypto:
        # (Biarkan logika crypto pakai Binance/Hyperliquid lu di sini)
        # df, _, _, _ = get_hl_crypto_data(...)
        df, _, _, _ = get_hl_crypto_data(ticker.replace("-USD", "USDT"), "1D")
        pass
    else:
        # Fallback ke Yahoo Finance dengan 3x Retry
        for attempt in range(3): 
            try:
                # Kasih jeda sepersekian detik biar nggak disangka spammer
                time.sleep(0.2) 
                
                df = yf.download(ticker, period="90d", interval="1d",
                                 progress=False, auto_adjust=True)
                
                if df is not None and not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    if 'Close' in df.columns:
                        return df.dropna(subset=['Close'])
                        
            except Exception as e:
                # Kalau gagal, tunggu setengah detik lalu coba lagi
                time.sleep(0.5) 
                continue
                
        # Kalau udah 3 kali nyoba tetep gagal
        print(f"⚠️ Gagal narik data {ticker} setelah 3x percobaan.")
        return None


# ══════════════════════════════════════════════════════════════════
#  5 METRIC CALCULATORS (masing-masing independen & cepat)
# ══════════════════════════════════════════════════════════════════

def _score_sortino(df: pd.DataFrame) -> tuple[float, str]:
    """
    [30 pts] Sortino Ratio — Return per unit downside risk.
    Threshold institusi: Sortino > 1.0 = excellent, > 0.5 = acceptable.
    """
    try:
        close    = df['Close'].dropna()
        log_ret  = np.log(close / close.shift(1)).dropna()
        if len(log_ret) < 10:
            return 0.0, "N/A"

        ann_ret  = float(log_ret.mean() * 252)
        downside = log_ret[log_ret < 0]
        if downside.empty:
            return 30.0, "EXCEPTIONAL"

        down_vol = float(downside.std() * np.sqrt(252))
        sortino  = (ann_ret - 0.05) / down_vol if down_vol > 0 else 0.0

        if   sortino >= 1.5:  return 30.0, f"{sortino:.2f} ✦✦✦"
        elif sortino >= 1.0:  return 25.0, f"{sortino:.2f} ✦✦"
        elif sortino >= 0.5:  return 18.0, f"{sortino:.2f} ✦"
        elif sortino >= 0.0:  return 10.0, f"{sortino:.2f} ~"
        else:                 return  0.0, f"{sortino:.2f} ✗"
    except Exception:
        return 0.0, "ERR"


def _score_regime(df: pd.DataFrame) -> tuple[float, str]:
    """
    [25 pts] HMM Regime — State pasar tersembunyi.
    Implementasi ringan: hanya pakai return clustering percentile
    tanpa full EM iteration agar cepat di batch scan.
    """
    try:
        close   = df['Close'].dropna().values.astype(float)
        returns = np.diff(np.log(close))
        if len(returns) < 20:
            return 12.5, "INSUFFICIENT_DATA"

        # Simple percentile regime proxy (mirip HMM initialization step)
        mean_ret  = np.mean(returns)
        std_ret   = np.std(returns)
        recent_14 = returns[-14:]
        recent_mean = np.mean(recent_14)
        recent_vol  = np.std(recent_14)

        # Volatility clustering check
        hist_vol    = std_ret * np.sqrt(252)
        recent_vol_ann = recent_vol * np.sqrt(252)
        vol_ratio   = recent_vol_ann / hist_vol if hist_vol > 0 else 1.0

        # Regime determination
        if recent_mean > 0 and vol_ratio < 1.2:
            regime = "LOW_VOL_BULLISH"
            score  = 25.0
        elif recent_mean < -mean_ret and vol_ratio > 1.5:
            regime = "HIGH_VOL_BEARISH"
            score  = 0.0
        elif abs(recent_mean) < std_ret * 0.3:
            regime = "SIDEWAYS_CHOP"
            score  = 10.0
        elif recent_mean > 0:
            regime = "MILD_BULLISH"
            score  = 18.0
        else:
            regime = "MILD_BEARISH"
            score  = 5.0

        return score, regime
    except Exception:
        return 12.5, "ERR"


def _score_momentum(df: pd.DataFrame) -> tuple[float, str]:
    """
    [20 pts] Momentum 20D ROC + Acceleration.
    Momentum kuat = ROC positif DAN sedang mengakselerasi.
    """
    try:
        close = df['Close'].dropna()
        n     = len(close)
        if n < 25:
            return 10.0, "N/A"

        roc_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100)
        roc_10 = float((close.iloc[-1] / close.iloc[-11] - 1) * 100)
        roc_5  = float((close.iloc[-1] / close.iloc[-6]  - 1) * 100)

        # Acceleration: apakah momentum makin kuat ke depan?
        accelerating = (roc_5 > roc_10 > 0) or (roc_5 > 0 and roc_20 > 0)
        decelerating = roc_5 < 0 < roc_20

        if   roc_20 > 5  and accelerating: return 20.0, f"+{roc_20:.1f}% ACCEL ↑"
        elif roc_20 > 2  and accelerating: return 17.0, f"+{roc_20:.1f}% ↑"
        elif roc_20 > 0  and not decelerating: return 13.0, f"+{roc_20:.1f}% →"
        elif roc_20 > -2 and roc_5 > 0:   return  8.0, f"{roc_20:.1f}% recovering"
        elif decelerating:                 return  3.0, f"{roc_20:.1f}% DECAY ↓"
        else:                              return  0.0, f"{roc_20:.1f}% ✗"
    except Exception:
        return 10.0, "ERR"


def _score_zscore(df: pd.DataFrame) -> tuple[float, str]:
    """
    [15 pts] Z-Score anti-overbought filter.
    Beli mahal = rugi. Harga yang sudah terlalu tinggi secara statistik = penalti.
    """
    try:
        close  = df['Close'].dropna()
        if len(close) < 20:
            return 7.5, "N/A"

        window       = 20
        rolling_mean = close.rolling(window).mean()
        rolling_std  = close.rolling(window).std()
        zscore       = float((close.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1])

        if   zscore < -2.0: return 15.0, f"Z={zscore:.2f} OVERSOLD ✦"  # Perfect entry zone
        elif zscore < -1.0: return 13.0, f"Z={zscore:.2f} DISCOUNTED"
        elif zscore < 0.5:  return 12.0, f"Z={zscore:.2f} FAIR"
        elif zscore < 1.5:  return  8.0, f"Z={zscore:.2f} EXTENDED"
        elif zscore < 2.5:  return  3.0, f"Z={zscore:.2f} OVERBOUGHT"
        else:               return  0.0, f"Z={zscore:.2f} EXTREME ✗"
    except Exception:
        return 7.5, "ERR"


def _score_volatility(df: pd.DataFrame) -> tuple[float, str]:
    """
    [10 pts] Volatility health check.
    Vol terlalu tinggi = risiko tidak terprediksi. Vol terlalu rendah = complacency.
    Sweet spot: 15–40% annualized.
    """
    try:
        close   = df['Close'].dropna()
        log_ret = np.log(close / close.shift(1)).dropna()
        if len(log_ret) < 10:
            return 5.0, "N/A"

        vol_ann = float(log_ret.std() * np.sqrt(252) * 100)

        if   15 <= vol_ann <= 30: return 10.0, f"{vol_ann:.0f}% IDEAL"
        elif 10 <= vol_ann <= 45: return  8.0, f"{vol_ann:.0f}% OK"
        elif  5 <= vol_ann <= 60: return  5.0, f"{vol_ann:.0f}% HIGH"
        elif vol_ann > 60:        return  0.0, f"{vol_ann:.0f}% EXTREME"
        else:                     return  3.0, f"{vol_ann:.0f}% LOW"
    except Exception:
        return 5.0, "ERR"


# ══════════════════════════════════════════════════════════════════
#  CORE SCORING LOGIC
# ══════════════════════════════════════════════════════════════════

def score_ticker_from_df(df: pd.DataFrame) -> Dict:
    """
    Hitung skor komposit dari DataFrame yang disediakan.
    Sangat berguna untuk backtesting atau live streaming.
    """
    if df is None or df.empty:
        return {"error": "No data", "score": 0, "status": "REJECTED"}

    try:
        # Run 5 scorers
        s_pts, s_lbl = _score_sortino(df)
        r_pts, r_lbl = _score_regime(df)
        m_pts, m_lbl = _score_momentum(df)
        z_pts, z_lbl = _score_zscore(df)
        v_pts, v_lbl = _score_volatility(df)

        total = round(s_pts + r_pts + m_pts + z_pts + v_pts, 1)

        # Status Gate
        if total >= 70:
            status, tag = "SATIN_READY", "🟢"
        elif total >= 50:
            status, tag = "MARGINAL", "🟡"
        else:
            status, tag = "REJECTED", "🔴"

        # Current price
        price = float(df['Close'].iloc[-1])

        # 3-day change %
        change_3d = None
        if len(df) >= 4:
            change_3d = round((df['Close'].iloc[-1] / df['Close'].iloc[-4] - 1) * 100, 2)

        return {
            "score"      : total,
            "status"     : status,
            "status_tag" : tag,
            "sortino"    : {"pts": round(s_pts, 1), "label": s_lbl, "max": 30},
            "regime"     : {"pts": round(r_pts, 1), "label": r_lbl, "max": 25},
            "momentum"   : {"pts": round(m_pts, 1), "label": m_lbl, "max": 20},
            "zscore"     : {"pts": round(z_pts, 1), "label": z_lbl, "max": 15},
            "volatility" : {"pts": round(v_pts, 1), "label": v_lbl, "max": 10},
            "price"      : round(price, 4),
            "change_3d"  : change_3d,
        }
    except Exception as e:
        return {"error": str(e), "score": 0, "status": "REJECTED"}


# ══════════════════════════════════════════════════════════════════
#  COMPOSITE SCORER
# ══════════════════════════════════════════════════════════════════

def _compute_score(ticker: str, market: str) -> Dict:
    """
    Jalankan semua 5 metric untuk satu ticker dan return skor komposit.
    Fungsi ini dipanggil paralel oleh ThreadPoolExecutor.
    """
    start = time.time()
    df    = _fetch_df_screener(ticker)

    if df is None or df.empty:
        return {
            "ticker"    : ticker,
            "market"    : market,
            "score"     : 0,
            "status"    : "REJECTED",
            "error"     : "No data"
        }

    res = score_ticker_from_df(df)
    elapsed = round((time.time() - start) * 1000, 1)
    
    res.update({
        "ticker"  : ticker,
        "market"  : market,
        "scan_ms" : elapsed
    })
    return res


# ══════════════════════════════════════════════════════════════════
#  MAIN SCREENER — Entry Point
# ══════════════════════════════════════════════════════════════════

def run_screener(
    markets     : List[str] = ["IDX", "US", "CRYPTO"],
    min_score   : float     = 0,
    max_workers : int       = 8,
    custom_tickers: Optional[List[str]] = None
) -> Dict:
    """
    Jalankan screener untuk semua ticker di watchlist yang dipilih.

    Args:
        markets        : List market yang di-scan ["IDX", "US", "CRYPTO"]
        min_score      : Filter minimum score (0 = tampilkan semua)
        max_workers    : Thread paralel (lebih tinggi = lebih cepat, lebih banyak request)
        custom_tickers : Override dengan custom list ticker

    Returns:
        Dict berisi ranked_list, summary, dan metadata scan
    """
    scan_start = time.time()

    # Bangun task list
    tasks = []
    if custom_tickers:
        for t in custom_tickers:
            tasks.append((t, "CUSTOM"))
    else:
        for market in markets:
            wl = WATCHLISTS.get(market.upper(), [])
            for ticker in wl:
                tasks.append((ticker, market.upper()))

    if not tasks:
        return {"error": "Tidak ada ticker untuk di-scan."}

    results = []

    # Parallel execution
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_compute_score, ticker, market): (ticker, market)
            for ticker, market in tasks
        }
        for future in as_completed(future_map):
            try:
                result = future.result(timeout=30)
                if result.get("score", 0) >= min_score:
                    results.append(result)
            except Exception as e:
                ticker, market = future_map[future]
                results.append({
                    "ticker": ticker, "market": market,
                    "score": 0, "status": "REJECTED",
                    "status_tag": "🔴", "error": str(e)
                })

    # Sort by score descending
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Segmentasi
    satin_ready = [r for r in results if r["status"] == "SATIN_READY"]
    marginal    = [r for r in results if r["status"] == "MARGINAL"]
    rejected    = [r for r in results if r["status"] == "REJECTED"]

    # Top pick per market
    top_picks = {}
    for market in (markets if not custom_tickers else ["CUSTOM"]):
        candidates = [r for r in satin_ready if r.get("market") == market.upper()]
        if candidates:
            top_picks[market] = candidates[0]

    elapsed_total = round(time.time() - scan_start, 2)

    return {
        "scan_metadata": {
            "timestamp"       : datetime.now().isoformat(),
            "markets_scanned" : markets,
            "total_scanned"   : len(results),
            "scan_duration_s" : elapsed_total,
            "threads_used"    : max_workers,
        },
        "summary": {
            "satin_ready_count": len(satin_ready),
            "marginal_count"   : len(marginal),
            "rejected_count"   : len(rejected),
            "top_score"        : results[0]["score"] if results else 0,
            "avg_score"        : round(np.mean([r["score"] for r in results]), 1) if results else 0,
        },
        "top_picks"    : top_picks,    # Best 1 per market
        "satin_ready"  : satin_ready,  # All green
        "marginal"     : marginal,     # All yellow
        "rejected"     : rejected,     # All red (bisa dihide di frontend)
        "ranked_list"  : results,      # Full sorted list
    }


# ══════════════════════════════════════════════════════════════════
#  SCORING EXPLANATION (untuk ditampilkan di UI)
# ══════════════════════════════════════════════════════════════════

SCORE_LEGEND = {
    "dimensions": {
        "sortino"   : {"max": 30, "desc": "Risk-adjusted return quality (Sortino Ratio)"},
        "regime"    : {"max": 25, "desc": "Market state via HMM-proxy regime detection"},
        "momentum"  : {"max": 20, "desc": "Trend strength via 20D ROC + acceleration"},
        "zscore"    : {"max": 15, "desc": "Statistical price position (anti-overbought)"},
        "volatility": {"max": 10, "desc": "Volatility health check (15-40% sweet spot)"},
    },
    "thresholds": {
        "SATIN_READY": {"min": 70, "color": "green",  "desc": "Layak dianalisis lebih dalam & pertimbangkan entry"},
        "MARGINAL"   : {"min": 50, "color": "yellow", "desc": "Setup belum ideal, tunggu konfirmasi tambahan"},
        "REJECTED"   : {"min":  0, "color": "red",    "desc": "Kondisi tidak mendukung, skip ticker ini"},
    }
}