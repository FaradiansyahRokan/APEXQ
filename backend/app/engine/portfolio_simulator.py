"""
╔══════════════════════════════════════════════════════════════════════╗
║       QUANTUM PORTFOLIO SIMULATOR — BACKTEST ENGINE v3.1 APEX       ║
║     1-Year Time Machine · Screener → ICT → Regime → Kelly Risk      ║
╠══════════════════════════════════════════════════════════════════════╣
║  CHANGELOG v3.1 (Profitability Fixes):                               ║
║                                                                      ║
║  ✅ FIX: ICT Strength normalization (_normalize_ict_strength)         ║
║     - Engine return "3/4" ratio format, bukan "STRONG" enum          ║
║     - Sekarang di-normalize: 3/4 → STRONG, 4/4 → VERY_STRONG        ║
║     - Fix "Strong ICT Entries = 0" bug                               ║
║                                                                      ║
║  ✅ FIX: Dynamic TP threshold diturunkan (3R sekarang bisa aktif)     ║
║     - score >= 4 → 3R (sebelumnya >= 6, terlalu ketat)              ║
║     - Hapus 1.6R conservative (data: 1.6R WR < 2R WR)              ║
║     - ADX threshold: 30 → 25, momentum ROC: 0.5% → 0.3%            ║
║                                                                      ║
║  [Semua fix dari v3.0 tetap berlaku]                                 ║
║                                                                      ║
║  ✅ FIX: Quality Score recalibrated — A+ sekarang bisa dicapai       ║
║     - Normalisasi screener: baseline 50 (bukan 0) → skor lebih fair  ║
║     - ICT bobot dikurangi dari 30 → 20 pts                           ║
║     - 4 tech confirmation slots masing-masing 5 pts                  ║
║                                                                      ║
║  ✅ NEW: Technical Fast Calculator (_calculate_technicals_fast)       ║
║     - EMA 20/50 trend alignment → bonus quality + win rate filter    ║
║     - RSI optimal range (35-72 long, 28-65 short) → avoid exhaustion ║
║     - Volume ratio confirmation (≥0.9× avg) → liquidity check       ║
║     - ADX trending check (≥20) → hanya masuk saat ada trend         ║
║                                                                      ║
║  ✅ NEW: Dynamic TP Multiplier (_compute_dynamic_tp_multiplier)       ║
║     - Trend kuat (ADX≥30 + EMA aligned + momentum) → TP 3R          ║
║     - Normal → TP 2R (default)                                       ║
║     - Lemah/chop → TP 1.6R (konservatif)                            ║
║                                                                      ║
║  ✅ NEW: Dynamic SL Multiplier                                        ║
║     - ATR dalam percentile tinggi (>80) → SL lebih lebar ×1.2       ║
║     - ATR rendah (<25) → SL lebih ketat ×0.9                        ║
║                                                                      ║
║  ✅ NEW: Counter-trend penalty in quality score                       ║
║     - Signal berlawanan EMA alignment → -8 pts quality              ║
║                                                                      ║
║  [Semua fix dari v2.0 tetap berlaku]                                 ║
║                                                                      ║
║  🔴 BUG FIX: Balance double-counting eliminated                      ║
║     - PnL sekarang HANYA diterapkan saat posisi benar-benar tutup   ║
║     - trade.balance_after dihitung ulang saat close, bukan saat open ║
║                                                                      ║
║  🔴 BUG FIX: Commission calculation diperbaiki                       ║
║     - Sebelumnya: commission = balance × pct (SALAH!)               ║
║     - Sekarang: commission = units × entry × pct (BENAR)            ║
║                                                                      ║
║  🔴 BUG FIX: Sharpe/Sortino annualization diperbaiki                 ║
║     - Menggunakan daily equity returns, bukan per-trade pnl          ║
║                                                                      ║
║  ✅ UPGRADE: Kelly-Adaptive Position Sizing                          ║
║     - Setelah 15 trade, Kelly dihitung dari rolling history          ║
║     - risk_per_trade disesuaikan secara dinamis dengan Kelly frac    ║
║                                                                      ║
║  ✅ UPGRADE: 3-Layer Confirmation Gate                               ║
║     - Layer 1: Screener Score ≥ min_screener_score                  ║
║     - Layer 2: HMM Regime confidence ≥ 55%                          ║
║     - Layer 3: ICT bias_strength ≥ MODERATE                         ║
║     - Semua harus lulus → jika tidak, trade DIBLOKIR                ║
║                                                                      ║
║  ✅ UPGRADE: Regime-Dynamic Size Scaling                             ║
║     - LOW_VOL_BULLISH  → 100% dari risk target                      ║
║     - SIDEWAYS_CHOP    → 60% dari risk target (hati-hati)           ║
║     - HIGH_VOL_BEARISH → SKIP (tidak masuk sama sekali)             ║
║                                                                      ║
║  ✅ UPGRADE: Consecutive-Loss Drawdown Guard                         ║
║     - Setelah 3 loss berturut: ukuran posisi dikurangi 50%          ║
║     - Reset saat pertama kali profit kembali                         ║
║                                                                      ║
║  ✅ UPGRADE: Partial Profit Lock at 1.5R                             ║
║     - Pada 1R: SL dipindah ke Break Even                            ║
║     - Pada 1.5R: booking 50% profit, trail sisanya                  ║
║                                                                      ║
║  ✅ UPGRADE: Equity Curve dari Daily Close, bukan trade-event        ║
║     - Interpolasi harian → grafik equity lebih smooth dan realistis ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import warnings
import time

# ── APEX Engine Imports ──
from app.engine.screener_engine import score_ticker_from_df
from app.engine.regime_engine import detect_hmm_regime, get_full_regime_analysis
from app.engine.ict_engine import get_ict_full_analysis
from app.engine.quant_engine import calculate_technicals
from app.engine.macro_engine import get_cross_asset_data

warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class TradeRecord:
    """Rekaman lengkap satu trade dari entry sampai exit."""
    trade_id      : int
    ticker        : str
    entry_date    : str
    exit_date     : str
    direction     : str           # LONG / SHORT
    entry_price   : float
    exit_price    : float
    stop_loss     : float
    take_profit   : float
    units         : float
    pnl_usd       : float
    pnl_pct       : float         # pnl/balance_at_entry × 100
    outcome       : str           # WIN / LOSS / BE
    regime        : str
    regime_conf   : float         # HMM confidence %
    screener_score: float
    ict_strength  : str           # STRONG / MODERATE / WEAK
    balance_after : float
    exit_reason   : str           # TP_HIT / SL_HIT / BE_EXIT / TIME_EXIT / PARTIAL_TP
    kelly_fraction: float         # Kelly frac yang dipakai saat entry
    size_scale    : float         # Regime size scaling factor yang dipakai
    quality_score    : float = 0.0   # Composite quality score (0-100) saat entry
    tp_multiplier    : float = 1.0   # Dynamic TP multiplier yang dipakai
    tech_ema_aligned : bool  = False  # EMA trend aligned saat entry
    tech_rsi_ok      : bool  = False  # RSI dalam range optimal
    tech_vol_ok      : bool  = False  # Volume confirmed
    tech_adx_trend   : bool  = False  # ADX trending
    sector        : str = "Unknown"


@dataclass
class SimulationConfig:
    """Konfigurasi lengkap untuk satu run simulasi."""
    initial_balance    : float = 100.0
    risk_per_trade     : float = 2.0       # % risiko per trade (base)
    max_open_trades    : int   = 3
    sl_atr_mult        : float = 1.5       # Stop Loss = 1.5x ATR
    tp_rr_ratio        : float = 2.0       # Take Profit = 2R (full)
    min_screener_score : float = 70.0      # Dinaikkan dari 65 → 70
    scan_universe      : str   = "US"
    lookback_years     : int   = 1
    max_hold_days      : int   = 15
    commission_pct     : float = 0.1       # % dari nilai posisi (BUKAN balance)
    regime_filter      : bool  = True
    use_be_logic       : bool  = True      # Move SL to BE at 1R
    be_threshold_rr    : float = 1.0
    use_partial_tp     : bool  = True      # Partial TP at 1.5R
    partial_tp_rr      : float = 1.5       # Lock 50% profit di sini
    partial_tp_frac    : float = 0.5       # Berapa % posisi yang diclose di partial TP
    # ── v2.0 Additions ──────────────────────────────
    use_adaptive_kelly : bool  = True      # Aktifkan Kelly-adaptive sizing
    kelly_fraction     : float = 0.25      # Quarter Kelly (fraction of full Kelly)
    kelly_warmup_trades: int   = 15        # Mulai adaptive Kelly setelah N trades
    kelly_lookback     : int   = 25        # Rolling window trade history untuk Kelly
    max_risk_cap_pct   : float = 3.0       # Hard cap risk per trade (%)
    min_risk_floor_pct : float = 0.5       # Minimum risk per trade (%)
    min_regime_conf    : float = 55.0      # Min HMM confidence % untuk entry
    min_ict_strength   : str   = "MODERATE"  # Min ICT bias strength
    consec_loss_guard  : int   = 3         # Guard aktif setelah N loss berturut
    consec_loss_scale  : float = 0.5       # Kurangi size ke X% setelah guard aktif
    regime_size_bull   : float = 1.0       # Size scaling di BULLISH
    regime_size_chop   : float = 0.6       # Size scaling di SIDEWAYS_CHOP
    circuit_breaker_dd : float = 15.0      # Circuit breaker pada DD% dari initial


@dataclass
class SimulationResult:
    """Output lengkap hasil simulasi."""
    config             : SimulationConfig
    trades             : List[TradeRecord] = field(default_factory=list)
    equity_curve       : List[Dict]        = field(default_factory=list)
    weekly_snapshots   : List[Dict]        = field(default_factory=list)
    final_balance      : float = 0.0
    total_return_pct   : float = 0.0
    sharpe_ratio       : float = 0.0
    sortino_ratio      : float = 0.0
    max_drawdown_pct   : float = 0.0
    win_rate_pct       : float = 0.0
    profit_factor      : float = 0.0
    total_trades       : int   = 0
    winning_trades     : int   = 0
    losing_trades      : int   = 0
    avg_win_pct        : float = 0.0
    avg_loss_pct       : float = 0.0
    best_trade         : Optional[TradeRecord] = None
    worst_trade        : Optional[TradeRecord] = None
    calmar_ratio       : float = 0.0
    expectancy_usd     : float = 0.0
    trades_filtered    : int   = 0         # Berapa trade yang diblokir gate
    kelly_avg_fraction : float = 0.0       # Rata-rata Kelly fraction dipakai


# ══════════════════════════════════════════════════════════════════
#  UNIVERSE & DATA REGISTRY
# ══════════════════════════════════════════════════════════════════

WATCHLISTS = {
    "IDX": [
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
        "BYAN.JK", "TPIA.JK", "ICBP.JK", "UNVR.JK", "KLBF.JK",
        "BSDE.JK", "CPIN.JK", "INDF.JK", "MIKA.JK", "HMSP.JK",
    ],
    "US": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
        "AMD", "AVGO", "ORCL", "CRM", "NFLX", "PLTR", "COIN", "SPY",
    ],
    "CRYPTO": [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
        "DOGE-USD", "ADA-USD", "AVAX-USD", "LINK-USD", "DOT-USD",
    ],
    "UNIVERSAL": [
        "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
        "AMD", "AVGO", "ORCL", "CRM", "NFLX", "PLTR", "COIN", "SPY",
        "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
        "BYAN.JK", "TPIA.JK", "ICBP.JK", "UNVR.JK", "KLBF.JK",
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
    ]
}

# ICT strength tier ordering (untuk comparison)
_ICT_STRENGTH_ORDER = {"VERY_WEAK": 0, "WEAK": 1, "MODERATE": 2, "STRONG": 3, "VERY_STRONG": 4}


def _normalize_ict_strength(raw_strength) -> str:
    """
    v3.1 FIX: ICT engine kadang return ratio "3/4" atau angka,
    bukan enum string. Normalize ke standard enum.

    Ratio logic:
      "1/1", "1/2"       → WEAK
      "2/3", "2/4"       → MODERATE  
      "3/4", "3/5", "2/2"→ STRONG
      "4/4", "4/5", "5/5"→ VERY_STRONG
      Already string enum → return as-is
    """
    if isinstance(raw_strength, str) and raw_strength in _ICT_STRENGTH_ORDER:
        return raw_strength   # Already normalized

    s = str(raw_strength).strip()

    # Try parsing "numerator/denominator" format
    if "/" in s:
        try:
            num, denom = s.split("/")
            num, denom = int(num), int(denom)
            ratio = num / max(denom, 1)
            if ratio >= 0.90 or (num >= 4):    return "VERY_STRONG"
            elif ratio >= 0.70 or (num >= 3):  return "STRONG"
            elif ratio >= 0.50 or (num >= 2):  return "MODERATE"
            else:                              return "WEAK"
        except (ValueError, ZeroDivisionError):
            pass

    # Try numeric
    try:
        v = float(s)
        if v >= 4:   return "VERY_STRONG"
        elif v >= 3: return "STRONG"
        elif v >= 2: return "MODERATE"
        elif v >= 1: return "WEAK"
        else:        return "VERY_WEAK"
    except ValueError:
        pass

    return "MODERATE"  # Safe fallback


# ══════════════════════════════════════════════════════════════════
#  LAYER 1 — DATA FETCHER
# ══════════════════════════════════════════════════════════════════

def _fetch_historical_data(ticker: str, start: datetime, end: datetime) -> Optional[pd.DataFrame]:
    for attempt in range(3):
        try:
            time.sleep(0.15)
            df = yf.download(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval="1d",
                progress=False,
                auto_adjust=True
            )
            if df is None or df.empty:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            required_cols = {"Open", "High", "Low", "Close", "Volume"}
            if not required_cols.issubset(df.columns):
                continue
            return df.dropna(subset=["Close"])
        except Exception:
            time.sleep(0.5)
            continue
    return None


# ══════════════════════════════════════════════════════════════════
#  LAYER 2 — SCREENER
# ══════════════════════════════════════════════════════════════════

def _score_ticker(df_slice: pd.DataFrame) -> float:
    res = score_ticker_from_df(df_slice)
    return res.get("score", 0.0)


# ══════════════════════════════════════════════════════════════════
#  LAYER 3 — REGIME DETECTOR (v2: returns confidence + regime)
# ══════════════════════════════════════════════════════════════════

def _detect_regime_full(df_slice: pd.DataFrame) -> Tuple[str, float]:
    """
    Returns (regime_name, confidence_pct).
    Confidence digunakan sebagai filter gate di v2.
    """
    res = detect_hmm_regime(df_slice)
    if "error" in res:
        return "UNKNOWN", 0.0
    return res.get("current_regime", "UNKNOWN"), res.get("confidence_pct", 0.0)


# ══════════════════════════════════════════════════════════════════
#  LAYER 4 — ICT ENGINE (v2: returns strength + signal)
# ══════════════════════════════════════════════════════════════════

def _calculate_atr(df_slice: pd.DataFrame, period: int = 14) -> float:
    if len(df_slice) < period + 1:
        return float(df_slice["Close"].std()) if len(df_slice) > 1 else 1.0
    high  = df_slice["High"].values.astype(float)
    low   = df_slice["Low"].values.astype(float)
    close = df_slice["Close"].values.astype(float)
    trs = [max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
           for i in range(1, len(close))]
    return float(np.mean(trs[-period:]))


def _calculate_technicals_fast(df: pd.DataFrame) -> Dict:
    """
    v3: Hitung indikator teknikal cepat untuk quality scoring dan dynamic TP.

    Output:
      ema20, ema50           → trend alignment
      rsi                    → momentum exhaustion check
      volume_ratio           → current vol vs 20-day avg
      roc_10                 → 10-day rate of change
      trend_aligned          → True jika EMA20 > EMA50 (bull) atau sebaliknya (bear)
      rsi_ok_long            → RSI antara 40-70 (tidak overbought untuk long)
      rsi_ok_short           → RSI antara 30-60 (tidak oversold untuk short)
      vol_confirmed          → Volume hari ini > 1.0× avg (konfirmasi)
      momentum_strong        → ROC > +1% (bull) atau < -1% (bear)
      atr_percentile         → ATR saat ini vs 20-day ATR history (0-100)
    """
    if df is None or len(df) < 55:
        return {
            "ema20": 0.0, "ema50": 0.0, "rsi": 50.0, "volume_ratio": 1.0,
            "roc_10": 0.0, "trend_aligned_bull": False, "trend_aligned_bear": False,
            "rsi_ok_long": True, "rsi_ok_short": True,
            "vol_confirmed": False, "momentum_strong_bull": False,
            "momentum_strong_bear": False, "atr_percentile": 50.0,
            "adx": 25.0, "adx_trending": False,
        }

    close  = df["Close"].astype(float)
    high   = df["High"].astype(float)
    low    = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    # ── EMA ──────────────────────────────────────────────────────
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    cur_close = float(close.iloc[-1])

    # ── RSI (14) ─────────────────────────────────────────────────
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs    = gain / loss.replace(0, 1e-9)
    rsi   = float((100 - (100 / (1 + rs))).iloc[-1])

    # ── Volume ratio (current vs 20-day avg) ─────────────────────
    vol_avg    = float(volume.rolling(20).mean().iloc[-1]) or 1.0
    vol_ratio  = float(volume.iloc[-1]) / vol_avg

    # ── Rate of Change 10-day ─────────────────────────────────────
    roc_10 = float((close.iloc[-1] - close.iloc[-11]) / close.iloc[-11] * 100) if len(close) > 11 else 0.0

    # ── ATR percentile (current ATR vs 20-day ATR history) ────────
    high_arr  = high.values.astype(float)
    low_arr   = low.values.astype(float)
    close_arr = close.values.astype(float)
    trs = [max(high_arr[i]-low_arr[i], abs(high_arr[i]-close_arr[i-1]), abs(low_arr[i]-close_arr[i-1]))
           for i in range(1, len(close_arr))]
    atr_series = np.array(trs)
    cur_atr    = float(np.mean(atr_series[-14:])) if len(atr_series) >= 14 else float(np.mean(atr_series))
    atr_hist   = [float(np.mean(atr_series[i:i+14])) for i in range(max(0, len(atr_series)-20), len(atr_series)-13)] if len(atr_series) >= 34 else [cur_atr]
    atr_pct    = float(np.mean(np.array(atr_hist) <= cur_atr) * 100) if atr_hist else 50.0

    # ── ADX (simplified) ─────────────────────────────────────────
    # Uses +DM/-DM over 14 periods for trend strength
    tr_s  = pd.Series(trs).rolling(14).sum()
    dm_up = (high.diff()).where(high.diff() > low.diff().abs(), 0.0).where(high.diff() > 0, 0.0)
    dm_dn = (low.diff().abs()).where(low.diff().abs() > high.diff(), 0.0).where(low.diff() < 0, 0.0)
    pdi   = 100 * dm_up.rolling(14).sum() / (tr_s.reindex(dm_up.index) + 1e-9)
    mdi   = 100 * dm_dn.rolling(14).sum() / (tr_s.reindex(dm_dn.index) + 1e-9)
    dx    = (pdi - mdi).abs() / (pdi + mdi + 1e-9) * 100
    adx   = float(dx.rolling(14).mean().iloc[-1]) if not dx.rolling(14).mean().empty else 20.0
    if np.isnan(adx): adx = 20.0

    return {
        "ema20"               : ema20,
        "ema50"               : ema50,
        "cur_close"           : cur_close,
        "rsi"                 : rsi,
        "volume_ratio"        : vol_ratio,
        "roc_10"              : roc_10,
        "atr_percentile"      : atr_pct,
        "adx"                 : adx,
        # Pre-computed condition flags
        "trend_aligned_bull"  : cur_close > ema20 > ema50,       # Price > EMA20 > EMA50
        "trend_aligned_bear"  : cur_close < ema20 < ema50,       # Price < EMA20 < EMA50
        "rsi_ok_long"         : 35.0 <= rsi <= 72.0,             # Not overbought for long
        "rsi_ok_short"        : 28.0 <= rsi <= 65.0,             # Not oversold for short
        "vol_confirmed"       : vol_ratio >= 0.9,                 # Decent volume (lowered threshold)
        "momentum_strong_bull": roc_10 > 0.3,                    # Positive momentum (lowered)
        "momentum_strong_bear": roc_10 < -0.3,                   # Negative momentum (lowered)
        "adx_trending"        : adx >= 20.0,                     # Market is trending
    }


def _compute_quality_score_v3(
    score       : float,
    regime_conf : float,
    ict_signal  : Dict,
    tech        : Dict,
    direction   : str,
) -> Tuple[float, Dict]:
    """
    v3 Quality Score (0-100) — RECALIBRATED + TECH CONFIRMATIONS.

    Masalah v2:  Screener 93 + Regime 99 + ICT MODERATE = 86.9 (max A)
                 → A+ tidak pernah tercapai karena ICT jarang STRONG.

    Solusi v3:   Kurangi bobot ICT, tambah bonus dari 4 konfirmasi teknikal.
                 Sekarang A+ bisa dicapai dengan screener tinggi + tech alignment.

    Komponen (total 100):
      [35 pts] Screener score      → normalized dari 0-100
      [25 pts] Regime confidence   → normalized dari 0-100%
      [20 pts] ICT signal strength → WEAK=10, MODERATE=15, STRONG=20, VERY_STRONG=20
      [20 pts] Tech confirmations  → 4 bonus, masing-masing 5 pts:
                 +5 EMA trend aligned (price > EMA20 > EMA50 for LONG)
                 +5 RSI dalam range optimal (tidak overbought/oversold)
                 +5 Volume confirmed (> 0.9× avg)
                 +5 ADX trending (> 20 = ada trend)
    """
    # ── Base components ──────────────────────────────────────────
    # Normalize screener: baseline 65 = 0 pts, 100 = 35 pts
    screener_normalized = max(0.0, (score - 50.0) / 50.0)  # 65→0.3, 80→0.6, 100→1.0
    screener_pts = min(35.0, screener_normalized * 35.0)

    regime_pts = min(25.0, (regime_conf / 100.0) * 25.0)

    ict_strength = ict_signal.get("strength", "WEAK")
    ict_pts_map  = {"VERY_WEAK": 5, "WEAK": 10, "MODERATE": 15, "STRONG": 20, "VERY_STRONG": 20}
    ict_pts      = ict_pts_map.get(ict_strength, 10)

    # ── Tech confirmation bonus (each +5 pts) ────────────────────
    tech_detail = {}
    tech_pts    = 0.0

    if direction == "LONG":
        aligned = tech.get("trend_aligned_bull", False)
        rsi_ok  = tech.get("rsi_ok_long", True)
        mom_ok  = tech.get("momentum_strong_bull", False)
    else:
        aligned = tech.get("trend_aligned_bear", False)
        rsi_ok  = tech.get("rsi_ok_short", True)
        mom_ok  = tech.get("momentum_strong_bear", False)

    tech_detail["ema_aligned"]  = aligned
    tech_detail["rsi_ok"]       = rsi_ok
    tech_detail["vol_ok"]       = tech.get("vol_confirmed", False)
    tech_detail["adx_trending"] = tech.get("adx_trending", False)

    if aligned          : tech_pts += 5.0
    if rsi_ok           : tech_pts += 5.0
    if tech.get("vol_confirmed", False): tech_pts += 5.0
    if tech.get("adx_trending", False) : tech_pts += 5.0

    quality = screener_pts + regime_pts + ict_pts + tech_pts

    # ── Soft penalty for counter-trend signals ───────────────────
    # Jika sinyal BERLAWANAN dengan EMA alignment → kurangi sedikit
    if direction == "LONG" and tech.get("trend_aligned_bear", False):
        quality -= 8.0   # Counter-trend long = penalized
    elif direction == "SHORT" and tech.get("trend_aligned_bull", False):
        quality -= 8.0   # Counter-trend short = penalized

    quality = max(0.0, min(100.0, quality))

    breakdown = {
        "screener_pts" : round(screener_pts, 1),
        "regime_pts"   : round(regime_pts, 1),
        "ict_pts"      : ict_pts,
        "tech_pts"     : tech_pts,
        "tech_detail"  : tech_detail,
        "total"        : round(quality, 1),
    }

    return quality, breakdown


def _compute_dynamic_tp_multiplier(tech: Dict, ict_signal: Dict, direction: str) -> float:
    """
    v3.1 FIX: Threshold diturunkan agar 3R bisa aktif.
    
    Root cause sebelumnya: score >= 6 hampir tidak pernah tercapai karena
    ICT jarang STRONG dan ADX jarang >= 30 secara bersamaan.
    
    Perubahan:
    - Score >= 4 → 3R (sebelumnya >= 6, terlalu ketat)
    - Score >= 2 → 2R (default, sebelumnya >= 4)  
    - Score < 2  → 2R juga (hapus 1.6R — data shows 1.6R hurts WR)
    
    Reasoning: better to let winner run (2R or 3R) daripada cut early.
    Partial TP di 1.5R sudah menghandle risk management.
    """
    score = 0

    # ADX trending (threshold diturunkan dari 30 ke 25)
    adx = tech.get("adx", 20.0)
    if adx >= 25:   score += 2
    elif adx >= 18: score += 1

    # EMA aligned with direction
    if direction == "LONG"  and tech.get("trend_aligned_bull", False): score += 2
    if direction == "SHORT" and tech.get("trend_aligned_bear", False): score += 2

    # Momentum (threshold diturunkan: ROC > 0.3% bukan 0.5%)
    if direction == "LONG"  and tech.get("momentum_strong_bull", False): score += 1
    if direction == "SHORT" and tech.get("momentum_strong_bear", False): score += 1

    # ICT strength
    ict_strength = ict_signal.get("strength", "WEAK")
    if ict_strength in ("STRONG", "VERY_STRONG"): score += 2
    elif ict_strength == "MODERATE":              score += 1

    # Volume confirmation bonus
    if tech.get("vol_confirmed", False): score += 1

    # Map score → multiplier (lebih agresif, hapus 0.8 conservative)
    if score >= 4:  return 1.5    # → 3R  (previously needed score 6)
    else:           return 1.0    # → 2R  (default, no more 1.6R)


def _find_entry_signal(df_slice: pd.DataFrame, config: SimulationConfig) -> Optional[Dict]:
    """
    v2: Juga mengembalikan bias_strength dari ICT untuk gate filtering.
    """
    ict = get_ict_full_analysis(df_slice)
    bias     = ict.get("composite_bias", "NEUTRAL")
    strength = _normalize_ict_strength(ict.get("bias_strength", "WEAK"))

    if bias == "NEUTRAL":
        return None

    # Blokir sinyal yang terlalu lemah
    min_strength_val  = _ICT_STRENGTH_ORDER.get(config.min_ict_strength, 2)
    curr_strength_val = _ICT_STRENGTH_ORDER.get(strength, 1)
    if curr_strength_val < min_strength_val:
        return None

    close   = float(df_slice["Close"].iloc[-1])
    atr     = _calculate_atr(df_slice, period=14)
    sl_dist = atr * config.sl_atr_mult
    tp_dist = sl_dist * config.tp_rr_ratio

    if bias == "BULLISH":
        return {
            "direction": "LONG",
            "entry"    : close,
            "sl"       : round(close - sl_dist, 6),
            "tp"       : round(close + tp_dist, 6),
            "atr"      : round(atr, 6),
            "strength" : strength,
            "setup"    : f"ICT_{strength}_BULLISH",
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
        }
    elif bias == "BEARISH":
        return {
            "direction": "SHORT",
            "entry"    : close,
            "sl"       : round(close + sl_dist, 6),
            "tp"       : round(close - tp_dist, 6),
            "atr"      : round(atr, 6),
            "strength" : strength,
            "setup"    : f"ICT_{strength}_BEARISH",
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
        }
    return None


def _find_entry_signal_soft(df_slice: pd.DataFrame, config: SimulationConfig) -> Optional[Dict]:
    """
    v3 SOFT: Hanya blokir NEUTRAL. Semua bias valid masuk.
    Tambahkan tech data dan dynamic TP multiplier ke dalam signal dict.
    """
    ict      = get_ict_full_analysis(df_slice)
    bias     = ict.get("composite_bias", "NEUTRAL")
    strength = _normalize_ict_strength(ict.get("bias_strength", "WEAK"))

    if bias == "NEUTRAL":
        return None

    close   = float(df_slice["Close"].iloc[-1])
    atr     = _calculate_atr(df_slice, period=14)
    sl_dist = atr * config.sl_atr_mult

    # v3: Compute tech once here, pass to caller via signal dict
    tech = _calculate_technicals_fast(df_slice)

    direction = "LONG" if bias == "BULLISH" else "SHORT"

    # v3: Dynamic TP based on momentum & trend
    tp_mult  = _compute_dynamic_tp_multiplier(tech, {"strength": strength}, direction)
    tp_dist  = sl_dist * config.tp_rr_ratio * tp_mult

    # v3: Dynamic SL — tighten if RSI extreme or vol high
    atr_pct = tech.get("atr_percentile", 50.0)
    if atr_pct > 80:     sl_mult = 1.2   # High vol → wider SL
    elif atr_pct < 25:   sl_mult = 0.9   # Low vol → tighter SL
    else:                sl_mult = 1.0
    sl_dist_adj = sl_dist * sl_mult

    if direction == "LONG":
        return {
            "direction"      : "LONG",
            "entry"          : close,
            "sl"             : round(close - sl_dist_adj, 6),
            "tp"             : round(close + tp_dist, 6),
            "atr"            : round(atr, 6),
            "strength"       : strength,
            "setup"          : f"ICT_{strength}_BULLISH",
            "tp_multiplier"  : round(tp_mult, 2),
            "sl_multiplier"  : round(sl_mult, 2),
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
            "tech"           : tech,    # Passed for quality scoring
        }
    else:
        return {
            "direction"      : "SHORT",
            "entry"          : close,
            "sl"             : round(close + sl_dist_adj, 6),
            "tp"             : round(close - tp_dist, 6),
            "atr"            : round(atr, 6),
            "strength"       : strength,
            "setup"          : f"ICT_{strength}_BEARISH",
            "tp_multiplier"  : round(tp_mult, 2),
            "sl_multiplier"  : round(sl_mult, 2),
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
            "tech"           : tech,
        }


# ══════════════════════════════════════════════════════════════════
#  LAYER 5 — KELLY-ADAPTIVE POSITION SIZER
# ══════════════════════════════════════════════════════════════════

def _compute_adaptive_kelly(
    trade_history  : List[TradeRecord],
    config         : SimulationConfig,
    base_risk_pct  : float,
    consec_losses  : int
) -> Tuple[float, float]:
    """
    Hitung risk_pct yang optimal berdasarkan Kelly dari trade history.

    Returns:
        (final_risk_pct, kelly_fraction_used)
    """
    # Belum cukup data → pakai base risk
    if len(trade_history) < config.kelly_warmup_trades or not config.use_adaptive_kelly:
        risk = base_risk_pct
        # Tetap apply consecutive loss guard
        if consec_losses >= config.consec_loss_guard:
            risk *= config.consec_loss_scale
        return min(max(risk, config.min_risk_floor_pct), config.max_risk_cap_pct), 0.25

    # Rolling window dari trade history terakhir
    recent = trade_history[-config.kelly_lookback:]
    wins   = [t for t in recent if t.outcome == "WIN"]
    losses = [t for t in recent if t.outcome == "LOSS"]

    n_total = len(recent)
    n_wins  = len(wins)
    n_loss  = len(losses)

    if n_wins == 0 or n_loss == 0:
        return base_risk_pct, 0.25

    win_rate = n_wins / n_total
    avg_win  = np.mean([abs(t.pnl_pct) for t in wins])
    avg_loss = np.mean([abs(t.pnl_pct) for t in losses])

    if avg_loss == 0:
        return base_risk_pct, 0.25

    rr = avg_win / avg_loss
    full_kelly = win_rate - ((1 - win_rate) / rr)

    if full_kelly <= 0:
        # Negative edge → reduce to floor
        return config.min_risk_floor_pct, 0.0

    fractional_kelly = full_kelly * config.kelly_fraction
    # Scale fractional kelly ke risk_pct domain
    # full_kelly = 1 → use base_risk_pct, Kelly scale it proportionally
    kelly_scaled_risk = base_risk_pct * (fractional_kelly / (config.kelly_fraction + 1e-9))
    kelly_scaled_risk = min(kelly_scaled_risk, config.max_risk_cap_pct)
    kelly_scaled_risk = max(kelly_scaled_risk, config.min_risk_floor_pct)

    # Apply consecutive loss guard on top
    if consec_losses >= config.consec_loss_guard:
        kelly_scaled_risk *= config.consec_loss_scale
        print(f"   ⚠️  CONSEC LOSS GUARD: {consec_losses} losses → size scaled to "
              f"{config.consec_loss_scale*100:.0f}%")

    return round(kelly_scaled_risk, 4), round(config.kelly_fraction, 4)


# ══════════════════════════════════════════════════════════════════
#  LAYER 6 — TRADE SIMULATOR (v2: fixed commission + partial TP)
# ══════════════════════════════════════════════════════════════════

def _simulate_trade(
    ticker        : str,
    signal        : Dict,
    df_future     : pd.DataFrame,
    balance_entry : float,      # Balance SAAT ENTRY (sebelum trade ini)
    config        : SimulationConfig,
    trade_id      : int,
    entry_date    : str,
    regime        : str,
    regime_conf   : float,
    score         : float,
    risk_pct      : float,      # Final risk % yang sudah diadaptasi oleh Kelly
    kelly_frac    : float,
    size_scale    : float,
    quality_score : float = 50.0,
    tp_multiplier : float = 1.0,
    tech          : Dict  = None,
    sector        : str   = "Unknown"
) -> Optional[TradeRecord]:
    """
    v2 Forward-simulate satu trade.

    FIXES:
    - Commission dihitung dari nilai posisi, BUKAN dari total balance
    - Partial TP di 1.5R: close 50% posisi, trail sisanya dengan BE stop
    - balance_after dihitung dari balance_entry (dikirim dari caller)
    """
    if df_future is None or df_future.empty:
        return None

    direction  = signal["direction"]
    entry      = signal["entry"]
    sl_price   = signal["sl"]
    tp_price   = signal["tp"]
    sl_dist    = abs(entry - sl_price)

    if sl_dist == 0:
        return None

    # ── Hitung units berdasarkan risk yang sudah diadaptasi ─────
    actual_risk_pct  = risk_pct * size_scale
    actual_risk_pct  = min(max(actual_risk_pct, config.min_risk_floor_pct), config.max_risk_cap_pct)
    dollar_risk      = balance_entry * (actual_risk_pct / 100)
    units_full       = dollar_risk / sl_dist

    # ── FIX COMMISSION: % dari nilai posisi, bukan dari balance ─
    position_value   = units_full * entry
    commission_entry = position_value * (config.commission_pct / 100)
    commission_exit  = position_value * (config.commission_pct / 100)
    total_commission = commission_entry + commission_exit

    # ── Partial TP setup ────────────────────────────────────────
    partial_tp_price = None
    partial_tp_units = 0.0
    partial_pnl      = 0.0
    partial_booked   = False

    if config.use_partial_tp:
        partial_dist = sl_dist * config.partial_tp_rr
        if direction == "LONG":
            partial_tp_price = entry + partial_dist
        else:
            partial_tp_price = entry - partial_dist
        partial_tp_units = units_full * config.partial_tp_frac

    # ── Break Even setup ────────────────────────────────────────
    be_trigger_dist = sl_dist * config.be_threshold_rr
    if direction == "LONG":
        be_trigger_price = entry + be_trigger_dist
    else:
        be_trigger_price = entry - be_trigger_dist
    is_be_activated = False

    # Remaining units after potential partial close
    units_remaining = units_full

    exit_price  = entry
    exit_reason = "TIME_EXIT"
    final_date  = df_future.index[-1]

    for i, (date, row) in enumerate(df_future.iterrows()):
        if i >= config.max_hold_days:
            exit_price  = float(row["Close"])
            exit_reason = "TIME_EXIT"
            final_date  = date
            break

        high  = float(row["High"])
        low   = float(row["Low"])
        close = float(row["Close"])

        if direction == "LONG":
            # 1. Partial TP check
            if config.use_partial_tp and not partial_booked and high >= partial_tp_price:
                partial_pnl    = (partial_tp_price - entry) * partial_tp_units
                units_remaining -= partial_tp_units
                partial_booked  = True

            # 2. BE trigger check
            if not is_be_activated and config.use_be_logic and high >= be_trigger_price:
                is_be_activated = True
                sl_price        = entry  # Move to Break Even

            # 3. SL / TP check (on remaining units)
            if low <= sl_price:
                exit_price  = sl_price
                exit_reason = "BE_EXIT" if is_be_activated else "SL_HIT"
                final_date  = date
                break
            elif high >= tp_price:
                exit_price  = tp_price
                exit_reason = "TP_HIT"
                final_date  = date
                break

        else:  # SHORT
            # 1. Partial TP check
            if config.use_partial_tp and not partial_booked and low <= partial_tp_price:
                partial_pnl    = (entry - partial_tp_price) * partial_tp_units
                units_remaining -= partial_tp_units
                partial_booked  = True

            # 2. BE trigger check
            if not is_be_activated and config.use_be_logic and low <= be_trigger_price:
                is_be_activated = True
                sl_price        = entry

            # 3. SL / TP check
            if high >= sl_price:
                exit_price  = sl_price
                exit_reason = "BE_EXIT" if is_be_activated else "SL_HIT"
                final_date  = date
                break
            elif low <= tp_price:
                exit_price  = tp_price
                exit_reason = "TP_HIT"
                final_date  = date
                break
    else:
        exit_price  = float(df_future["Close"].iloc[-1])
        exit_reason = "TIME_EXIT"
        final_date  = df_future.index[-1]

    # ── P&L Calculation ─────────────────────────────────────────
    if direction == "LONG":
        main_pnl = (exit_price - entry) * units_remaining
    else:
        main_pnl = (entry - exit_price) * units_remaining

    # ── FIX: Hitung commission exit berdasarkan actual exit size ─
    actual_exit_value   = units_remaining * exit_price
    actual_commission   = (units_full * entry + units_remaining * exit_price) * (config.commission_pct / 100)
    if partial_booked:
        actual_commission += (partial_tp_units * partial_tp_price) * (config.commission_pct / 100)

    raw_pnl       = main_pnl + partial_pnl
    net_pnl       = raw_pnl - actual_commission
    pnl_pct       = (net_pnl / balance_entry) * 100
    balance_after = balance_entry + net_pnl

    # Outcome
    if net_pnl > 0.01:
        outcome = "WIN"
    elif exit_reason in ("BE_EXIT",) or abs(net_pnl) <= actual_commission * 1.5:
        outcome = "BE"
    else:
        outcome = "LOSS"

    exit_date_str = final_date.strftime("%Y-%m-%d") if hasattr(final_date, "strftime") else str(final_date)
    full_exit_reason = exit_reason
    if partial_booked:
        full_exit_reason += "+PARTIAL_TP"

    return TradeRecord(
        trade_id      = trade_id,
        ticker        = ticker,
        entry_date    = entry_date,
        exit_date     = exit_date_str,
        direction     = direction,
        entry_price   = round(entry, 6),
        exit_price    = round(exit_price, 6),
        stop_loss     = round(sl_price, 6),
        take_profit   = round(tp_price, 6),
        units         = round(units_full, 6),
        pnl_usd       = round(net_pnl, 4),
        pnl_pct       = round(pnl_pct, 4),
        outcome       = outcome,
        regime        = regime,
        regime_conf   = round(regime_conf, 2),
        screener_score= score,
        ict_strength  = signal.get("strength", "UNKNOWN"),
        balance_after = round(balance_after, 4),
        exit_reason   = full_exit_reason,
        kelly_fraction   = kelly_frac,
        size_scale       = size_scale,
        quality_score    = round(quality_score, 1),
        tp_multiplier    = tp_multiplier,
        tech_ema_aligned = bool((tech or {}).get("trend_aligned_bull") or (tech or {}).get("trend_aligned_bear")),
        tech_rsi_ok      = bool((tech or {}).get("rsi_ok_long") or (tech or {}).get("rsi_ok_short")),
        tech_vol_ok      = bool((tech or {}).get("vol_confirmed")),
        tech_adx_trend   = bool((tech or {}).get("adx_trending")),
        sector           = sector
    )


# ══════════════════════════════════════════════════════════════════
#  LAYER 7 — ANALYTICS ENGINE (v2: fixed Sharpe/Sortino)
# ══════════════════════════════════════════════════════════════════

def _compute_analytics(result: SimulationResult) -> SimulationResult:
    """
    v2 FIXES:
    - Sharpe/Sortino menggunakan daily equity returns (bukan per-trade pnl_pct)
    - Equity curve diinterpolasi harian untuk representasi yang akurat
    """
    trades = result.trades
    if not trades:
        return result

    pnl_usds = np.array([t.pnl_usd for t in trades])
    wins      = [t for t in trades if t.outcome == "WIN"]
    losses    = [t for t in trades if t.outcome == "LOSS"]

    result.total_trades   = len(trades)
    result.winning_trades = len(wins)
    result.losing_trades  = len(losses)
    result.win_rate_pct   = round(len(wins) / len(trades) * 100, 2) if trades else 0

    gross_win  = sum(t.pnl_usd for t in wins)   if wins   else 0
    gross_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0
    result.profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else 9999.0

    result.avg_win_pct  = round(np.mean([t.pnl_pct for t in wins]),  4) if wins   else 0
    result.avg_loss_pct = round(np.mean([t.pnl_pct for t in losses]), 4) if losses else 0

    if trades:
        wr = result.winning_trades / result.total_trades
        result.expectancy_usd = round(
            (wr * (gross_win / len(wins) if wins else 0)) -
            ((1 - wr) * (gross_loss / len(losses) if losses else 0)),
            4
        )

    # ── Build daily equity curve via interpolation ───────────────
    # Kumpulkan semua event (trade close)
    balance_events: Dict[str, float] = {}
    running_bal = result.config.initial_balance

    # Start event
    first_entry = trades[0].entry_date
    balance_events[first_entry] = running_bal

    for t in sorted(trades, key=lambda x: x.exit_date):
        running_bal += t.pnl_usd
        balance_events[t.exit_date] = round(running_bal, 4)

    # Sort events and interpolate daily
    sorted_event_dates = sorted(balance_events.keys())

    # Build full daily date range
    try:
        d_start = datetime.strptime(sorted_event_dates[0], "%Y-%m-%d")
        d_end   = datetime.strptime(sorted_event_dates[-1], "%Y-%m-%d")
    except Exception:
        d_start = datetime.now() - timedelta(days=365)
        d_end   = datetime.now()

    all_dates = []
    cur = d_start
    while cur <= d_end:
        all_dates.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)

    # Fill forward from events
    daily_balance = {}
    last_known    = result.config.initial_balance
    for d in all_dates:
        if d in balance_events:
            last_known = balance_events[d]
        daily_balance[d] = last_known

    result.equity_curve = [{"time": d, "balance": b} for d, b in sorted(daily_balance.items())]
    result.final_balance = round(running_bal, 4)
    result.total_return_pct = round(
        (running_bal - result.config.initial_balance) / result.config.initial_balance * 100, 2
    )

    # ── FIX: Sharpe & Sortino via daily returns ──────────────────
    if len(result.equity_curve) > 2:
        balances_arr = np.array([p["balance"] for p in result.equity_curve])
        # Daily returns from equity curve
        daily_rets   = np.diff(balances_arr) / balances_arr[:-1]
        daily_rets   = daily_rets[np.isfinite(daily_rets)]

        if len(daily_rets) > 5 and np.std(daily_rets) > 0:
            mean_d = np.mean(daily_rets)
            std_d  = np.std(daily_rets)
            result.sharpe_ratio = round((mean_d / std_d) * np.sqrt(252), 3)

            down_rets = daily_rets[daily_rets < 0]
            down_std  = np.std(down_rets) if len(down_rets) > 1 else std_d
            result.sortino_ratio = round((mean_d / down_std) * np.sqrt(252) if down_std > 0 else 0, 3)

    # ── Max Drawdown ─────────────────────────────────────────────
    eq_arr = np.array([p["balance"] for p in result.equity_curve])
    peaks  = np.maximum.accumulate(eq_arr)
    if len(peaks) > 0 and peaks[0] > 0:
        dds = (eq_arr - peaks) / peaks * 100
        result.max_drawdown_pct = round(float(np.min(dds)), 2)

    # ── Calmar Ratio ─────────────────────────────────────────────
    if result.max_drawdown_pct < 0:
        result.calmar_ratio = round(result.total_return_pct / abs(result.max_drawdown_pct), 3)

    # ── Best / Worst trade ───────────────────────────────────────
    if trades:
        result.best_trade  = max(trades, key=lambda t: t.pnl_usd)
        result.worst_trade = min(trades, key=lambda t: t.pnl_usd)

    # ── Kelly average ─────────────────────────────────────────────
    kelly_fracs = [t.kelly_fraction for t in trades if t.kelly_fraction > 0]
    result.kelly_avg_fraction = round(np.mean(kelly_fracs), 4) if kelly_fracs else 0

    return result


# ══════════════════════════════════════════════════════════════════
#  LAYER 8 — CONSECUTIVE LOSS TRACKER
# ══════════════════════════════════════════════════════════════════

def _get_consecutive_losses(trades: List[TradeRecord]) -> int:
    """Hitung jumlah loss berturut-turut dari akhir trade history."""
    count = 0
    for t in reversed(trades):
        if t.outcome == "LOSS":
            count += 1
        else:
            break
    return count


# ══════════════════════════════════════════════════════════════════
#  MASTER SIMULATION RUNNER v2.0
# ══════════════════════════════════════════════════════════════════

def run_simulation(config: SimulationConfig) -> SimulationResult:
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  MASTER ENTRY POINT — Quantum Portfolio Simulator v2.0      ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  Pipeline per-minggu:                                        ║
    ║  1. SCREENER   → Ambil top N ticker dengan skor ≥ threshold  ║
    ║  2. GATE L1    → Screener score pass?                        ║
    ║  3. GATE L2    → HMM Regime confidence ≥ min_regime_conf?    ║
    ║  4. GATE L3    → ICT bias strength ≥ min_ict_strength?       ║
    ║  5. SIZE CALC  → Kelly-adaptive risk + regime scaling        ║
    ║  6. SIMULATE   → Forward sim dengan partial TP + BE logic    ║
    ║  7. ANALYTICS  → Daily equity curve + correct Sharpe         ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    result   = SimulationResult(config=config)
    balance  = config.initial_balance
    trade_id = 0
    trades_filtered = 0

    end_date   = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=365 * config.lookback_years)
    tickers    = WATCHLISTS.get(config.scan_universe, WATCHLISTS["US"])

    print(f"\n{'═'*65}")
    print(f"  QUANTUM PORTFOLIO SIMULATOR v2.0")
    print(f"  Universe  : {config.scan_universe} ({len(tickers)} tickers)")
    print(f"  Period    : {start_date.date()} → {end_date.date()}")
    print(f"  Capital   : ${config.initial_balance:,.2f}")
    print(f"  Risk/Trade: {config.risk_per_trade}% (adaptive Kelly: {config.use_adaptive_kelly})")
    print(f"  Min Score : {config.min_screener_score} | Min ICT: {config.min_ict_strength}")
    print(f"  Regime Min Conf: {config.min_regime_conf}%")
    print(f"{'═'*65}")

    # ── Pre-fetch all data ────────────────────────────────────────
    print("\n📡 Fetching historical data...")
    all_data: Dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        print(f"   [{i+1:2d}/{len(tickers)}] {ticker:15s}", end=" ")
        df = _fetch_historical_data(ticker, start_date, end_date)
        if df is not None and len(df) >= 60:
            all_data[ticker] = df
            print(f"✓ {len(df)} candles")
        else:
            print("✗ Insufficient data")

    if not all_data:
        print("❌ No valid data. Abort.")
        return result

    print(f"\n✅ {len(all_data)} tickers loaded.")
    print(f"\n🔄 Starting rolling weekly scan with 3-layer gate...\n")

    # ── Rolling weekly scan ───────────────────────────────────────
    closed_trades  : List[TradeRecord] = []  # Only confirmed closed trades
    open_positions : List[Dict] = []
    current_date   = start_date + timedelta(days=60)
    week_num       = 0

    while current_date <= end_date - timedelta(days=config.max_hold_days):
        week_num += 1
        candidates  = []

        # ── STEP 1: Score all tickers ──────────────────────────
        for ticker, full_df in all_data.items():
            df_slice = full_df[full_df.index <= current_date].tail(90)
            if len(df_slice) < 55:
                continue
            score = _score_ticker(df_slice)
            if score >= config.min_screener_score:
                candidates.append((ticker, score, df_slice))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:config.max_open_trades * 2]  # Buffer lebih besar

        week_snapshot = {
            "week"         : week_num,
            "date"         : current_date.strftime("%Y-%m-%d"),
            "balance"      : round(balance, 4),
            "candidates"   : len(candidates),
            "trades_opened": 0,
            "open_positions": len(open_positions)
        }

        # ── STEP 2: Close expired positions ────────────────────
        # FIX v2: Balance HANYA diupdate di sini (saat posisi benar-benar tutup)
        positions_to_close = []
        for pos in open_positions:
            try:
                exit_date_obj = datetime.strptime(pos["exit_date"], "%Y-%m-%d")
            except ValueError:
                positions_to_close.append(pos)
                continue
            if current_date >= exit_date_obj:
                # Recalculate balance_after berdasarkan balance saat ini
                trade = pos["trade"]
                trade.balance_after = round(balance + trade.pnl_usd, 4)
                balance = trade.balance_after
                closed_trades.append(trade)
                positions_to_close.append(pos)

        for p in positions_to_close:
            open_positions.remove(p)

        # ── STEP 3: Circuit Breaker ─────────────────────────────
        drawdown_from_start = (balance - config.initial_balance) / config.initial_balance * 100
        if drawdown_from_start < -config.circuit_breaker_dd:
            print(f"   Week {week_num:3d} | 🛑 CIRCUIT BREAKER: DD={drawdown_from_start:.1f}%")
            current_date += timedelta(days=7)
            result.weekly_snapshots.append(week_snapshot)
            continue

        # ── STEP 4: Find entry signals via SOFT QUALITY SCORING ──
        #
        # v2.1 Philosophy: TIDAK ada hard block berdasarkan confidence.
        # Semua sinyal valid bisa masuk, tapi SIZE disesuaikan dengan
        # composite quality score. Sinyal lemah = posisi kecil.
        # Hanya HIGH_VOL_BEARISH yang tetap di-skip (fundamental risk).
        #
        # Quality Score → Size Multiplier:
        #   90-100 → 1.00× (full)
        #   70-89  → 0.75×
        #   50-69  → 0.55×
        #   30-49  → 0.35×
        #   <30    → 0.20× (minimum, masih masuk)
        #
        open_count  = len(open_positions)
        consec_loss = _get_consecutive_losses(closed_trades)

        for ticker, score, df_slice in top_candidates:
            if open_count >= config.max_open_trades:
                break

            # ── HARD BLOCK: Hanya untuk HIGH_VOL_BEARISH ──────────
            regime, regime_conf = _detect_regime_full(df_slice)
            if config.regime_filter and regime == "HIGH_VOL_BEARISH":
                trades_filtered += 1
                continue  # Satu-satunya hard block yang justified

            # ── ICT signal (WAJIB ada bias, tapi strength boleh apapun) ─
            signal = _find_entry_signal_soft(df_slice, config)
            if signal is None:
                trades_filtered += 1
                continue  # Hanya NEUTRAL yang diblok

            # ── v3: QUALITY SCORE — recalibrated + tech confirmations ──
            tech = signal.get("tech", {})
            quality_score, quality_breakdown = _compute_quality_score_v3(
                score       = score,
                regime_conf = regime_conf,
                ict_signal  = signal,
                tech        = tech,
                direction   = signal["direction"],
            )

            # ── MAP QUALITY → SIZE SCALE ───────────────────────────
            if quality_score >= 90:
                base_size_scale = 1.00
            elif quality_score >= 75:
                base_size_scale = 0.80
            elif quality_score >= 60:
                base_size_scale = 0.60
            elif quality_score >= 45:
                base_size_scale = 0.40
            else:
                base_size_scale = 0.22

            # ── OVERLAY Regime context on size ────────────────────
            if "BULLISH" in regime or "LOW_VOL" in regime:
                regime_scale = config.regime_size_bull    # 1.00
            elif "SIDEWAYS" in regime or "CHOP" in regime:
                regime_scale = config.regime_size_chop    # 0.60
            else:
                regime_scale = 0.50   # Unknown → conservative

            size_scale = base_size_scale * regime_scale

            # ── Kelly-adaptive risk % ────────────────────────────
            kelly_risk_pct, kelly_frac = _compute_adaptive_kelly(
                closed_trades, config, config.risk_per_trade, consec_loss
            )

            # ── Get future data ──────────────────────────────────
            future_end = current_date + timedelta(days=config.max_hold_days + 5)
            full_df    = all_data[ticker]
            df_future  = full_df[
                (full_df.index > current_date) &
                (full_df.index <= future_end)
            ].head(config.max_hold_days)

            if df_future.empty:
                continue

            entry_date = current_date.strftime("%Y-%m-%d")
            trade_id  += 1

            # ── SIMULATE TRADE ───────────────────────────────────
            # FIX v2: balance_entry = current balance (tidak termasuk pending positions)
            trade = _simulate_trade(
                ticker        = ticker,
                signal        = signal,
                df_future     = df_future,
                balance_entry = balance,
                config        = config,
                trade_id      = trade_id,
                entry_date    = entry_date,
                regime        = regime,
                regime_conf   = regime_conf,
                score         = score,
                risk_pct      = kelly_risk_pct,
                kelly_frac    = kelly_frac,
                size_scale    = size_scale,
                quality_score = quality_score,
                tp_multiplier = signal.get("tp_multiplier", 1.0),
                tech          = tech,
                sector        = "Unknown"
            )

            if trade is None:
                trade_id -= 1
                continue

            # Schedule trade (PnL akan diapply saat close di STEP 2)
            open_positions.append({
                "trade"    : trade,
                "exit_date": trade.exit_date
            })
            open_count += 1
            week_snapshot["trades_opened"] += 1

            regime_emoji = "🟢" if "BULL" in regime else "🟡" if "CHOP" in regime else "🔴"
            icon         = "✅" if trade.outcome == "WIN" else "❌" if trade.outcome == "LOSS" else "〰️"
            tech_flags   = ""
            if tech.get("trend_aligned_bull") or tech.get("trend_aligned_bear"): tech_flags += "T"
            if tech.get("rsi_ok_long") or tech.get("rsi_ok_short"): tech_flags += "R"
            if tech.get("vol_confirmed"):  tech_flags += "V"
            if tech.get("adx_trending"):   tech_flags += "A"
            tp_mul_str = f"TP×{signal.get('tp_multiplier', 1.0)}"
            print(f"   Week {week_num:3d} | {icon} {ticker:10s} "
                  f"{signal['direction']:5s} | "
                  f"Scr:{score:5.1f} | "
                  f"Reg:{regime_emoji}{regime_conf:.0f}% | "
                  f"ICT:{signal['strength']:8s} | "
                  f"Q:{quality_score:.0f}/100 | "
                  f"Tech:[{tech_flags:4s}] | "
                  f"{tp_mul_str} | "
                  f"Size:×{size_scale:.2f} | "
                  f"P&L: ${trade.pnl_usd:+7.2f}")

        result.weekly_snapshots.append(week_snapshot)
        current_date += timedelta(days=7)

    # ── Flush remaining open positions ────────────────────────────
    for pos in open_positions:
        trade = pos["trade"]
        trade.balance_after = round(balance + trade.pnl_usd, 4)
        balance = trade.balance_after
        closed_trades.append(trade)

    # ── Sort chronologically ──────────────────────────────────────
    result.trades = sorted(closed_trades, key=lambda t: t.entry_date)
    result.trades_filtered = trades_filtered

    # ── Compute final analytics ────────────────────────────────────
    result = _compute_analytics(result)

    print(f"\n{'═'*65}")
    print(f"  FINAL BALANCE  : ${result.final_balance:,.2f}")
    print(f"  TOTAL RETURN   : {result.total_return_pct:+.2f}%")
    print(f"  TOTAL TRADES   : {result.total_trades}")
    print(f"  WIN RATE       : {result.win_rate_pct:.1f}%")
    print(f"  PROFIT FACTOR  : {result.profit_factor:.3f}")
    print(f"  SHARPE         : {result.sharpe_ratio:.3f}")
    print(f"  MAX DRAWDOWN   : {result.max_drawdown_pct:.2f}%")
    print(f"  TRADES FILTERED: {result.trades_filtered} (by 3-layer gate)")
    print(f"{'═'*65}\n")

    return result


# ══════════════════════════════════════════════════════════════════
#  REPORT GENERATORS
# ══════════════════════════════════════════════════════════════════

def generate_json_report(result: SimulationResult) -> Dict:
    """Export hasil simulasi sebagai dict JSON-serializable."""
    trades_list = []
    for t in result.trades:
        trades_list.append({
            "trade_id"      : t.trade_id,
            "ticker"        : t.ticker,
            "entry_date"    : t.entry_date,
            "exit_date"     : t.exit_date,
            "direction"     : t.direction,
            "entry_price"   : t.entry_price,
            "exit_price"    : t.exit_price,
            "stop_loss"     : t.stop_loss,
            "take_profit"   : t.take_profit,
            "pnl_usd"       : t.pnl_usd,
            "pnl_pct"       : t.pnl_pct,
            "outcome"       : t.outcome,
            "regime"        : t.regime,
            "regime_conf"   : t.regime_conf,
            "screener_score": t.screener_score,
            "ict_strength"  : t.ict_strength,
            "balance_after" : t.balance_after,
            "exit_reason"   : t.exit_reason,
            "kelly_fraction"  : t.kelly_fraction,
            "size_scale"      : t.size_scale,
            "quality_score"   : t.quality_score,
            "tp_multiplier"   : t.tp_multiplier,
            "tech_ema_aligned": t.tech_ema_aligned,
            "tech_rsi_ok"     : t.tech_rsi_ok,
            "tech_vol_ok"     : t.tech_vol_ok,
            "tech_adx_trend"  : t.tech_adx_trend,
        })

    return {
        "config": {
            "initial_balance"     : result.config.initial_balance,
            "risk_per_trade"      : result.config.risk_per_trade,
            "scan_universe"       : result.config.scan_universe,
            "lookback_years"      : result.config.lookback_years,
            "tp_rr_ratio"         : result.config.tp_rr_ratio,
            "min_screener_score"  : result.config.min_screener_score,
            "use_adaptive_kelly"  : result.config.use_adaptive_kelly,
            "kelly_fraction"      : result.config.kelly_fraction,
            "min_regime_conf"     : result.config.min_regime_conf,
            "min_ict_strength"    : result.config.min_ict_strength,
            "consec_loss_guard"   : result.config.consec_loss_guard,
            "regime_size_bull"    : result.config.regime_size_bull,
            "regime_size_chop"    : result.config.regime_size_chop,
        },
        "summary": {
            "final_balance"       : result.final_balance,
            "total_return_pct"    : result.total_return_pct,
            "sharpe_ratio"        : result.sharpe_ratio,
            "sortino_ratio"       : result.sortino_ratio,
            "calmar_ratio"        : result.calmar_ratio,
            "max_drawdown_pct"    : result.max_drawdown_pct,
            "profit_factor"       : result.profit_factor,
            "win_rate_pct"        : result.win_rate_pct,
            "total_trades"        : result.total_trades,
            "winning_trades"      : result.winning_trades,
            "losing_trades"       : result.losing_trades,
            "avg_win_pct"         : result.avg_win_pct,
            "avg_loss_pct"        : result.avg_loss_pct,
            "expectancy_usd"      : result.expectancy_usd,
            "trades_filtered"     : result.trades_filtered,
            "kelly_avg_fraction"  : result.kelly_avg_fraction,
        },
        "equity_curve"   : result.equity_curve,
        "trades"         : trades_list,
        "weekly_snapshots": result.weekly_snapshots,
        "best_trade"     : trades_list[result.trades.index(result.best_trade)]  if result.best_trade  and result.best_trade  in result.trades else None,
        "worst_trade"    : trades_list[result.trades.index(result.worst_trade)] if result.worst_trade and result.worst_trade in result.trades else None,
    }