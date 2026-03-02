"""
╔══════════════════════════════════════════════════════════════════════╗
║         QUANTUM PORTFOLIO SIMULATOR — BACKTEST ENGINE v1.0          ║
║   1-Year Time Machine · Screener → ICT → Regime → Risk Manager      ║
╚══════════════════════════════════════════════════════════════════════╝

Filosofi:
  Simulator ini menjawab satu pertanyaan sederhana:
  "Kalau kamu punya modal $X dan 100% mengikuti sinyal sistem ini
   selama 1 tahun — berapa saldo kamu sekarang?"

Pipeline per-minggu (rolling window):
  1. SCREENER   → Scan watchlist, ambil top 3 ticker SATIN_READY
  2. REGIME     → Cek apakah market regime mendukung entry
  3. ICT ENGINE → Cari POI (FVG / Order Block) untuk entry presisi
  4. KELLY      → Hitung optimal position size berdasarkan edge
  5. RISK MGR   → Validasi circuit breaker & daily loss limit
  6. SIMULATE   → Forward simulate trade dengan SL/TP dari ICT
  7. LOG        → Catat semua hasil ke TradeJournal

Author  : APEX System
Version : 1.0.0
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
from app.engine.regime_engine import detect_hmm_regime
from app.engine.ict_engine import get_ict_full_analysis
from app.engine.quant_engine import calculate_technicals

warnings.filterwarnings("ignore")


# ══════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class TradeRecord:
    """Rekaman lengkap satu trade dari entry sampai exit."""
    trade_id     : int
    ticker       : str
    entry_date   : str
    exit_date    : str
    direction    : str          # LONG / SHORT
    entry_price  : float
    exit_price   : float
    stop_loss    : float
    take_profit  : float
    units        : float
    pnl_usd      : float
    pnl_pct      : float
    outcome      : str          # WIN / LOSS / BE (Break Even)
    regime       : str
    screener_score: float
    balance_after : float
    exit_reason  : str          # TP_HIT / SL_HIT / TIME_EXIT / CIRCUIT_BREAK


@dataclass  
class SimulationConfig:
    """Konfigurasi lengkap untuk satu run simulasi."""
    initial_balance : float = 100.0
    risk_per_trade  : float = 2.0       # % risiko per trade
    max_open_trades : int   = 3         # Maks posisi bersamaan
    sl_atr_mult     : float = 1.5       # Stop Loss = 1.5x ATR
    tp_rr_ratio     : float = 2.0       # Take Profit = 2R
    min_screener_score: float = 65.0    # Min skor Screener untuk entry
    scan_universe   : str   = "US"      # IDX / US / CRYPTO
    lookback_years  : int   = 1         # Durasi simulasi (tahun)
    max_hold_days   : int   = 15        # Maks hari pegang posisi
    commission_pct  : float = 0.1       # Komisi per trade (%)
    regime_filter   : bool  = True      # Aktifkan filter regime HMM


@dataclass
class SimulationResult:
    """Output lengkap hasil simulasi."""
    config          : SimulationConfig
    trades          : List[TradeRecord] = field(default_factory=list)
    equity_curve    : List[Dict]        = field(default_factory=list)
    weekly_snapshots: List[Dict]        = field(default_factory=list)
    final_balance   : float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio    : float = 0.0
    sortino_ratio   : float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct    : float = 0.0
    profit_factor   : float = 0.0
    total_trades    : int   = 0
    winning_trades  : int   = 0
    losing_trades   : int   = 0
    avg_win_pct     : float = 0.0
    avg_loss_pct    : float = 0.0
    best_trade      : Optional[TradeRecord] = None
    worst_trade     : Optional[TradeRecord] = None
    longest_drawdown_days: int = 0
    calmar_ratio    : float = 0.0
    expectancy_usd  : float = 0.0


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


# ══════════════════════════════════════════════════════════════════
#  LAYER 1 — DATA FETCHER
# ══════════════════════════════════════════════════════════════════

def _fetch_historical_data(ticker: str, start: datetime, end: datetime) -> Optional[pd.DataFrame]:
    """
    Fetch data OHLCV historis lengkap untuk periode simulasi.
    Menggunakan Yahoo Finance dengan error handling robust.
    """
    for attempt in range(3):
        try:
            time.sleep(0.15)  # Rate limit protection
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
#  LAYER 2 — MINI SCREENER (Standalone, no app imports)
# ══════════════════════════════════════════════════════════════════

def _score_ticker(df_slice: pd.DataFrame) -> float:
    """
    Scoring menggunakan engine real dari screener_engine.py.
    """
    res = score_ticker_from_df(df_slice)
    return res.get("score", 0.0)


# ══════════════════════════════════════════════════════════════════
#  LAYER 3 — MINI REGIME DETECTOR
# ══════════════════════════════════════════════════════════════════

def _detect_regime_simple(df_slice: pd.DataFrame) -> Tuple[str, float]:
    """
    Deteksi regime menggunakan HMM engine real dari regime_engine.py.
    """
    res = detect_hmm_regime(df_slice)
    if "error" in res:
        return "UNKNOWN", 0.0
    return res.get("current_regime", "UNKNOWN"), res.get("confidence_pct", 0.0)


# ══════════════════════════════════════════════════════════════════
#  LAYER 4 — MINI ICT / ENTRY LOGIC
# ══════════════════════════════════════════════════════════════════

def _calculate_atr(df_slice: pd.DataFrame, period: int = 14) -> float:
    """Hitung ATR untuk penentuan SL/TP."""
    if len(df_slice) < period + 1:
        return float(df_slice["Close"].std()) if len(df_slice) > 1 else 1.0

    high  = df_slice["High"].values.astype(float)
    low   = df_slice["Low"].values.astype(float)
    close = df_slice["Close"].values.astype(float)

    trs = [max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
           for i in range(1, len(close))]
    return float(np.mean(trs[-period:]))


def _find_entry_signal(df_slice: pd.DataFrame, config: SimulationConfig) -> Optional[Dict]:
    """
    Cari sinyal entry berdasarkan ICT Full Analysis.
    Menerjemahkan bias ICT menjadi setup trade dengan SL/TP.
    """
    ict = get_ict_full_analysis(df_slice)
    bias = ict.get("composite_bias", "NEUTRAL")
    
    if bias == "NEUTRAL":
        return None

    close = float(df_slice["Close"].iloc[-1])
    atr   = _calculate_atr(df_slice, period=14)
    
    sl_dist = atr * config.sl_atr_mult
    tp_dist = sl_dist * config.tp_rr_ratio

    if bias == "BULLISH":
        return {
            "direction": "LONG",
            "entry"    : close,
            "sl"       : round(close - sl_dist, 6),
            "tp"       : round(close + tp_dist, 6),
            "atr"      : round(atr, 6),
            "setup"    : f"ICT_{ict.get('bias_strength')}_BULLISH"
        }
    elif bias == "BEARISH":
        return {
            "direction": "SHORT",
            "entry"    : close,
            "sl"       : round(close + sl_dist, 6),
            "tp"       : round(close - tp_dist, 6),
            "atr"      : round(atr, 6),
            "setup"    : f"ICT_{ict.get('bias_strength')}_BEARISH"
        }

    return None


# ══════════════════════════════════════════════════════════════════
#  LAYER 5 — TRADE SIMULATOR
# ══════════════════════════════════════════════════════════════════

def _simulate_trade(
    ticker     : str,
    signal     : Dict,
    df_future  : pd.DataFrame,
    balance    : float,
    config     : SimulationConfig,
    trade_id   : int,
    entry_date : str,
    regime     : str,
    score      : float
) -> Optional[TradeRecord]:
    """
    Forward-simulate satu trade pada data historis.
    Cek setiap candle: apakah SL atau TP sudah tercapai.
    """
    if df_future is None or df_future.empty:
        return None

    risk_usd    = balance * (config.risk_per_trade / 100)
    sl_distance = abs(signal["entry"] - signal["sl"])
    if sl_distance == 0:
        return None

    # Hitung commission
    commission  = balance * (config.commission_pct / 100)
    units       = risk_usd / sl_distance

    direction   = signal["direction"]
    entry       = signal["entry"]
    sl_price    = signal["sl"]
    tp_price    = signal["tp"]

    for i, (date, row) in enumerate(df_future.iterrows()):
        if i >= config.max_hold_days:
            # Time exit: close at current close
            exit_price = float(row["Close"])
            exit_reason = "TIME_EXIT"
            break

        high = float(row["High"])
        low  = float(row["Low"])

        if direction == "LONG":
            if low <= sl_price:
                exit_price  = sl_price
                exit_reason = "SL_HIT"
                break
            elif high >= tp_price:
                exit_price  = tp_price
                exit_reason = "TP_HIT"
                break
        else:  # SHORT
            if high >= sl_price:
                exit_price  = sl_price
                exit_reason = "SL_HIT"
                break
            elif low <= tp_price:
                exit_price  = tp_price
                exit_reason = "TP_HIT"
                break
    else:
        exit_price  = float(df_future["Close"].iloc[-1])
        exit_reason = "TIME_EXIT"
        date        = df_future.index[-1]

    # ── P&L Calculation ──
    if direction == "LONG":
        raw_pnl = (exit_price - entry) * units
    else:
        raw_pnl = (entry - exit_price) * units

    net_pnl     = raw_pnl - commission
    pnl_pct     = (net_pnl / balance) * 100
    balance_after = balance + net_pnl

    outcome = "WIN" if net_pnl > 0 else ("BE" if abs(net_pnl) < 0.01 else "LOSS")

    exit_date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)

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
        units         = round(units, 6),
        pnl_usd       = round(net_pnl, 4),
        pnl_pct       = round(pnl_pct, 4),
        outcome       = outcome,
        regime        = regime,
        screener_score= score,
        balance_after = round(balance_after, 4),
        exit_reason   = exit_reason
    )


# ══════════════════════════════════════════════════════════════════
#  LAYER 6 — ANALYTICS ENGINE
# ══════════════════════════════════════════════════════════════════

def _compute_analytics(result: SimulationResult) -> SimulationResult:
    """
    Hitung semua metrik performa dari daftar trades yang sudah ada.
    Modifies result in-place dan return.
    """
    trades = result.trades
    if not trades:
        return result

    pnls   = np.array([t.pnl_usd for t in trades])
    pnl_pcts = np.array([t.pnl_pct for t in trades])
    wins   = [t for t in trades if t.outcome == "WIN"]
    losses = [t for t in trades if t.outcome == "LOSS"]

    result.total_trades    = len(trades)
    result.winning_trades  = len(wins)
    result.losing_trades   = len(losses)
    result.win_rate_pct    = round(len(wins) / len(trades) * 100, 2) if trades else 0

    # Profit Factor
    gross_win  = sum(t.pnl_usd for t in wins)  if wins   else 0
    gross_loss = abs(sum(t.pnl_usd for t in losses)) if losses else 0
    result.profit_factor = round(gross_win / gross_loss, 3) if gross_loss > 0 else 9999.0

    # Avg Win / Loss
    result.avg_win_pct  = round(np.mean([t.pnl_pct for t in wins]),  4) if wins   else 0
    result.avg_loss_pct = round(np.mean([t.pnl_pct for t in losses]),4) if losses else 0

    # Expectancy
    if trades:
        wr = result.winning_trades / result.total_trades
        result.expectancy_usd = round(
            (wr * (gross_win / len(wins) if wins else 0)) -
            ((1 - wr) * (gross_loss / len(losses) if losses else 0)),
            4
        )

    # Build equity curve (Aggregate by date to prevent duplicates for Lightweight Charts)
    daily_equity = {}
    running_bal = result.config.initial_balance
    
    # Starting point
    start_date = trades[0].entry_date if trades else datetime.now().strftime("%Y-%m-%d")
    daily_equity[start_date] = running_bal
    
    for t in trades:
        running_bal += t.pnl_usd
        # We take the latest balance for each date
        daily_equity[t.exit_date] = round(running_bal, 4)

    sorted_dates = sorted(daily_equity.keys())
    
    # Add final point for current/end date to ensure the chart doesn't cut off early
    # This is helpful if a Circuit Breaker hits or no trades happen for a while
    end_date_str = trades[-1].exit_date if trades else datetime.now().strftime("%Y-%m-%d")
    if sorted_dates and end_date_str not in daily_equity:
        daily_equity[end_date_str] = round(running_bal, 4)
        sorted_dates.append(end_date_str)
        sorted_dates.sort()

    result.equity_curve = [
        {"time": d, "balance": daily_equity[d]} 
        for d in sorted_dates
    ]
    
    print(f"DEBUG: Portfolio Simulator - Equity Curve Points: {len(result.equity_curve)}")
    if result.equity_curve:
        print(f"DEBUG: Sample Point: {result.equity_curve[0]}")

    result.final_balance   = round(running_bal, 4)
    result.total_return_pct = round((running_bal - result.config.initial_balance) /
                                     result.config.initial_balance * 100, 2)

    # Sharpe & Sortino (annualized)
    if len(pnl_pcts) > 1:
        mean_r = np.mean(pnl_pcts) * 252 / result.total_trades * result.total_trades
        std_r  = np.std(pnl_pcts)
        down_r = pnl_pcts[pnl_pcts < 0]

        mean_daily = np.mean(pnl_pcts)
        std_daily  = np.std(pnl_pcts)
        result.sharpe_ratio = round(
            (mean_daily / std_daily) * np.sqrt(252) if std_daily > 0 else 0, 3
        )
        down_std = np.std(down_r) if len(down_r) > 1 else std_daily
        result.sortino_ratio = round(
            (mean_daily / down_std) * np.sqrt(252) if down_std > 0 else 0, 3
        )

    # Max Drawdown
    balances = [point["balance"] for point in result.equity_curve]
    eq_arr = np.array(balances)
    peaks  = np.maximum.accumulate(eq_arr)
    
    if len(peaks) > 0 and peaks[-1] > 0:
        dds = (eq_arr - peaks) / peaks * 100
        result.max_drawdown_pct = round(float(np.min(dds)), 2)
    else:
        result.max_drawdown_pct = 0.0

    # Calmar Ratio
    if result.max_drawdown_pct < 0:
        result.calmar_ratio = round(result.total_return_pct / abs(result.max_drawdown_pct), 3)
    else:
        result.calmar_ratio = 0.0

    # Best & Worst trade
    if trades:
        result.best_trade  = max(trades, key=lambda t: t.pnl_usd)
        result.worst_trade = min(trades, key=lambda t: t.pnl_usd)

    return result


# ══════════════════════════════════════════════════════════════════
#  LAYER 7 — MASTER SIMULATION RUNNER
# ══════════════════════════════════════════════════════════════════

def run_simulation(config: SimulationConfig) -> SimulationResult:
    """
    ╔══════════════════════════════════════════════════════════════╗
    ║  MASTER ENTRY POINT — Quantum Portfolio Simulator           ║
    ╚══════════════════════════════════════════════════════════════╝

    Menjalankan simulasi penuh 1 tahun step-by-step:
      - Setiap minggu: scan universe, pick top candidates
      - Setiap kandidat: cek regime + cari entry signal
      - Setiap sinyal: forward simulate dengan SL/TP
      - Accumulate balance & equity curve

    Args:
        config: SimulationConfig object

    Returns:
        SimulationResult dengan semua metrics & trade log
    """
    result   = SimulationResult(config=config)
    balance  = config.initial_balance
    trade_id = 0

    # ── Setup timeline ──────────────────────────────────────────
    end_date   = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=365 * config.lookback_years)
    tickers    = WATCHLISTS.get(config.scan_universe, WATCHLISTS["US"])

    print(f"\n{'═'*65}")
    print(f"  QUANTUM PORTFOLIO SIMULATOR")
    print(f"  Universe : {config.scan_universe} ({len(tickers)} tickers)")
    print(f"  Period   : {start_date.date()} → {end_date.date()}")
    print(f"  Capital  : ${config.initial_balance:,.2f}")
    print(f"  Risk/Trade: {config.risk_per_trade}%")
    print(f"{'═'*65}")

    # ── Fetch semua data di awal (lebih efisien) ──────────────────
    print("\n📡 Fetching historical data for all tickers...")
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
        print("❌ No valid data fetched. Abort.")
        return result

    print(f"\n✅ {len(all_data)} tickers loaded successfully.")

    # ── Rolling weekly scan ───────────────────────────────────────
    open_positions: List[Dict] = []   # Track open trades
    current_date   = start_date + timedelta(days=60)  # Warmup period
    week_num       = 0

    print(f"\n🔄 Starting rolling weekly scan...\n")

    while current_date <= end_date - timedelta(days=config.max_hold_days):
        week_num   += 1
        candidates  = []

        # ── STEP 1: Score all tickers on this week's slice ─────
        for ticker, full_df in all_data.items():
            df_slice = full_df[full_df.index <= current_date].tail(90)
            if len(df_slice) < 55:
                continue
            score = _score_ticker(df_slice)
            if score >= config.min_screener_score:
                candidates.append((ticker, score, df_slice))

        # Sort by score descending — take top N
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_candidates = candidates[:config.max_open_trades]

        week_snapshot = {
            "week"         : week_num,
            "date"         : current_date.strftime("%Y-%m-%d"),
            "balance"      : round(balance, 4),
            "candidates"   : len(candidates),
            "trades_opened": 0,
            "open_positions": len(open_positions)
        }

        # ── STEP 2: Check & close expired open positions ────────
        positions_to_close = []
        for pos in open_positions:
            exit_date_obj = datetime.strptime(pos["exit_date"], "%Y-%m-%d")
            if current_date >= exit_date_obj:
                balance += pos["trade"].pnl_usd
                result.trades.append(pos["trade"])
                positions_to_close.append(pos)

        for p in positions_to_close:
            open_positions.remove(p)

        # ── STEP 3: Circuit Breaker ─────────────────────────────
        # Don't trade if we're down > 15% from initial (hard circuit breaker)
        drawdown_from_start = (balance - config.initial_balance) / config.initial_balance * 100
        if drawdown_from_start < -15:
            print(f"   Week {week_num:3d} | 🛑 CIRCUIT BREAKER: DD={drawdown_from_start:.1f}%")
            current_date += timedelta(days=7)
            result.weekly_snapshots.append(week_snapshot)
            continue

        # ── STEP 4: Find entry signals & simulate ───────────────
        open_count = len(open_positions)

        for ticker, score, df_slice in top_candidates:
            if open_count >= config.max_open_trades:
                break

            # Regime filter
            regime, regime_conf = _detect_regime_simple(df_slice)
            if config.regime_filter and regime == "HIGH_VOL_BEARISH":
                continue  # Skip high vol bearish regime

            # Find entry signal
            signal = _find_entry_signal(df_slice, config)
            if signal is None:
                continue

            # Get future data for forward simulation
            future_start = current_date + timedelta(days=1)
            future_end   = current_date + timedelta(days=config.max_hold_days + 5)
            full_df      = all_data[ticker]
            df_future    = full_df[
                (full_df.index > current_date) &
                (full_df.index <= future_end)
            ].head(config.max_hold_days)

            if df_future.empty:
                continue

            entry_date = current_date.strftime("%Y-%m-%d")
            trade_id  += 1

            trade = _simulate_trade(
                ticker     = ticker,
                signal     = signal,
                df_future  = df_future,
                balance    = balance,
                config     = config,
                trade_id   = trade_id,
                entry_date = entry_date,
                regime     = regime,
                score      = score
            )

            if trade is None:
                continue

            # Schedule this position
            open_positions.append({
                "trade"    : trade,
                "exit_date": trade.exit_date
            })
            open_count += 1
            week_snapshot["trades_opened"] += 1

            # Immediately update balance for closed position tracking
            balance = trade.balance_after

            icon = "✅" if trade.outcome == "WIN" else "❌"
            print(f"   Week {week_num:3d} | {icon} {ticker:10s} "
                  f"{signal['direction']:5s} | "
                  f"Score:{score:5.1f} | "
                  f"P&L: ${trade.pnl_usd:+7.2f} ({trade.pnl_pct:+.2f}%) | "
                  f"Bal: ${balance:,.2f}")

        result.weekly_snapshots.append(week_snapshot)
        current_date += timedelta(days=7)  # Move forward 1 week

    # ── Flush any remaining open positions ─────────────────────
    for pos in open_positions:
        balance += pos["trade"].pnl_usd
        result.trades.append(pos["trade"])

    # ── Sort trades chronologically ──────────────────────────────
    result.trades.sort(key=lambda t: t.entry_date)

    # ── Compute final analytics ──────────────────────────────────
    result = _compute_analytics(result)

    return result


# ══════════════════════════════════════════════════════════════════
#  LAYER 8 — REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════

def print_report(result: SimulationResult) -> None:
    """Cetak laporan simulasi yang komprehensif ke console."""
    cfg = result.config
    sep = "═" * 65

    print(f"\n{sep}")
    print(f"  QUANTUM PORTFOLIO SIMULATOR — FINAL REPORT")
    print(f"{sep}")
    print(f"  Universe : {cfg.scan_universe}")
    print(f"  Period   : {cfg.lookback_years} Year(s)")
    print(f"  Capital  : ${cfg.initial_balance:,.2f}  →  ${result.final_balance:,.2f}")
    print(f"  Return   : {result.total_return_pct:+.2f}%")
    print(f"  Max DD   : {result.max_drawdown_pct:.2f}%")
    print(f"{sep}")
    print(f"\n  📊 PERFORMANCE METRICS")
    print(f"  {'Sharpe Ratio':<30} {result.sharpe_ratio:>10.3f}")
    print(f"  {'Sortino Ratio':<30} {result.sortino_ratio:>10.3f}")
    print(f"  {'Calmar Ratio':<30} {result.calmar_ratio:>10.3f}")
    print(f"  {'Profit Factor':<30} {result.profit_factor:>10.3f}")
    print(f"  {'Expectancy per Trade':<30} ${result.expectancy_usd:>9.2f}")
    print(f"\n  🎯 TRADE STATISTICS")
    print(f"  {'Total Trades':<30} {result.total_trades:>10d}")
    print(f"  {'Win Rate':<30} {result.win_rate_pct:>9.1f}%")
    print(f"  {'Winning Trades':<30} {result.winning_trades:>10d}")
    print(f"  {'Losing Trades':<30} {result.losing_trades:>10d}")
    print(f"  {'Avg Win':<30} {result.avg_win_pct:>9.2f}%")
    print(f"  {'Avg Loss':<30} {result.avg_loss_pct:>9.2f}%")

    if result.best_trade:
        print(f"\n  🏆 BEST TRADE")
        print(f"     {result.best_trade.ticker} ({result.best_trade.entry_date}) "
              f"+${result.best_trade.pnl_usd:.2f} ({result.best_trade.pnl_pct:+.2f}%)")

    if result.worst_trade:
        print(f"\n  💀 WORST TRADE")
        print(f"     {result.worst_trade.ticker} ({result.worst_trade.entry_date}) "
              f"${result.worst_trade.pnl_usd:.2f} ({result.worst_trade.pnl_pct:+.2f}%)")

    print(f"\n{sep}\n")


def generate_json_report(result: SimulationResult) -> Dict:
    """
    Export hasil simulasi sebagai dict JSON-serializable.
    Siap untuk dikonsumsi oleh frontend / API endpoint.
    """
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
            "screener_score": t.screener_score,
            "balance_after" : t.balance_after,
            "exit_reason"   : t.exit_reason
        })

    return {
        "config": {
            "initial_balance"   : result.config.initial_balance,
            "risk_per_trade"    : result.config.risk_per_trade,
            "scan_universe"     : result.config.scan_universe,
            "tp_rr_ratio"       : result.config.tp_rr_ratio,
            "min_screener_score": result.config.min_screener_score,
        },
        "summary": {
            "final_balance"     : result.final_balance,
            "total_return_pct"  : result.total_return_pct,
            "sharpe_ratio"      : result.sharpe_ratio,
            "sortino_ratio"     : result.sortino_ratio,
            "calmar_ratio"      : result.calmar_ratio,
            "max_drawdown_pct"  : result.max_drawdown_pct,
            "profit_factor"     : result.profit_factor,
            "win_rate_pct"      : result.win_rate_pct,
            "total_trades"      : result.total_trades,
            "winning_trades"    : result.winning_trades,
            "losing_trades"     : result.losing_trades,
            "avg_win_pct"       : result.avg_win_pct,
            "avg_loss_pct"      : result.avg_loss_pct,
            "expectancy_usd"    : result.expectancy_usd,
        },
        "equity_curve"      : result.equity_curve,
        "trades"            : trades_list,
        "weekly_snapshots"  : result.weekly_snapshots,
        "best_trade"        : trades_list[result.trades.index(result.best_trade)] if result.best_trade and result.best_trade in result.trades else None,
        "worst_trade"       : trades_list[result.trades.index(result.worst_trade)] if result.worst_trade and result.worst_trade in result.trades else None,
    }


# ══════════════════════════════════════════════════════════════════
#  ENTRYPOINT — Standalone test
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = SimulationConfig(
        initial_balance    = 100.0,    # Modal awal $100
        risk_per_trade     = 2.0,      # Risk 2% per trade
        max_open_trades    = 3,        # Maks 3 posisi bersamaan
        sl_atr_mult        = 1.5,      # SL = 1.5x ATR
        tp_rr_ratio        = 2.0,      # TP = 2R
        min_screener_score = 65.0,     # Minimum skor screener
        scan_universe      = "US",     # Scan US stocks
        lookback_years     = 1,        # 1 tahun simulasi
        max_hold_days      = 15,       # Maks 15 hari pegang
        commission_pct     = 0.1,      # Komisi 0.1%
        regime_filter      = True      # Aktifkan regime filter
    )

    result = run_simulation(config)
    print_report(result)

    import json
    report = generate_json_report(result)
    with open("simulation_result.json", "w") as f:
        json.dump(report, f, indent=2)
    print("📁 Full report saved to simulation_result.json")