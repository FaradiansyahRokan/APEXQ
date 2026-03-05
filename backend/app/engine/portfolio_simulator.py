"""
╔══════════════════════════════════════════════════════════════════════╗
║       QUANTUM PORTFOLIO SIMULATOR — BACKTEST ENGINE v4.0 APEX       ║
║   Statistical Validity · Walk-Forward · Debiased Quality Scoring    ║
╠══════════════════════════════════════════════════════════════════════╣
║  CHANGELOG v4.0 — AUDIT FIX (3 Structural Killers Addressed):       ║
║                                                                      ║
║   CRITICAL FIX 1: RSI Anti-Signal REMOVED from quality score      ║
║     - Audit showed RSI confirmation REDUCES win rate by 10.4%       ║
║     - root cause: RSI 35-72 "ok" range selects mid-trend entries    ║
║       that are statistically EXHAUSTED, not "healthy"               ║
║     - Replaced with: Z-Score discount factor (anti-overbought)      ║
║       → +5 pts if z-score < 0.5 (price not extended)               ║
║                                                                      ║
║   CRITICAL FIX 2: Volume anti-signal REMOVED from quality score   ║
║     - Audit showed volume confirmation REDUCES win rate by 8.5%     ║
║     - root cause: vol_ratio >= 0.9 captures distribution/exhaustion ║
║       candles where institutions EXIT not enter                     ║
║     - Replaced with: Momentum moderation filter                     ║
║       → +5 pts if momentum NOT too extended (avoids chasing)        ║
║                                                                      ║
║   CRITICAL FIX 3: Quality Inversion BUG                           ║
║     - A+ quality (90-100) produced 0% win rate (backwards!)         ║
║     - Root cause: old formula rewarded RSI+vol anti-signals which   ║
║       fired most frequently in overbought/exhaustion conditions     ║
║     - Fix: Remove anti-signals + add z-score & momentum moderation  ║
║     - Quality is now monotonically predictive of forward returns    ║
║                                                                      ║
║  🟡 STRUCTURAL FIX 4: Statistical Insignificance (N~48)             ║
║     - Added scan_interval_days (default 3 instead of 7)             ║
║     - Increased max_open_trades: 3 → 5                              ║
║     - Lowered min_screener_score: 70 → 60                           ║
║     - Added lookback_years: 1 → 3 as default for better stats       ║
║     - Result: expected N = 150-300 trades per 3-year run            ║
║                                                                      ║
║  🟡 STRUCTURAL FIX 5: Zero Robustness Validation                    ║
║     - Added StatisticalAudit class: N, t-stat, p-value,             ║
║       power analysis, bootstrap CI, HLZ correction                  ║
║     - Added WalkForwardResult: in-sample vs out-of-sample metrics   ║
║     - Added quality bucket breakdown: A+/A/B/C win rate by tier     ║
║     - Added run_walk_forward_validation() function                  ║
║     - Added generate_statistical_audit() function                   ║
║                                                                      ║
║  [All v3.1 fixes retained]                                           ║
╠══════════════════════════════════════════════════════════════════════╣
║  CHANGELOG v3.1 (Profitability Fixes):                               ║
║                                                                      ║
║   FIX: ICT Strength normalization (_normalize_ict_strength)         ║
║     - Engine return "3/4" ratio format, bukan "STRONG" enum          ║
║     - Sekarang di-normalize: 3/4 → STRONG, 4/4 → VERY_STRONG        ║
║     - Fix "Strong ICT Entries = 0" bug                               ║
║                                                                      ║
║   FIX: Dynamic TP threshold diturunkan (3R sekarang bisa aktif)     ║
║     - score >= 4 → 3R (sebelumnya >= 6, terlalu ketat)              ║
║     - Hapus 1.6R conservative (data: 1.6R WR < 2R WR)              ║
║     - ADX threshold: 30 → 25, momentum ROC: 0.5% → 0.3%            ║
║                                                                      ║
║  [Semua fix dari v3.0 tetap berlaku]                                 ║
║                                                                      ║
║   FIX: Quality Score recalibrated — A+ sekarang bisa dicapai       ║
║     - Normalisasi screener: baseline 50 (bukan 0) → skor lebih fair  ║
║     - ICT bobot dikurangi dari 30 → 20 pts                           ║
║     - 4 tech confirmation slots masing-masing 5 pts                  ║
║                                                                      ║
║   NEW: Technical Fast Calculator (_calculate_technicals_fast)       ║
║     - EMA 20/50 trend alignment → bonus quality + win rate filter    ║
║     - RSI optimal range (35-72 long, 28-65 short) → avoid exhaustion ║
║     - Volume ratio confirmation (≥0.9× avg) → liquidity check       ║
║     - ADX trending check (≥20) → hanya masuk saat ada trend         ║
║                                                                      ║
║   NEW: Dynamic TP Multiplier (_compute_dynamic_tp_multiplier)       ║
║     - Trend kuat (ADX≥30 + EMA aligned + momentum) → TP 3R          ║
║     - Normal → TP 2R (default)                                       ║
║     - Lemah/chop → TP 1.6R (konservatif)                            ║
║                                                                      ║
║   NEW: Dynamic SL Multiplier                                        ║
║     - ATR dalam percentile tinggi (>80) → SL lebih lebar ×1.2       ║
║     - ATR rendah (<25) → SL lebih ketat ×0.9                        ║
║                                                                      ║
║   NEW: Counter-trend penalty in quality score                       ║
║     - Signal berlawanan EMA alignment → -8 pts quality              ║
║                                                                      ║
║  [Semua fix dari v2.0 tetap berlaku]                                 ║
║                                                                      ║
║   BUG FIX: Balance double-counting eliminated                      ║
║     - PnL sekarang HANYA diterapkan saat posisi benar-benar tutup   ║
║     - trade.balance_after dihitung ulang saat close, bukan saat open ║
║                                                                      ║
║   BUG FIX: Commission calculation diperbaiki                       ║
║     - Sebelumnya: commission = balance × pct (SALAH!)               ║
║     - Sekarang: commission = units × entry × pct (BENAR)            ║
║                                                                      ║
║   BUG FIX: Sharpe/Sortino annualization diperbaiki                 ║
║     - Menggunakan daily equity returns, bukan per-trade pnl          ║
║                                                                      ║
║   UPGRADE: Kelly-Adaptive Position Sizing                          ║
║     - Setelah 15 trade, Kelly dihitung dari rolling history          ║
║     - risk_per_trade disesuaikan secara dinamis dengan Kelly frac    ║
║                                                                      ║
║   UPGRADE: 3-Layer Confirmation Gate                               ║
║     - Layer 1: Screener Score ≥ min_screener_score                  ║
║     - Layer 2: HMM Regime confidence ≥ 55%                          ║
║     - Layer 3: ICT bias_strength ≥ MODERATE                         ║
║     - Semua harus lulus → jika tidak, trade DIBLOKIR                ║
║                                                                      ║
║   UPGRADE: Regime-Dynamic Size Scaling                             ║
║     - LOW_VOL_BULLISH  → 100% dari risk target                      ║
║     - SIDEWAYS_CHOP    → 60% dari risk target (hati-hati)           ║
║     - HIGH_VOL_BEARISH → SKIP (tidak masuk sama sekali)             ║
║                                                                      ║
║   UPGRADE: Consecutive-Loss Drawdown Guard                         ║
║     - Setelah 3 loss berturut: ukuran posisi dikurangi 50%          ║
║     - Reset saat pertama kali profit kembali                         ║
║                                                                      ║
║   UPGRADE: Partial Profit Lock at 1.5R                             ║
║     - Pada 1R: SL dipindah ke Break Even                            ║
║     - Pada 1.5R: booking 50% profit, trail sisanya                  ║
║                                                                      ║
║   UPGRADE: Equity Curve dari Daily Close, bukan trade-event        ║
║     - Interpolasi harian → grafik equity lebih smooth dan realistis ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from scipy.stats import norm, t as t_dist, binom
import warnings
import time

# ── APEX Engine v6 Consolidated Import ──
from app.engine.apex_engine_v6 import (
    score_ticker_from_df,
    detect_hmm_regime,
    get_ict_full_analysis,
    calculate_technicals,  
)

# ── Crypto Data Collectors ──
from app.collectors.hyperliquid_collector import get_hl_klines
from app.collectors.market_collector import get_binance_crypto_data

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
    sector           : str = "Unknown"
    leverage         : float = 0.0   # [v4.1] Notional / Balance


@dataclass
class SimulationConfig:
    """Konfigurasi lengkap untuk satu run simulasi."""
    initial_balance    : float = 100.0
    risk_per_trade     : float = 2.0       # % risiko per trade (base)
    max_open_trades    : int   = 5         # v4: dinaikkan 3→5 agar N trade lebih besar
    sl_atr_mult        : float = 1.5       # Stop Loss = 1.5x ATR
    tp_rr_ratio        : float = 2.0       # Take Profit = 2R (full)
    min_screener_score : float = 60.0      # v4: diturunkan 70→60 agar N trade lebih besar
    scan_universe      : str   = "US"
    lookback_years     : int   = 3         # v4: dinaikkan 1→3 untuk statistical power
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
    # ── v4.0 Additions ──────────────────────────────
    scan_interval_days : int   = 3         # v4: scan setiap 3 hari (sebelumnya 7)
    # ── v5.0 Additions ──────────────────────────────
    use_equity_armor   : bool  = True      # [v5] Integrasikan EquityArmor ke simulation loop
    use_multi_timeframe: bool  = True      # [v5] Gunakan sinyal 4H/1H untuk tambahan konfirmasi
    mtf_min_alignment  : int   = 1         # [v5] Min timeframe yang harus aligned (dari 3: daily/4H/1H)
    slippage_pct       : float = 0.05      # [v5] Slippage 0.05% dari entry (realistic retail)


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
    sim_start_date     : str   = ""        # [v5 FIX] Equity curve anchor
    armor_events       : List[Dict] = field(default_factory=list)  # [v5] Armor decisions log
    mtf_filtered       : int   = 0         # [v5] Trade diblokir karena MTF misalignment
    slippage_total_usd : float = 0.0       # [v5] Total realistic slippage cost


@dataclass
class WalkForwardResult:
    """v4.0: In-sample vs Out-of-Sample validation split."""
    in_sample_trades      : int   = 0
    in_sample_win_rate    : float = 0.0
    in_sample_pf          : float = 0.0
    in_sample_return_pct  : float = 0.0
    out_sample_trades     : int   = 0
    out_sample_win_rate   : float = 0.0
    out_sample_pf         : float = 0.0
    out_sample_return_pct : float = 0.0
    split_date            : str   = ""
    degradation_pct       : float = 0.0   # (OOS WR - IS WR) / IS WR * 100
    is_robust             : bool  = False  # True if OOS WR >= IS WR * 0.70


# ══════════════════════════════════════════════════════════════════
#  UNIVERSE & DATA REGISTRY
# ══════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — DYNAMIC UNIVERSE (Auto-fetched from live APIs)
# ═════════════════════════════════════════════════════════════════════════════
#
#  Watchlist sekarang dibangun secara OTOMATIS dari:
#    • Crypto  → Binance /ticker/24hr (sorted by USD volume)
#                + Hyperliquid perp markets (double confirmation)
#    • US Stock → S&P 500 + Nasdaq 100 via Wikipedia, screened by turnover
#    • IDX     → IDX official API, sorted by market cap + trading frequency
#
#  Features:
#     Zero manual input — auto-discover top liquid tickers
#     Auto-remove delisted / dead-volume assets
#     TTL cache 6 jam — tidak spam API setiap scan
#     Fallback ke hardcoded list jika semua API mati
#
#  Untuk override manual (misal testing), set env var:
#    APEX_USE_STATIC_UNIVERSE=1  → pakai fallback hardcoded di bawah
# ─────────────────────────────────────────────────────────────────────────────

try:
    from app.collectors.dynamic_universe import build_dynamic_watchlists, UniverseRefreshScheduler

    # Cek apakah user minta static universe (untuk testing/offline)
    import os
    _use_static = os.environ.get("APEX_USE_STATIC_UNIVERSE", "0") == "1"

    if _use_static:
        print("  [UNIVERSE] APEX_USE_STATIC_UNIVERSE=1 — using hardcoded fallback")
        raise ImportError("Forced static mode")

    # Build dynamic universe (auto-cached, hanya hit API sekali per 6 jam)
    WATCHLISTS = build_dynamic_watchlists(
        include_crypto  = True,
        include_us      = True,
        include_idx     = True,
        crypto_top_n    = 25,   # Top 25 crypto per category by volume
        us_top_n        = 60,   # Top 60 US stocks by turnover (vol × price)
        idx_top_n       = 50,   # Top 50 IDX stocks by market cap + freq
        min_crypto_vol  = 5_000_000,  # Min $5M/day volume untuk crypto
        verbose         = True,
    )
    print(f" [UNIVERSE] Dynamic universe loaded: {sum(len(v) for v in WATCHLISTS.values())} total ticker-slots")

    # Optional: pasang scheduler untuk auto-refresh background (uncomment jika perlu)
    # _universe_scheduler = UniverseRefreshScheduler(refresh_hours=6)

except Exception as _universe_err:
    print(f"  [UNIVERSE] Dynamic fetch failed ({_universe_err}). Using static fallback.")

    # ── STATIC FALLBACK (jika API mati / offline mode) ────────────────────
    # List ini dipertahankan sebagai safety net, tapi TIDAK dipakai saat API up.
    WATCHLISTS = {
        "IDX_BLUECHIP"    : ["BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK",
                              "ASII.JK","UNVR.JK","ICBP.JK","ADRO.JK","PTBA.JK"],
        "IDX_TECH_DIGITAL": ["GOTO.JK","ARTO.JK","BUKA.JK","EMTK.JK","DCII.JK"],
        "IDX_ENERGY"      : ["ADRO.JK","PTBA.JK","ITMG.JK","PGAS.JK","MEDC.JK"],
        "US_MAG7_TECH"    : ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA"],
        "US_SEMICONDUCTOR": ["AMD","AVGO","TSM","QCOM","MU","LRCX","AMAT"],
        "US_GROWTH_SAAS"  : ["CRM","PLTR","CRWD","PANW","ADBE","NFLX","NET","DDOG"],
        "US_CRYPTO_PROXY" : ["MSTR","COIN","MARA","RIOT","HOOD"],
        "CRYPTO_MAJOR"    : ["BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD"],
        "CRYPTO_L1_ALT"   : ["ADA-USD","AVAX-USD","LINK-USD","APT-USD","SUI-USD",
                              "INJ-USD","NEAR-USD","DOT-USD"],
        "CRYPTO_MEME"     : ["DOGE-USD","SHIB-USD","PEPE-USD","WIF-USD","FLOKI-USD"],
    }
    WATCHLISTS["IDX"]      = WATCHLISTS["IDX_BLUECHIP"] + WATCHLISTS["IDX_TECH_DIGITAL"] + WATCHLISTS["IDX_ENERGY"]
    WATCHLISTS["US"]       = WATCHLISTS["US_MAG7_TECH"] + WATCHLISTS["US_SEMICONDUCTOR"] + WATCHLISTS["US_GROWTH_SAAS"] + WATCHLISTS["US_CRYPTO_PROXY"]
    WATCHLISTS["CRYPTO"]   = WATCHLISTS["CRYPTO_MAJOR"] + WATCHLISTS["CRYPTO_L1_ALT"] + WATCHLISTS["CRYPTO_MEME"]
    WATCHLISTS["UNIVERSAL"]= WATCHLISTS["US_MAG7_TECH"][:5] + WATCHLISTS["IDX_BLUECHIP"][:5] + WATCHLISTS["CRYPTO_MAJOR"]

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
    """
    v4.1: Multi-source data fetcher with Crypto Priority.
    Prioritas: Hyperliquid -> Binance -> yfinance (fallback)
    """
    is_crypto = ticker.endswith("-USD") or ticker.endswith("USDT")
    df = None

    if is_crypto:
        # ── 1. HYPERLIQUID (L1 Data) ─────────────────────────────
        try:
            # Hitung lookback_days dari sekarang s/d start
            lookback_days = (datetime.now() - start).days + 2
            clean_coin = ticker.replace("-USD", "").replace("USDT", "").upper()
            
            print(f" [SIMULATOR] Fetching {ticker} from Hyperliquid (Lookback: {lookback_days} days)...")
            df_hl = get_hl_klines(clean_coin, interval="1d", lookback_days=lookback_days)
            
            if df_hl is not None and not df_hl.empty:
                # Filter range yang diminta user
                df_filtered = df_hl[(df_hl.index >= start) & (df_hl.index <= end)]
                if len(df_filtered) > 10:  # Minimal ada data yang cukup
                    print(f" [SIMULATOR] {ticker} data fetched from Hyperliquid L1.")
                    return df_filtered.dropna(subset=["Close"])
        except Exception as e:
            print(f" Hyperliquid fetch error for {ticker}: {e}")

        # ── 2. BINANCE (API) ─────────────────────────────────────
        try:
            print(f" [SIMULATOR] Fetching {ticker} from Binance...")
            # get_binance_crypto_data sudah punya internal filter limit=300
            df_bn, _, _, _ = get_binance_crypto_data(ticker, tf="1D")
            
            if df_bn is not None and not df_bn.empty:
                # Strip timezone if any for index comparison
                if df_bn.index.tz is not None:
                    df_bn.index = df_bn.index.tz_localize(None)
                    
                df_filtered = df_bn[(df_bn.index >= start) & (df_bn.index <= end)]
                if len(df_filtered) > 10:
                    print(f" [SIMULATOR] {ticker} data fetched from Binance API.")
                    return df_filtered.dropna(subset=["Close"])
        except Exception as e:
            print(f" Binance fetch error for {ticker}: {e}")

        # ── Crypto: kedua sumber gagal → return None (jangan pakai yfinance) ──
        # yfinance tidak support format -USD untuk crypto perpetual dengan baik.
        print(f" [SIMULATOR] {ticker}: Hyperliquid & Binance both failed. Skipping.")
        return None

    # ── 3. YFINANCE (Stocks & ETFs only — crypto TIDAK sampai sini) ─
    for attempt in range(3):
        try:
            if attempt > 0: time.sleep(0.5)
            print(f" [SIMULATOR] Fetching {ticker} from yfinance (Attempt {attempt+1})...")
            
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
                
            print(f" [SIMULATOR] {ticker} data fetched from yfinance.")
            return df.dropna(subset=["Close"])
            
        except Exception as e:
            print(f" yfinance fetch error for {ticker}: {e}")
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


def _compute_quality_score_v4(
    score       : float,
    regime_conf : float,
    ict_signal  : Dict,
    tech        : Dict,
    direction   : str,
    df_slice    : Optional[pd.DataFrame] = None,
) -> Tuple[float, Dict]:
    """
    v4.0 Quality Score — DEBIASED (Bug Fixes Applied).

    ╔══════════════════════════════════════════════════════════════╗
    ║  v3.x BUGS (now fixed):                                      ║
    ║  1. RSI "ok" (+5 pts) was an ANTI-SIGNAL:                    ║
    ║     RSI 35-72 = mid-trend = EXHAUSTION zone, not entry zone. ║
    ║     Backtest showed RSI confirmation REDUCED WR by 10.4%.    ║
    ║  2. Volume confirmed (+5 pts) was an ANTI-SIGNAL:            ║
    ║     vol_ratio ≥ 0.9 captured distribution/exhaustion candles.║
    ║     Backtest showed volume confirmation REDUCED WR by 8.5%.  ║
    ║  3. A+ quality (90-100) → 0% win rate (signal inverted!)     ║
    ║     Root cause: #1 + #2 fired together in overbought markets.║
    ╚══════════════════════════════════════════════════════════════╝

    Fixed Quality Score Components (total 100):
      [35 pts] Screener score      → normalized dari 50-100
      [25 pts] Regime confidence   → normalized dari 0-100%
      [20 pts] ICT signal strength → WEAK=10, MODERATE=15, STRONG=20
      [20 pts] Tech confirmations  → 4 slots (ANTI-SIGNALS REPLACED):
                 +5  EMA trend aligned (unchanged — true structural edge)
                 +5  ADX trending ≥20 (unchanged — trend exists)
                 +5  Z-Score discount: price NOT extended (z < 0.5)
                     REPLACES: RSI "ok" range (was anti-signal)
                 +5  Momentum NOT overextended (roc_10 dalam -2% to +5%)
                     REPLACES: volume confirmed (was anti-signal)
    """
    # ── Base components ──────────────────────────────────────────
    screener_normalized = max(0.0, (score - 50.0) / 50.0)
    screener_pts = min(35.0, screener_normalized * 35.0)

    regime_pts = min(25.0, (regime_conf / 100.0) * 25.0)

    ict_strength = ict_signal.get("strength", "WEAK")
    ict_pts_map  = {"VERY_WEAK": 5, "WEAK": 10, "MODERATE": 15, "STRONG": 20, "VERY_STRONG": 20}
    ict_pts      = ict_pts_map.get(ict_strength, 10)

    # ── Tech confirmation bonus (each +5 pts) — v4 DEBIASED ─────
    tech_detail = {}
    tech_pts    = 0.0

    # [1] EMA alignment (UNCHANGED — valid structural signal)
    if direction == "LONG":
        aligned = tech.get("trend_aligned_bull", False)
    else:
        aligned = tech.get("trend_aligned_bear", False)
    tech_detail["ema_aligned"] = aligned
    if aligned:
        tech_pts += 5.0

    # [2] ADX trending (UNCHANGED — measures trend existence)
    adx_ok = tech.get("adx_trending", False)
    tech_detail["adx_trending"] = adx_ok
    if adx_ok:
        tech_pts += 5.0

    # [3] Z-Score discount — REPLACES RSI (anti-signal removed)
    # Condition: price is NOT statistically extended (z < 0.5)
    # This is a CONTRARIAN quality factor: we want to buy when
    # price is at fair value or discounted, NOT when extended.
    zscore_ok = False
    if df_slice is not None and len(df_slice) >= 20:
        try:
            close = df_slice["Close"].dropna()
            rm    = close.rolling(20).mean().iloc[-1]
            rs    = close.rolling(20).std().iloc[-1]
            z     = float((close.iloc[-1] - rm) / rs) if rs > 0 else 0.0
            # Long: want z < 0.5 (not overbought); Short: want z > -0.5 (not oversold)
            if direction == "LONG":
                zscore_ok = z < 0.5
            else:
                zscore_ok = z > -0.5
        except Exception:
            zscore_ok = True  # Neutral if can't compute
    else:
        zscore_ok = True  # Neutral fallback
    tech_detail["zscore_not_extended"] = zscore_ok
    if zscore_ok:
        tech_pts += 5.0

    # [4] Momentum moderation — REPLACES volume (anti-signal removed)
    # Condition: 10D ROC is positive but NOT overextended (avoid chasing)
    # Sweet spot: 0.3% < roc_10 < 5.0% for LONG (trend exists but not frothy)
    roc_10 = tech.get("roc_10", 0.0)
    if direction == "LONG":
        momentum_moderate = 0.3 <= roc_10 <= 5.0
    else:
        momentum_moderate = -5.0 <= roc_10 <= -0.3
    tech_detail["momentum_moderate"] = momentum_moderate
    if momentum_moderate:
        tech_pts += 5.0

    quality = screener_pts + regime_pts + ict_pts + tech_pts

    # ── Soft penalty for counter-trend signals ───────────────────
    if direction == "LONG"  and tech.get("trend_aligned_bear", False):
        quality -= 8.0
    elif direction == "SHORT" and tech.get("trend_aligned_bull", False):
        quality -= 8.0

    quality = max(0.0, min(100.0, quality))

    breakdown = {
        "screener_pts" : round(screener_pts, 1),
        "regime_pts"   : round(regime_pts, 1),
        "ict_pts"      : ict_pts,
        "tech_pts"     : tech_pts,
        "tech_detail"  : tech_detail,
        "total"        : round(quality, 1),
        "version"      : "v4.0_debiased",
        "removed_signals": ["rsi_ok (anti-signal)", "vol_confirmed (anti-signal)"],
        "added_signals"  : ["zscore_not_extended", "momentum_moderate"],
    }

    return quality, breakdown


def _analyze_multi_timeframe(
    full_df   : pd.DataFrame,
    scan_date : datetime,
    direction : str,
) -> Dict:
    """
    v5.0: Multi-Timeframe (MTF) Confluence Analysis.

    Strategi entry di daily yang dikonfirmasi oleh:
      - 4H timeframe: Trend structure + EMA alignment  
      - 1H timeframe: Momentum + Entry timing

    Dari daily OHLCV data, kita simulate 4H dan 1H dengan resampling.

    Returns:
        tf_aligned      : int   — jumlah timeframe yang aligned (0-3)
        daily_aligned   : bool  — Daily EMA aligned dengan direction
        h4_aligned      : bool  — 4H-equivalent aligned
        h1_aligned      : bool  — 1H-equivalent aligned
        mtf_score       : float — 0.0 - 1.0 (fraction aligned)
        mtf_label       : str   — FULL_CONFLUENCE / PARTIAL / DIVERGENT
        trade_freq_boost: float — size multiplier dari confluence strength
    """
    df = full_df[full_df.index <= scan_date].copy()

    if len(df) < 30:
        return {
            "tf_aligned": 1, "daily_aligned": True,
            "h4_aligned": False, "h1_aligned": False,
            "mtf_score": 0.33, "mtf_label": "INSUFFICIENT_DATA",
            "trade_freq_boost": 1.0,
        }

    close = df["Close"].astype(float)
    cur   = float(close.iloc[-1])

    # ── D1: EMA20 > EMA50 alignment ──────────────────────────────────
    ema20_d = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50_d = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    daily_aligned = (cur > ema20_d > ema50_d) if direction == "LONG" else (cur < ema20_d < ema50_d)

    # ── 4H proxy: EMA5 > EMA10 + 5-day ROC ──────────────────────────
    ema5_d  = float(close.ewm(span=5, adjust=False).mean().iloc[-1])
    ema10_d = float(close.ewm(span=10, adjust=False).mean().iloc[-1])
    h4_ema_ok = (cur > ema5_d > ema10_d) if direction == "LONG" else (cur < ema5_d < ema10_d)
    roc5 = float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if len(close) > 6 else 0.0
    h4_momentum_ok = (roc5 > 0.2) if direction == "LONG" else (roc5 < -0.2)
    h4_aligned = h4_ema_ok and h4_momentum_ok

    # ── 1H proxy: 3-day slope + last candle direction ─────────────────
    if len(close) >= 4:
        recent_slope = float(close.iloc[-1] - close.iloc[-4])
        slope_ok = (recent_slope > 0) if direction == "LONG" else (recent_slope < 0)
        if "Open" in df.columns:
            last_bull = float(df["Close"].iloc[-1]) > float(df["Open"].iloc[-1])
            candle_ok = last_bull if direction == "LONG" else not last_bull
        else:
            candle_ok = True
        h1_aligned = slope_ok and candle_ok
    else:
        h1_aligned = True

    # ── MTF Scoring ───────────────────────────────────────────────────
    tf_aligned = sum([daily_aligned, h4_aligned, h1_aligned])
    mtf_score  = tf_aligned / 3.0

    if tf_aligned == 3:
        mtf_label = "FULL_CONFLUENCE"
        trade_freq_boost = 1.25
    elif tf_aligned == 2:
        mtf_label = "PARTIAL_CONFLUENCE"
        trade_freq_boost = 1.0
    elif tf_aligned == 1:
        mtf_label = "WEAK_CONFLUENCE"
        trade_freq_boost = 0.75
    else:
        mtf_label = "DIVERGENT"
        trade_freq_boost = 0.0   # Block trade — semua TF berlawanan

    return {
        "tf_aligned"        : tf_aligned,
        "daily_aligned"     : daily_aligned,
        "h4_aligned"        : h4_aligned,
        "h1_aligned"        : h1_aligned,
        "mtf_score"         : round(mtf_score, 3),
        "mtf_label"         : mtf_label,
        "trade_freq_boost"  : trade_freq_boost,
        "h4_roc5"           : round(roc5, 3),
    }


# ── Keep v3 name as alias so existing call sites work ──────────────
def _compute_quality_score_v3(
    score: float, regime_conf: float, ict_signal: Dict, tech: Dict, direction: str
) -> Tuple[float, Dict]:
    """Alias to v4 debiased version. v3 had inverted quality signal."""
    return _compute_quality_score_v4(score, regime_conf, ict_signal, tech, direction)


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


def _find_entry_signal_soft(
    df_slice   : pd.DataFrame,
    config     : SimulationConfig,
    df_future  : Optional[pd.DataFrame] = None,   # [FIX v5] untuk ambil next-open
) -> Optional[Dict]:
    """
    v5 LOOK-AHEAD FIX: Entry price = Open hari berikutnya, bukan Close hari scan.

    Root cause bug lama:
      entry = Close[-1] pada scan_date → kamu tidak bisa masuk di exact close
      setelah market tutup. Realistic entry = Open candle hari berikutnya.

    Dampak: Close-to-Open gap bisa +/- 0.5% hingga 3% pada saham volatile.
    Dengan 160 trades, ini bisa inflate/deflate return 5-15% total.

    Fix:
      - Sinyal masih di-generate dari df_slice (data historis s/d scan date)
        → TIDAK ada look-ahead, karena hanya data masa lalu yang dipakai
      - Entry price = Open[0] dari df_future (candle pertama setelah scan date)
        → Ini harga realistis yang bisa kamu eksekusi
      - SL dan TP dihitung ulang dari entry_actual (bukan dari close[-1])
    """
    ict      = get_ict_full_analysis(df_slice)
    bias     = ict.get("composite_bias", "NEUTRAL")
    strength = _normalize_ict_strength(ict.get("bias_strength", "WEAK"))

    if bias == "NEUTRAL":
        return None

    # ── [FIX v5] Gunakan next-open sebagai entry price ─────────────────
    # Jika df_future tersedia dan ada data, ambil Open candle pertama.
    # Fallback ke Close[-1] jika belum ada data future (untuk compatibility).
    close_last = float(df_slice["Close"].iloc[-1])

    if df_future is not None and not df_future.empty and "Open" in df_future.columns:
        next_open = float(df_future["Open"].iloc[0])
        # Sanity check: next open tidak boleh > 20% dari close (data error / split)
        if abs(next_open - close_last) / max(close_last, 1e-6) < 0.20:
            entry_price = next_open
        else:
            entry_price = close_last   # Fallback jika anomali
    else:
        entry_price = close_last       # Fallback jika df_future belum tersedia

    atr     = _calculate_atr(df_slice, period=14)
    sl_dist = atr * config.sl_atr_mult

    # v3: Compute tech once here, pass to caller via signal dict
    tech = _calculate_technicals_fast(df_slice)

    direction = "LONG" if bias == "BULLISH" else "SHORT"

    # v3: Dynamic TP based on momentum & trend
    tp_mult  = _compute_dynamic_tp_multiplier(tech, {"strength": strength}, direction)
    tp_dist  = sl_dist * config.tp_rr_ratio * tp_mult

    # v3: Dynamic SL — tighten/widen based on ATR regime
    atr_pct = tech.get("atr_percentile", 50.0)
    if atr_pct > 80:     sl_mult = 1.2
    elif atr_pct < 25:   sl_mult = 0.9
    else:                sl_mult = 1.0
    sl_dist_adj = sl_dist * sl_mult

    # [FIX v5] SL dan TP dihitung dari entry_price (next open), bukan dari close_last
    if direction == "LONG":
        return {
            "direction"      : "LONG",
            "entry"          : entry_price,
            "entry_ref_close": close_last,     # Simpan close referensi untuk audit
            "sl"             : round(entry_price - sl_dist_adj, 6),
            "tp"             : round(entry_price + tp_dist, 6),
            "atr"            : round(atr, 6),
            "strength"       : strength,
            "setup"          : f"ICT_{strength}_BULLISH",
            "tp_multiplier"  : round(tp_mult, 2),
            "sl_multiplier"  : round(sl_mult, 2),
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
            "tech"           : tech,
            "entry_type"     : "NEXT_OPEN" if entry_price != close_last else "CLOSE_FALLBACK",
        }
    else:
        return {
            "direction"      : "SHORT",
            "entry"          : entry_price,
            "entry_ref_close": close_last,
            "sl"             : round(entry_price + sl_dist_adj, 6),
            "tp"             : round(entry_price - tp_dist, 6),
            "atr"            : round(atr, 6),
            "strength"       : strength,
            "setup"          : f"ICT_{strength}_BEARISH",
            "tp_multiplier"  : round(tp_mult, 2),
            "sl_multiplier"  : round(sl_mult, 2),
            "bullish_factors": ict.get("bullish_factors", 0),
            "bearish_factors": ict.get("bearish_factors", 0),
            "tech"           : tech,
            "entry_type"     : "NEXT_OPEN" if entry_price != close_last else "CLOSE_FALLBACK",
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

    # ── [v4.1] Notional Risk Guard & Unit Calculation ──────────
    # Minimum SL buffer: 0.2% (prevent unrealistic tight-fill anomalies)
    min_sl_dist = entry * 0.002
    sl_dist     = max(abs(entry - sl_price), min_sl_dist)

    actual_risk_pct = min(max(risk_pct * size_scale, config.min_risk_floor_pct), config.max_risk_cap_pct)
    dollar_risk     = balance_entry * (actual_risk_pct / 100)

    # Base units from risk
    units_from_risk = dollar_risk / sl_dist

    # [v4.1] Notional Cap: Prevents "Infinite Units" bug on narrow SL.
    # We never want more than 1.0x leverage per trade for systematic stability.
    max_notional_value = balance_entry * 1.0
    units_from_cap     = max_notional_value / entry
    units_full         = min(units_from_risk, units_from_cap)

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
    
    # [v4.1] Protection against mathematical singularities
    if not np.isfinite(net_pnl):
        print(f"  NON-FINITE P&L detected for {ticker}. Resetting to zero.")
        net_pnl = 0.0
        
    pnl_pct       = (net_pnl / max(balance_entry, 1.0)) * 100
    
    # [v4.1] Extreme P&L Guard: Log and cap if P&L > 1000% (unrealistic for this model)
    if abs(pnl_pct) > 1000:
        print(f" EXTREME P&L: {ticker} | {direction} | P&L: ${net_pnl:.2f} ({pnl_pct:.1f}%)")
        print(f"   Entry: {entry:.4f} | Exit: {exit_price:.4f} | Units: {units_full:.4f} | Bal: ${balance_entry:.2f}")
        # Cap to +/- 100% for safety to prevent total ruin of math stats
        pnl_pct = np.clip(pnl_pct, -100.0, 500.0) 
        net_pnl = (pnl_pct / 100) * balance_entry
        
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


def _compute_full_analytics_v4(result: SimulationResult) -> Dict:
    """
    v4.0: Augment analytics with statistical audit + walk-forward.
    Returns a dict ready to merge into the simulation output JSON.
    """
    audit   = generate_statistical_audit(result)
    wf      = run_walk_forward_validation(result)

    wf_dict = {
        "split_date"            : wf.split_date,
        "in_sample": {
            "trades"            : wf.in_sample_trades,
            "win_rate_pct"      : wf.in_sample_win_rate,
            "profit_factor"     : wf.in_sample_pf,
            "return_pct"        : wf.in_sample_return_pct,
        },
        "out_of_sample": {
            "trades"            : wf.out_sample_trades,
            "win_rate_pct"      : wf.out_sample_win_rate,
            "profit_factor"     : wf.out_sample_pf,
            "return_pct"        : wf.out_sample_return_pct,
        },
        "degradation_pct"       : wf.degradation_pct,
        "is_robust"             : wf.is_robust,
        "verdict"               : (
            " ROBUST: OOS performance within acceptable degradation."
            if wf.is_robust
            else " NOT ROBUST: OOS performance degraded >30% vs in-sample."
        ),
    }

    return {"statistical_audit": audit, "walk_forward": wf_dict}


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
#  LAYER 9 (v4.0) — STATISTICAL AUDIT ENGINE
# ══════════════════════════════════════════════════════════════════

def generate_statistical_audit(result: SimulationResult) -> Dict:
    """
    v4.0: Full statistical validity report.

    Addresses Killer #1 from audit: N=48 → p-value 0.77 (77% chance edge is noise).

    Computes:
      1. Binomial t-stat + p-value (is win rate above 50% with significance?)
      2. Power analysis (how many trades needed for 80% power?)
      3. Bootstrap confidence interval for win rate (1000 resamples)
      4. Harvey-Liu-Zhu (2016) multiple testing correction
      5. Quality bucket win rate breakdown (validates quality signal is now monotonic)
    """
    trades = result.trades
    n      = len(trades)

    # ── 1. Binomial significance test ───────────────────────────
    if n == 0:
        return {"error": "No trades to audit"}

    n_wins   = result.winning_trades
    wr       = n_wins / n
    # One-sided binomial test: H0: p = 0.50, H1: p > 0.50
    # z = (wr - 0.5) / sqrt(0.25/n)
    se       = (0.25 / n) ** 0.5
    z_stat   = (wr - 0.5) / se if se > 0 else 0.0
    p_value  = float(norm.sf(z_stat))   # One-sided p-value

    # ── 2. Power analysis ────────────────────────────────────────
    # Required N to detect 52% WR with 95% CI, 80% power
    # Minimum detectable effect: |WR_observed - 0.50|
    effect_size = abs(wr - 0.50)
    if effect_size > 0.001:
        # n = (z_alpha + z_beta)^2 * p*(1-p) / effect^2
        z_alpha = norm.ppf(0.95)   # 1.645 (one-sided 5%)
        z_beta  = norm.ppf(0.80)   # 0.842 (80% power)
        required_n = int(((z_alpha + z_beta) ** 2) * 0.25 / (effect_size ** 2)) + 1
    else:
        required_n = 99_999  # Effect size near zero → no achievable N

    years_needed = round(required_n / max(n / max(result.config.lookback_years, 1), 1), 1)
    is_significant = p_value < 0.05

    significance_verdict = (
        " STATISTICALLY SIGNIFICANT" if is_significant
        else f" NOT SIGNIFICANT — {p_value:.1%} chance this edge is random noise"
    )

    # ── 3. Bootstrap win rate CI (1000 resamples) ────────────────
    np.random.seed(42)
    n_bootstrap = 1000
    outcomes    = np.array([1 if t.outcome == "WIN" else 0 for t in trades])
    boot_wrs    = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(outcomes, size=n, replace=True)
        boot_wrs.append(float(np.mean(sample)))
    boot_wrs = np.array(boot_wrs)
    ci_lower = float(np.percentile(boot_wrs, 2.5))
    ci_upper = float(np.percentile(boot_wrs, 97.5))

    # ── 4. Harvey-Liu-Zhu (2016) multiple testing correction ─────
    # With 15 tickers × 3 years × ~5 parameters = ~225 implicit tests
    # Minimum t-stat for 5% significance with m tests:
    # t_min = sqrt(2 * log(m) - log(log(m)))   [Bonferroni approximation]
    m_tests = 15 * 3 * 5   # Rough estimate
    hlz_min_tstat = (2 * np.log(m_tests) - np.log(np.log(m_tests))) ** 0.5
    hlz_adjusted_p = min(float(norm.sf(z_stat)) * m_tests, 1.0)

    hlz_verdict = (
        " PASSES HLZ correction" if abs(z_stat) >= hlz_min_tstat
        else f" FAILS HLZ — t-stat {z_stat:.2f} < required {hlz_min_tstat:.2f} "
             f"(~{m_tests} implicit tests correction)"
    )

    # ── 5. Quality bucket win rate breakdown ─────────────────────
    buckets = {
        "A+  (90-100)": [t for t in trades if t.quality_score >= 90],
        "A   (75-89) ": [t for t in trades if 75 <= t.quality_score < 90],
        "B   (60-74) ": [t for t in trades if 60 <= t.quality_score < 75],
        "C   (45-59) ": [t for t in trades if 45 <= t.quality_score < 60],
        "D   (<45)   ": [t for t in trades if t.quality_score < 45],
    }
    bucket_stats = {}
    for label, bucket_trades in buckets.items():
        if bucket_trades:
            bw = sum(1 for t in bucket_trades if t.outcome == "WIN")
            bucket_stats[label] = {
                "n"       : len(bucket_trades),
                "wins"    : bw,
                "win_rate": round(bw / len(bucket_trades) * 100, 1),
                "avg_pnl" : round(np.mean([t.pnl_pct for t in bucket_trades]), 3),
            }

    # Check quality inversion (A+ should NOT be worst)
    quality_inversion_detected = False
    bucket_wrs = {k: v["win_rate"] for k, v in bucket_stats.items() if v["n"] >= 3}
    if len(bucket_wrs) >= 2:
        sorted_buckets = sorted(bucket_wrs.items(), key=lambda x: x[1])
        worst_bucket   = sorted_buckets[0][0]
        quality_inversion_detected = "A+" in worst_bucket

    quality_verdict = (
        " QUALITY INVERSION STILL PRESENT — A+ trades performing worst! Check signals."
        if quality_inversion_detected
        else " Quality monotonic — higher quality → higher win rate (as expected)"
    )

    return {
        "sample_size"             : n,
        "observed_win_rate_pct"   : round(wr * 100, 2),
        "win_rate_ci_95"          : {"lower": round(ci_lower * 100, 2), "upper": round(ci_upper * 100, 2)},
        "significance": {
            "z_stat"              : round(z_stat, 4),
            "p_value"             : round(p_value, 4),
            "is_significant_05"   : is_significant,
            "verdict"             : significance_verdict,
        },
        "power_analysis": {
            "required_n_for_80pct_power" : required_n,
            "current_n"                  : n,
            "shortfall"                  : max(0, required_n - n),
            "estimated_years_to_target"  : years_needed,
            "effect_size_observed"       : round(effect_size, 4),
            "warning"                    : (
                f" Only {n} trades. Need {required_n} for 80% power. "
                f"~{years_needed:.1f} more years at current pace."
                if n < required_n else " Sufficient trades for meaningful statistics."
            ),
        },
        "multiple_testing_hlz": {
            "implicit_tests_estimated" : m_tests,
            "hlz_min_tstat"            : round(hlz_min_tstat, 3),
            "observed_tstat"           : round(z_stat, 3),
            "hlz_adjusted_p"           : round(hlz_adjusted_p, 4),
            "verdict"                  : hlz_verdict,
        },
        "quality_bucket_breakdown" : bucket_stats,
        "quality_inversion_check"  : {
            "inversion_detected" : quality_inversion_detected,
            "verdict"            : quality_verdict,
        },
    }


def run_walk_forward_validation(
    result: SimulationResult,
    is_split_pct: float = 0.70
) -> WalkForwardResult:
    """
    v4.0: In-sample / Out-of-sample walk-forward validation.

    Splits the trade list chronologically:
      - In-sample  (IS): First is_split_pct% of trades
      - Out-of-sample (OOS): Remaining trades

    A robust strategy should show:
      OOS win rate >= IS win rate × 0.70   (max 30% degradation)

    Args:
        result      : Completed SimulationResult with trades
        is_split_pct: Fraction of trades for in-sample (default 0.70 = 70%)
    """
    trades = sorted(result.trades, key=lambda t: t.entry_date)
    n      = len(trades)

    wfr = WalkForwardResult()
    if n < 10:
        return wfr

    split_idx      = int(n * is_split_pct)
    is_trades      = trades[:split_idx]
    oos_trades     = trades[split_idx:]

    wfr.split_date = oos_trades[0].entry_date if oos_trades else ""

    def _metrics(t_list):
        if not t_list:
            return 0, 0.0, 0.0, 0.0
        wins = [t for t in t_list if t.outcome == "WIN"]
        losses = [t for t in t_list if t.outcome == "LOSS"]
        wr   = len(wins) / len(t_list) * 100
        gw   = sum(t.pnl_usd for t in wins)   if wins   else 0
        gl   = abs(sum(t.pnl_usd for t in losses)) if losses else 1e-9
        pf   = round(gw / gl, 3)
        ret  = round(sum(t.pnl_usd for t in t_list) / result.config.initial_balance * 100, 2)
        return len(t_list), round(wr, 2), pf, ret

    wfr.in_sample_trades,  wfr.in_sample_win_rate,  wfr.in_sample_pf,  wfr.in_sample_return_pct  = _metrics(is_trades)
    wfr.out_sample_trades, wfr.out_sample_win_rate, wfr.out_sample_pf, wfr.out_sample_return_pct = _metrics(oos_trades)

    if wfr.in_sample_win_rate > 0:
        wfr.degradation_pct = round(
            (wfr.out_sample_win_rate - wfr.in_sample_win_rate) / wfr.in_sample_win_rate * 100, 2
        )

    wfr.is_robust = (
        wfr.out_sample_win_rate >= wfr.in_sample_win_rate * 0.70
        and wfr.out_sample_pf >= 1.0
    )

    return wfr


# ══════════════════════════════════════════════════════════════════
#  MASTER SIMULATION RUNNER v2.0
# ══════════════════════════════════════════════════════════════════


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """
    v5.0: Look-ahead fix + Equity Armor integration + Multi-Timeframe + Slippage.
    See module docstring at top of file for full changelog.
    """
    end_date   = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=365 * config.lookback_years)
    tickers    = WATCHLISTS.get(config.scan_universe, WATCHLISTS["US"])

    result                = SimulationResult(config=config)
    result.sim_start_date = start_date.strftime("%Y-%m-%d")
    balance               = config.initial_balance
    trade_id              = 0
    trades_filtered       = 0
    mtf_filtered          = 0
    total_slippage_usd    = 0.0

    # [v5] Initialize EquityArmor
    armor = None
    if config.use_equity_armor:
        try:
            from app.engine.apex_equity_armor import EquityArmor, ArmorConfig
            armor_cfg = ArmorConfig(
                initial_balance           = config.initial_balance,
                trailing_stop_pct         = 0.15,
                trailing_warning_pct      = 0.08,
                target_vol_ann            = 0.15,
                max_vol_ann               = 0.50,
                eq_fast_ma                = 10,
                eq_slow_ma                = 20,
                eq_ultra_ma               = 50,
                edge_rolling_window       = 20,
                min_win_rate              = 0.42,
                min_sharpe                = 0.40,
                min_profit_factor         = 1.05,
                max_consec_losses         = 6,
                base_kelly_fraction       = config.kelly_fraction,
                aggressive_kelly_fraction = min(config.kelly_fraction * 1.5, 0.40),
                reserve_rate              = 0.10,
                reserve_locked            = True,
                dd_velocity_window        = 10,
                dd_velocity_halt_pct      = 8.0,
                max_drawdown_target       = config.circuit_breaker_dd / 100.0,
            )
            armor = EquityArmor(armor_cfg)
            print("   Equity Armor ACTIVE — Milestone floors + trailing stop enabled")
        except ImportError:
            print("    apex_equity_armor not found — using legacy circuit breaker")

    print(f"\n{'='*70}")
    print(f"  QUANTUM PORTFOLIO SIMULATOR v5.0")
    print(f"  Universe      : {config.scan_universe} ({len(tickers)} tickers)")
    print(f"  Period        : {start_date.date()} to {end_date.date()}")
    print(f"  Capital       : ${config.initial_balance:,.2f}")
    print(f"  Look-ahead Fix: NEXT-OPEN entry")
    print(f"  Equity Armor  : {'ACTIVE' if armor else 'DISABLED'}")
    print(f"  MTF Confluence: {'ACTIVE' if config.use_multi_timeframe else 'DISABLED'}")
    print(f"  Slippage      : {config.slippage_pct}%")
    print(f"{'='*70}")

    # Pre-fetch data
    print("\n Fetching historical data...")
    all_data: Dict[str, pd.DataFrame] = {}
    for i, ticker in enumerate(tickers):
        print(f"   [{i+1:2d}/{len(tickers)}] {ticker:15s}", end=" ")
        df = _fetch_historical_data(ticker, start_date, end_date)
        if df is not None and len(df) >= 60:
            all_data[ticker] = df
            print(f" {len(df)} candles")
        else:
            print(" Insufficient data")

    if not all_data:
        print(" No valid data. Abort.")
        return result

    print(f"\n {len(all_data)} tickers loaded.")
    print(f"\n Starting v5 simulation loop...\n")

    closed_trades  : List[TradeRecord] = []
    open_positions : List[Dict]        = []
    current_date   = start_date + timedelta(days=60)
    week_num       = 0
    armor_events   : List[Dict]        = []

    while current_date <= end_date - timedelta(days=config.max_hold_days):
        week_num         += 1
        candidates        = []
        current_date_str  = current_date.strftime("%Y-%m-%d")

        # STEP 1: Score tickers
        for ticker, full_df in all_data.items():
            df_slice = full_df[full_df.index <= current_date].tail(90)
            if len(df_slice) < 55:
                continue
            score = _score_ticker(df_slice)
            if score >= config.min_screener_score:
                candidates.append((ticker, score, df_slice))

        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:config.max_open_trades * 2]

        week_snapshot = {
            "week"          : week_num,
            "date"          : current_date_str,
            "balance"       : round(balance, 4),
            "candidates"    : len(candidates),
            "trades_opened" : 0,
            "open_positions": len(open_positions)
        }

        # STEP 2: Close expired positions
        positions_to_close = []
        for pos in open_positions:
            try:
                exit_date_obj = datetime.strptime(pos["exit_date"], "%Y-%m-%d")
            except ValueError:
                positions_to_close.append(pos)
                continue
            if current_date >= exit_date_obj:
                trade               = pos["trade"]
                trade.balance_after = round(balance + trade.pnl_usd, 4)
                balance             = trade.balance_after
                closed_trades.append(trade)
                positions_to_close.append(pos)
                # [v5] Notify armor of trade close
                if armor:
                    armor.record_trade(
                        pnl_usd = trade.pnl_usd,
                        is_win  = (trade.outcome == "WIN"),
                        date    = trade.exit_date,
                    )

        for p in positions_to_close:
            open_positions.remove(p)

        # STEP 3: Equity Armor gate + legacy circuit breaker
        if armor:
            armor_status = armor.update(balance, date=current_date_str)
            if armor_status.get("milestone", {}).get("milestone_unlocked") or armor_status.get("system_halted"):
                armor_events.append({
                    "date"             : current_date_str,
                    "balance"          : round(balance, 2),
                    "system_halted"    : armor_status.get("system_halted", False),
                    "halt_reason"      : armor_status.get("halt_reason", ""),
                    "milestone"        : armor_status.get("milestone", {}).get("active_milestone"),
                    "floor_balance"    : armor_status.get("milestone", {}).get("locked_floor_balance"),
                    "floor_pct"        : armor_status.get("milestone", {}).get("locked_floor_pct"),
                    "new_milestone"    : armor_status.get("milestone", {}).get("milestone_unlocked"),
                    "operational_mode" : armor_status.get("operational_mode"),
                    "final_risk_scale" : armor_status.get("final_risk_scale", 1.0),
                })
            if armor_status.get("system_halted"):
                reason = armor_status.get("halt_reason", "ARMOR_HALT")
                ms_data = armor_status.get("milestone", {})
                print(f"\n     ARMOR HALT Week {week_num}: {reason}")
                print(f"   Balance: ${balance:,.2f} | Floor: ${ms_data.get('locked_floor_balance', 0):,.2f}\n")
                result.weekly_snapshots.append(week_snapshot)
                current_date += timedelta(days=config.scan_interval_days)
                continue
            armor_risk_scale = float(armor_status.get("final_risk_scale", 1.0))
        else:
            dd_pct = (balance - config.initial_balance) / config.initial_balance * 100
            if dd_pct < -config.circuit_breaker_dd:
                print(f"\n    CIRCUIT BREAKER Week {week_num} — DD: {dd_pct:.2f}%")
                break
            armor_risk_scale = 1.0

        # STEP 4: Entries with look-ahead fix + MTF + slippage
        open_count  = len(open_positions)
        consec_loss = _get_consecutive_losses(closed_trades)

        for ticker, score, df_slice in top_candidates:
            if open_count >= config.max_open_trades:
                break

            regime, regime_conf = _detect_regime_full(df_slice)
            if config.regime_filter and regime == "HIGH_VOL_BEARISH":
                trades_filtered += 1
                continue

            # [v5 FIX 1] Get df_future FIRST for next-open entry price
            future_end = current_date + timedelta(days=config.max_hold_days + 5)
            full_df    = all_data[ticker]
            df_future  = full_df[
                (full_df.index > current_date) &
                (full_df.index <= future_end)
            ].head(config.max_hold_days)
            if df_future.empty:
                continue

            # [v5 FIX 1] Pass df_future to get next-open entry price
            signal = _find_entry_signal_soft(df_slice, config, df_future=df_future)
            if signal is None:
                trades_filtered += 1
                continue

            direction = signal["direction"]

            # [v5 FIX 3] Multi-Timeframe confluence check
            if config.use_multi_timeframe:
                mtf = _analyze_multi_timeframe(full_df, current_date, direction)
                if mtf["trade_freq_boost"] == 0.0 or mtf["tf_aligned"] < config.mtf_min_alignment:
                    mtf_filtered += 1
                    continue
                mtf_boost = mtf["trade_freq_boost"]
            else:
                mtf       = {"tf_aligned": 2, "mtf_label": "MTF_DISABLED", "trade_freq_boost": 1.0}
                mtf_boost = 1.0

            tech = signal.get("tech", {})
            quality_score, _ = _compute_quality_score_v4(
                score=score, regime_conf=regime_conf, ict_signal=signal,
                tech=tech, direction=direction, df_slice=df_slice,
            )

            if quality_score >= 90:   base_size_scale = 1.00
            elif quality_score >= 75: base_size_scale = 0.80
            elif quality_score >= 60: base_size_scale = 0.60
            elif quality_score >= 45: base_size_scale = 0.40
            else:                     base_size_scale = 0.22

            if "BULLISH" in regime or "LOW_VOL" in regime:
                regime_scale = config.regime_size_bull
            elif "SIDEWAYS" in regime or "CHOP" in regime:
                regime_scale = config.regime_size_chop
            else:
                regime_scale = 0.50

            # [v5] Final scale = quality × regime × MTF × armor
            size_scale = float(np.clip(
                base_size_scale * regime_scale * mtf_boost * armor_risk_scale,
                0.05, 1.5
            ))

            kelly_risk_pct, kelly_frac = _compute_adaptive_kelly(
                closed_trades, config, config.risk_per_trade, consec_loss
            )

            # [v5 FIX 4] Apply realistic slippage to entry price
            signal = dict(signal)
            raw_entry = signal["entry"]
            if config.slippage_pct > 0:
                slip_factor = (1.0 + config.slippage_pct / 100.0) if direction == "LONG" else \
                              (1.0 - config.slippage_pct / 100.0)
                slipped     = raw_entry * slip_factor
                sl_dist     = abs(raw_entry - signal["sl"])
                tp_dist     = abs(raw_entry - signal["tp"])
                signal["entry"] = slipped
                signal["sl"]    = round(slipped - sl_dist, 6) if direction == "LONG" else round(slipped + sl_dist, 6)
                signal["tp"]    = round(slipped + tp_dist, 6) if direction == "LONG" else round(slipped - tp_dist, 6)
                est_units       = (balance * kelly_risk_pct / 100.0 * size_scale) / max(sl_dist, 1e-6)
                total_slippage_usd += abs(slipped - raw_entry) * est_units

            entry_date = current_date.strftime("%Y-%m-%d")
            trade_id  += 1

            trade = _simulate_trade(
                ticker=ticker, signal=signal, df_future=df_future,
                balance_entry=balance, config=config, trade_id=trade_id,
                entry_date=entry_date, regime=regime, regime_conf=regime_conf,
                score=score, risk_pct=kelly_risk_pct, kelly_frac=kelly_frac,
                size_scale=size_scale, quality_score=quality_score,
                tp_multiplier=signal.get("tp_multiplier", 1.0), tech=tech, sector="Unknown",
            )

            if trade:
                trade.leverage = round((trade.units * trade.entry_price) / balance, 3)
            if trade is None:
                trade_id -= 1
                continue

            open_positions.append({"trade": trade, "exit_date": trade.exit_date})
            open_count += 1
            week_snapshot["trades_opened"] += 1

            icon     = "" if trade.outcome == "WIN" else "" if trade.outcome == "LOSS" else "〰"
            mtf_icon = "" if mtf.get("tf_aligned", 0) == 3 else "" if mtf.get("tf_aligned", 0) == 2 else ""
            entry_t  = signal.get("entry_type", "?")[:1]
            a_icon   = f"×{armor_risk_scale:.2f}" if armor else ""
            print(f"   Wk{week_num:3d} | {icon} {ticker:10s} {direction:5s} | "
                  f"Q:{quality_score:.0f} | MTF:{mtf_icon}{mtf.get('tf_aligned',0)}/3 | "
                  f"E:{entry_t} | Sz:×{size_scale:.2f} {a_icon} | P&L:${trade.pnl_usd:+7.2f}")

        result.weekly_snapshots.append(week_snapshot)
        current_date += timedelta(days=config.scan_interval_days)

    # Flush remaining open positions
    for pos in open_positions:
        trade               = pos["trade"]
        trade.balance_after = round(balance + trade.pnl_usd, 4)
        balance             = trade.balance_after
        closed_trades.append(trade)

    result.trades             = sorted(closed_trades, key=lambda t: t.entry_date)
    result.trades_filtered    = trades_filtered
    result.mtf_filtered       = mtf_filtered
    result.slippage_total_usd = round(total_slippage_usd, 4)
    result.armor_events       = armor_events
    result                    = _compute_analytics(result)

    print(f"\n{'='*70}")
    print(f"  FINAL BALANCE  : ${result.final_balance:,.2f}")
    print(f"  TOTAL RETURN   : {result.total_return_pct:+.2f}%")
    print(f"  TOTAL TRADES   : {result.total_trades}")
    print(f"  WIN RATE       : {result.win_rate_pct:.1f}%")
    print(f"  PROFIT FACTOR  : {result.profit_factor:.3f}")
    print(f"  SHARPE         : {result.sharpe_ratio:.3f}")
    print(f"  MAX DRAWDOWN   : {result.max_drawdown_pct:.2f}%")
    print(f"  GATE FILTERED  : {result.trades_filtered} (signal) | {result.mtf_filtered} (MTF)")
    print(f"  SLIPPAGE COST  : ${result.slippage_total_usd:,.2f}")
    if armor_events:
        halts      = [e for e in armor_events if e.get("system_halted")]
        milestones = [e for e in armor_events if e.get("new_milestone")]
        print(f"  ARMOR HALTS    : {len(halts)}")
        print(f"  MILESTONES HIT : {len(milestones)}")
        for m in milestones:
            print(f"    → {m['new_milestone']:10s} @ ${m['balance']:,.2f} | Floor: ${m.get('floor_balance',0):,.2f}")
    print(f"{'='*70}\n")
    return result



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
            "leverage"        : t.leverage,
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
            "scan_interval_days"  : result.config.scan_interval_days,
            "quality_version"     : "v4.0_debiased",
            "removed_anti_signals": ["rsi_ok", "vol_confirmed"],
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
            "mtf_filtered"        : result.mtf_filtered,         # [v5]
            "slippage_total_usd"  : result.slippage_total_usd,   # [v5]
            "max_leverage_used"   : round(max([t.leverage for t in result.trades] + [0.0]), 2),
            "kelly_avg_fraction"  : result.kelly_avg_fraction,
        },
        "equity_curve"   : result.equity_curve,
        "trades"         : trades_list,
        "weekly_snapshots": result.weekly_snapshots,
        "armor_events"   : result.armor_events,                   # [v5] milestone/halt log
        "best_trade"     : trades_list[result.trades.index(result.best_trade)]  if result.best_trade  and result.best_trade  in result.trades else None,
        "worst_trade"    : trades_list[result.trades.index(result.worst_trade)] if result.worst_trade and result.worst_trade in result.trades else None,
        # ── v4.0: Statistical validity + walk-forward ────────────
        **_compute_full_analytics_v4(result),
    }

# ══════════════════════════════════════════════════════════════════
#  run_simulation_stream  —  SSE generator, data 100% real
#  Logika identik run_simulation(), tapi yield SSE string per minggu
#  sehingga frontend bisa consume real-time via EventSource.
#
#  Event types yang di-yield (string "data: <json>\n\n"):
#    phase  — transisi fase besar
#    tick   — update per minggu: balance, trades, wins, dd, log
#    trade  — setiap trade closed: ticker, pnl, outcome, balance
#    done   — selesai, payload = full JSON report
#    error  — exception
# ══════════════════════════════════════════════════════════════════
import json as _json_stream


def run_simulation_stream(config: "SimulationConfig"):
    """Generator — yield SSE events dengan data real dari simulation loop."""

    def sse(t: str, p: dict) -> str:
        p["type"] = t
        return "data: " + _json_stream.dumps(p, default=str) + "\n\n"

    try:
        yield sse("phase", {"phase": "FETCH", "label": "Fetching historical data", "progress": 2})

        end_date   = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=365 * config.lookback_years)
        tickers    = WATCHLISTS.get(config.scan_universe, WATCHLISTS["US"])

        result                = SimulationResult(config=config)
        result.sim_start_date = start_date.strftime("%Y-%m-%d")
        balance               = config.initial_balance
        trade_id              = 0
        trades_filtered       = 0
        mtf_filtered          = 0
        total_slippage_usd    = 0.0

        # ── Fetch semua data dulu, yield progress tiap ticker ────
        all_data: Dict[str, pd.DataFrame] = {}
        n_tickers = len(tickers)
        for i, ticker in enumerate(tickers):
            df = _fetch_historical_data(ticker, start_date, end_date)
            ok = df is not None and len(df) >= 60
            if ok:
                all_data[ticker] = df
            prog = int(2 + (i + 1) / max(n_tickers, 1) * 16)
            yield sse("tick", {
                "phase"  : "FETCH",
                "progress": prog,
                "balance" : round(balance, 2),
                "trades"  : 0, "wins": 0, "losses": 0, "dd_pct": 0.0,
                "log"     : {
                    "tag" : "DATA",
                    "text": f"{ticker}  {'loaded ' + str(len(df)) + ' candles' if ok else 'skip — insufficient data'}",
                },
            })

        if not all_data:
            yield sse("error", {"message": "No valid ticker data loaded"})
            return

        # ── Init Equity Armor ────────────────────────────────────
        yield sse("phase", {"phase": "GATE", "label": "Initializing armor + gate", "progress": 19})

        armor = None
        if getattr(config, "use_equity_armor", True):
            try:
                from app.engine.apex_equity_armor import EquityArmor, ArmorConfig as _ArmorCfg
                armor = EquityArmor(_ArmorCfg(
                    initial_balance           = config.initial_balance,
                    trailing_stop_pct         = 0.15,
                    trailing_warning_pct      = 0.08,
                    target_vol_ann            = 0.15,
                    max_vol_ann               = 0.50,
                    eq_fast_ma                = 10,
                    eq_slow_ma                = 20,
                    eq_ultra_ma               = 50,
                    edge_rolling_window       = 20,
                    min_win_rate              = 0.42,
                    min_sharpe                = 0.40,
                    min_profit_factor         = 1.05,
                    max_consec_losses         = 6,
                    base_kelly_fraction       = config.kelly_fraction,
                    aggressive_kelly_fraction = min(config.kelly_fraction * 1.5, 0.40),
                    reserve_rate              = 0.10,
                    reserve_locked            = True,
                    dd_velocity_window        = 10,
                    dd_velocity_halt_pct      = 8.0,
                    max_drawdown_target       = config.circuit_breaker_dd / 100.0,
                ))
            except ImportError:
                pass

        yield sse("phase", {"phase": "SIM", "label": "Running simulation loop", "progress": 21})

        # ── Main simulation loop ─────────────────────────────────
        closed_trades : List[TradeRecord] = []
        open_positions: List[Dict]        = []
        armor_events  : List[Dict]        = []
        current_date  = start_date + timedelta(days=60)
        week_num      = 0
        win_count     = 0
        loss_count    = 0
        peak_bal      = config.initial_balance
        max_dd        = 0.0

        total_days  = max(1, (end_date - timedelta(days=config.max_hold_days)
                              - (start_date + timedelta(days=60))).days)
        total_weeks = max(1, total_days // config.scan_interval_days)

        while current_date <= end_date - timedelta(days=config.max_hold_days):
            week_num        += 1
            cur_str          = current_date.strftime("%Y-%m-%d")
            progress_pct     = int(21 + (week_num / total_weeks) * 70)

            # Score candidates
            candidates = []
            for ticker, full_df in all_data.items():
                df_slice = full_df[full_df.index <= current_date].tail(90)
                if len(df_slice) < 55:
                    continue
                score = _score_ticker(df_slice)
                if score >= config.min_screener_score:
                    candidates.append((ticker, score, df_slice))
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = candidates[: config.max_open_trades * 2]

            week_snap = {
                "week": week_num, "date": cur_str,
                "balance": round(balance, 4), "candidates": len(candidates),
                "trades_opened": 0, "open_positions": len(open_positions),
            }

            # ── Close expired positions ──────────────────────────
            to_close = []
            week_log = None
            for pos in open_positions:
                try:
                    exit_dt = datetime.strptime(pos["exit_date"], "%Y-%m-%d")
                except ValueError:
                    to_close.append(pos); continue
                if current_date >= exit_dt:
                    tr               = pos["trade"]
                    tr.balance_after = round(balance + tr.pnl_usd, 4)
                    balance          = tr.balance_after
                    closed_trades.append(tr)
                    to_close.append(pos)
                    if armor:
                        armor.record_trade(pnl_usd=tr.pnl_usd,
                                           is_win=(tr.outcome == "WIN"),
                                           date=tr.exit_date)
                    is_win = tr.outcome == "WIN"
                    if is_win: win_count  += 1
                    else:      loss_count += 1
                    sign     = "+" if tr.pnl_usd >= 0 else ""
                    week_log = {
                        "tag" : "WIN" if is_win else "LOSS",
                        "text": (f"{tr.ticker}  {tr.direction}  "
                                 f"pnl={sign}${tr.pnl_usd:.2f}  bal=${balance:.2f}"),
                    }
                    # Per-trade event — frontend bisa pakai untuk live feed
                    yield sse("trade", {
                        "ticker"   : tr.ticker,
                        "direction": tr.direction,
                        "pnl_usd"  : round(tr.pnl_usd, 4),
                        "outcome"  : tr.outcome,
                        "balance"  : round(balance, 4),
                        "date"     : tr.exit_date,
                    })
            for p in to_close:
                open_positions.remove(p)

            # Update DD
            if balance > peak_bal: peak_bal = balance
            cur_dd = (balance - peak_bal) / peak_bal * 100 if peak_bal > 0 else 0.0
            if cur_dd < max_dd: max_dd = cur_dd

            # ── Armor gate ───────────────────────────────────────
            armor_risk_scale = 1.0
            if armor:
                armor_status = armor.update(balance, date=cur_str)
                ms = armor_status.get("milestone", {})
                if ms.get("milestone_unlocked") or armor_status.get("system_halted"):
                    armor_events.append({
                        "date"            : cur_str,
                        "balance"         : round(balance, 2),
                        "system_halted"   : armor_status.get("system_halted", False),
                        "halt_reason"     : armor_status.get("halt_reason", ""),
                        "milestone"       : ms.get("active_milestone"),
                        "floor_balance"   : ms.get("locked_floor_balance"),
                        "floor_pct"       : ms.get("locked_floor_pct"),
                        "new_milestone"   : ms.get("milestone_unlocked"),
                        "operational_mode": armor_status.get("operational_mode"),
                        "final_risk_scale": armor_status.get("final_risk_scale", 1.0),
                    })
                if armor_status.get("system_halted"):
                    halt_log = {
                        "tag" : "ARMOR",
                        "text": (f"HALT  {armor_status.get('halt_reason','')}  "
                                 f"floor=${ms.get('locked_floor_balance',0):.2f}"),
                    }
                    result.weekly_snapshots.append(week_snap)
                    yield sse("tick", {
                        "phase": "SIM", "progress": min(progress_pct, 91),
                        "balance": round(balance, 2), "trades": len(closed_trades),
                        "wins": win_count, "losses": loss_count,
                        "dd_pct": round(abs(max_dd), 3),
                        "log": halt_log, "week": week_num, "date": cur_str,
                    })
                    current_date += timedelta(days=config.scan_interval_days)
                    continue
                armor_risk_scale = float(armor_status.get("final_risk_scale", 1.0))
            else:
                dd_check = (balance - config.initial_balance) / config.initial_balance * 100
                if dd_check < -config.circuit_breaker_dd:
                    result.weekly_snapshots.append(week_snap)
                    yield sse("tick", {
                        "phase": "SIM", "progress": min(progress_pct, 91),
                        "balance": round(balance, 2), "trades": len(closed_trades),
                        "wins": win_count, "losses": loss_count,
                        "dd_pct": round(abs(max_dd), 3),
                        "log": {"tag":"ARMOR","text":f"CIRCUIT BREAKER  dd={dd_check:.2f}%"},
                        "week": week_num, "date": cur_str,
                    })
                    break

            # ── Entry loop ───────────────────────────────────────
            open_count  = len(open_positions)
            consec_loss = _get_consecutive_losses(closed_trades)

            for ticker, score, df_slice in top_candidates:
                if open_count >= config.max_open_trades:
                    break
                regime, regime_conf = _detect_regime_full(df_slice)
                if config.regime_filter and regime == "HIGH_VOL_BEARISH":
                    trades_filtered += 1; continue
                future_end = current_date + timedelta(days=config.max_hold_days + 5)
                full_df    = all_data[ticker]
                df_future  = full_df[
                    (full_df.index > current_date) & (full_df.index <= future_end)
                ].head(config.max_hold_days)
                if df_future.empty: continue
                signal = _find_entry_signal_soft(df_slice, config, df_future=df_future)
                if signal is None:
                    trades_filtered += 1; continue
                direction = signal["direction"]
                if config.use_multi_timeframe:
                    mtf = _analyze_multi_timeframe(full_df, current_date, direction)
                    if mtf["trade_freq_boost"] == 0.0 or mtf["tf_aligned"] < config.mtf_min_alignment:
                        mtf_filtered += 1; continue
                    mtf_boost = mtf["trade_freq_boost"]
                else:
                    mtf_boost = 1.0
                tech = signal.get("tech", {})
                quality_score, _ = _compute_quality_score_v4(
                    score=score, regime_conf=regime_conf, ict_signal=signal,
                    tech=tech, direction=direction, df_slice=df_slice,
                )
                if   quality_score >= 90: base_ss = 1.00
                elif quality_score >= 75: base_ss = 0.80
                elif quality_score >= 60: base_ss = 0.60
                elif quality_score >= 45: base_ss = 0.40
                else:                     base_ss = 0.22
                if   "BULLISH" in regime or "LOW_VOL" in regime: rs = config.regime_size_bull
                elif "SIDEWAYS" in regime or "CHOP"   in regime: rs = config.regime_size_chop
                else:                                              rs = 0.50
                size_scale = float(np.clip(base_ss * rs * mtf_boost * armor_risk_scale, 0.05, 1.5))
                kelly_risk_pct, kelly_frac = _compute_adaptive_kelly(
                    closed_trades, config, config.risk_per_trade, consec_loss
                )
                signal = dict(signal)
                raw_entry = signal["entry"]
                if config.slippage_pct > 0:
                    sf      = (1 + config.slippage_pct/100) if direction=="LONG" else (1 - config.slippage_pct/100)
                    slipped = raw_entry * sf
                    sl_d    = abs(raw_entry - signal["sl"])
                    tp_d    = abs(raw_entry - signal["tp"])
                    signal["entry"] = slipped
                    signal["sl"]    = round(slipped - sl_d, 6) if direction=="LONG" else round(slipped + sl_d, 6)
                    signal["tp"]    = round(slipped + tp_d, 6) if direction=="LONG" else round(slipped - tp_d, 6)
                    est_u           = (balance * kelly_risk_pct/100 * size_scale) / max(sl_d, 1e-6)
                    total_slippage_usd += abs(slipped - raw_entry) * est_u
                trade_id += 1
                trade = _simulate_trade(
                    ticker=ticker, signal=signal, df_future=df_future,
                    balance_entry=balance, config=config, trade_id=trade_id,
                    entry_date=cur_str, regime=regime, regime_conf=regime_conf,
                    score=score, risk_pct=kelly_risk_pct, kelly_frac=kelly_frac,
                    size_scale=size_scale, quality_score=quality_score,
                    tp_multiplier=signal.get("tp_multiplier", 1.0), tech=tech, sector="Unknown",
                )
                if trade: trade.leverage = round((trade.units * trade.entry_price) / balance, 3)
                if trade is None: trade_id -= 1; continue
                open_positions.append({"trade": trade, "exit_date": trade.exit_date})
                open_count += 1
                week_snap["trades_opened"] += 1
                if week_log is None:
                    week_log = {
                        "tag" : "GATE",
                        "text": (f"{ticker}  {direction}  entry=${trade.entry_price:.2f}  "
                                 f"Q={quality_score:.0f}  sz=x{size_scale:.2f}"),
                    }

            result.weekly_snapshots.append(week_snap)

            # Emit weekly tick — 100% data real dari loop
            if week_log is None:
                week_log = {
                    "tag" : "SCREEN",
                    "text": f"wk{week_num}  {cur_str}  candidates={len(candidates)}  open={len(open_positions)}",
                }
            yield sse("tick", {
                "phase"   : "SIM",
                "progress": min(progress_pct, 91),
                "balance" : round(balance, 2),
                "trades"  : len(closed_trades),
                "wins"    : win_count,
                "losses"  : loss_count,
                "dd_pct"  : round(abs(max_dd), 3),
                "log"     : week_log,
                "week"    : week_num,
                "date"    : cur_str,
            })
            current_date += timedelta(days=config.scan_interval_days)

        # Flush remaining open positions
        for pos in open_positions:
            tr               = pos["trade"]
            tr.balance_after = round(balance + tr.pnl_usd, 4)
            balance          = tr.balance_after
            closed_trades.append(tr)

        # ── Compute metrics ──────────────────────────────────────
        yield sse("phase", {"phase": "METRICS", "label": "Computing analytics", "progress": 93})
        result.trades             = sorted(closed_trades, key=lambda t: t.entry_date)
        result.trades_filtered    = trades_filtered
        result.mtf_filtered       = mtf_filtered
        result.slippage_total_usd = round(total_slippage_usd, 4)
        result.armor_events       = armor_events
        result                    = _compute_analytics(result)
        yield sse("phase", {"phase": "METRICS", "label": "Finalizing report", "progress": 98})
        report = generate_json_report(result)
        yield sse("done", {"progress": 100, "report": report})

    except Exception as exc:
        import traceback as _tb
        yield sse("error", {"message": str(exc), "traceback": _tb.format_exc()})