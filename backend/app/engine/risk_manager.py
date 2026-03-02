"""
╔══════════════════════════════════════════════════════════════════╗
║            SATIN — RISK MANAGER & WATCHDOG ENGINE               ║
║   Daily Loss Circuit Breaker · Drawdown Monitor · Trade Audit   ║
╚══════════════════════════════════════════════════════════════════╝

Satin bukan peramal harga. Satin adalah:
  1. Risk Manager      → Hitung apakah sebuah trade layak masuk
  2. Circuit Breaker   → Lock trading jika DD harian terlampaui
  3. Trade Auditor     → Rekam + evaluasi setiap keputusan trading
  4. Psychological Guard → Deteksi overtrading & revenge trading
  5. Backtesting Runner  → Evaluasi strategi di data historis

Semua state disimpan di memori per-session.
Untuk persistensi nyata, sambungkan ke Redis / SQLite.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import json
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  GLOBAL STATE (in-memory; ganti dengan DB untuk production)
# ─────────────────────────────────────────────────────────────────

_risk_state = {
    "account_balance"      : 30_000.0,
    "initial_balance"      : 30_000.0,
    "daily_start_balance"  : 30_000.0,
    "daily_pnl_pct"        : 0.0,
    "session_trades"       : [],
    "is_locked"            : False,
    "lock_reason"          : "",
    "lock_timestamp"       : None,
    "trade_log"            : [],
    "last_reset_date"      : datetime.now().date().isoformat(),
    # Risk Rules (bisa dikonfigurasi)
    "rules": {
        "max_daily_loss_pct"    : 2.0,   # Circuit breaker: lock jika DD harian > 2%
        "max_drawdown_pct"      : 10.0,  # Lock jika drawdown keseluruhan > 10%
        "max_trades_per_day"    : 5,     # Max trades sebelum cooldown
        "max_risk_per_trade_pct": 1.0,   # Max risk per trade
        "cooldown_minutes"      : 60,    # Waktu lock setelah circuit breaker
        "revenge_trade_window_min": 15,  # Window deteksi revenge trading
        "max_losses_in_window"  : 3,     # Max losses dalam window sebelum lock
    }
}


# ─────────────────────────────────────────────────────────────────
#  1. CIRCUIT BREAKER & DAILY RESET
# ─────────────────────────────────────────────────────────────────

def check_and_reset_daily(balance_update: Optional[float] = None) -> Dict:
    """
    Cek apakah hari sudah berganti dan reset counter harian.
    Juga update daily_start_balance jika ada balance baru.
    """
    global _risk_state

    today = datetime.now().date().isoformat()
    if today != _risk_state["last_reset_date"]:
        _risk_state["daily_start_balance"] = _risk_state["account_balance"]
        _risk_state["daily_pnl_pct"]       = 0.0
        _risk_state["session_trades"]      = []
        _risk_state["last_reset_date"]     = today
        # Lepas lock waktu-based jika cooldown sudah habis
        if _risk_state["is_locked"] and _risk_state["lock_timestamp"]:
            lock_time = datetime.fromisoformat(_risk_state["lock_timestamp"])
            if datetime.now() - lock_time > timedelta(hours=24):
                _risk_state["is_locked"]   = False
                _risk_state["lock_reason"] = ""

    if balance_update is not None:
        _risk_state["account_balance"] = balance_update

    daily_pnl = (_risk_state["account_balance"] - _risk_state["daily_start_balance"]) / _risk_state["daily_start_balance"] * 100
    _risk_state["daily_pnl_pct"] = round(daily_pnl, 4)

    return {
        "date"              : today,
        "account_balance"   : _risk_state["account_balance"],
        "daily_start_bal"   : _risk_state["daily_start_balance"],
        "daily_pnl_pct"     : _risk_state["daily_pnl_pct"],
        "is_locked"         : _risk_state["is_locked"],
        "lock_reason"       : _risk_state["lock_reason"],
        "session_trades"    : len(_risk_state["session_trades"]),
    }


def trigger_circuit_breaker(reason: str) -> Dict:
    """Paksa lock akun trading dengan alasan tertentu."""
    global _risk_state
    _risk_state["is_locked"]      = True
    _risk_state["lock_reason"]    = reason
    _risk_state["lock_timestamp"] = datetime.now().isoformat()

    return {
        "status"     : "LOCKED",
        "reason"     : reason,
        "timestamp"  : _risk_state["lock_timestamp"],
        "message"    : f"⛔ SATIN HAS LOCKED YOUR ACCOUNT: {reason}. Tunggu cooldown atau reset manual."
    }


def release_lock(override_reason: str = "Manual override") -> Dict:
    """Lepas lock manual dengan alasan yang wajib dicatat."""
    global _risk_state
    _risk_state["is_locked"]   = False
    _risk_state["lock_reason"] = ""
    return {"status": "UNLOCKED", "override_reason": override_reason, "timestamp": datetime.now().isoformat()}


# ─────────────────────────────────────────────────────────────────
#  2. PRE-TRADE RISK CHECK
# ─────────────────────────────────────────────────────────────────

def pre_trade_check(
    entry_price    : float,
    stop_loss_price: float,
    position_size  : float,
    ticker         : str,
    direction      : str = "LONG"
) -> Dict:
    """
    Jalankan semua cek risiko SEBELUM membuka posisi.
    Satin akan APPROVE atau REJECT trade berdasarkan rules.

    Args:
        entry_price    : Harga entry
        stop_loss_price: Harga stop loss
        position_size  : Ukuran posisi dalam USD
        ticker         : Symbol aset
        direction      : 'LONG' atau 'SHORT'
    """
    global _risk_state
    check_and_reset_daily()

    warnings_list = []
    rejections    = []

    # ── 1. Circuit Breaker Check ──
    if _risk_state["is_locked"]:
        return {
            "approved"   : False,
            "reason"     : f"ACCOUNT LOCKED: {_risk_state['lock_reason']}",
            "warnings"   : [],
            "rejections" : [_risk_state["lock_reason"]],
            "satin_msg"  : "⛔ Satin: Akun terkunci. Saya tidak mengizinkan trade ini."
        }

    balance = _risk_state["account_balance"]

    # ── 2. Daily Loss Check ──
    max_daily_loss = _risk_state["rules"]["max_daily_loss_pct"]
    if _risk_state["daily_pnl_pct"] <= -max_daily_loss:
        trigger_circuit_breaker(f"Daily loss limit {max_daily_loss}% tercapai (PnL: {_risk_state['daily_pnl_pct']:.2f}%)")
        rejections.append(f"Daily loss limit {max_daily_loss}% sudah tercapai.")

    # ── 3. Risk Per Trade Check ──
    risk_amount = abs(entry_price - stop_loss_price) * (position_size / entry_price)
    risk_pct    = (risk_amount / balance) * 100
    max_risk    = _risk_state["rules"]["max_risk_per_trade_pct"]

    if risk_pct > max_risk * 2:
        rejections.append(f"Risk per trade {risk_pct:.2f}% jauh melampaui limit {max_risk}%.")
    elif risk_pct > max_risk:
        warnings_list.append(f"⚠️ Risk per trade {risk_pct:.2f}% melebihi rekomendasi {max_risk}%. Kurangi size.")

    # ── 4. Max Trades Per Day ──
    n_trades = len(_risk_state["session_trades"])
    max_trades = _risk_state["rules"]["max_trades_per_day"]
    if n_trades >= max_trades:
        warnings_list.append(f"⚠️ Sudah {n_trades} trades hari ini. Kamu mendekati limit harian ({max_trades}).")

    # ── 5. Revenge Trading Detection ──
    revenge = _detect_revenge_trading()
    if revenge["detected"]:
        rejections.append(f"REVENGE TRADE DETECTED: {revenge['message']}")

    # ── 6. Overall Drawdown ──
    total_dd = (balance - _risk_state["initial_balance"]) / _risk_state["initial_balance"] * 100
    max_dd   = _risk_state["rules"]["max_drawdown_pct"]
    if total_dd <= -max_dd:
        trigger_circuit_breaker(f"Max drawdown {max_dd}% tercapai dari modal awal.")
        rejections.append(f"Total drawdown {abs(total_dd):.2f}% dari modal awal sudah mencapai limit.")

    # ── Final Decision ──
    approved = len(rejections) == 0

    if approved and warnings_list:
        satin_msg = f"✅ Satin: Trade DISETUJUI dengan catatan — " + " | ".join(warnings_list)
    elif approved:
        satin_msg = f"✅ Satin: Trade DISETUJUI. Risk {risk_pct:.2f}% dari akun. Tetap disiplin."
    else:
        satin_msg = f"⛔ Satin: Trade DITOLAK — " + " | ".join(rejections)

    return {
        "approved"        : approved,
        "ticker"          : ticker,
        "direction"       : direction,
        "entry_price"     : entry_price,
        "stop_loss_price" : stop_loss_price,
        "position_size"   : position_size,
        "risk_amount_usd" : round(risk_amount, 2),
        "risk_pct"        : round(risk_pct, 4),
        "daily_pnl_pct"   : _risk_state["daily_pnl_pct"],
        "session_trades"  : n_trades,
        "warnings"        : warnings_list,
        "rejections"      : rejections,
        "revenge_check"   : revenge,
        "satin_msg"       : satin_msg
    }


# ─────────────────────────────────────────────────────────────────
#  3. TRADE RECORDER (Post-Trade)
# ─────────────────────────────────────────────────────────────────

def record_trade(
    ticker     : str,
    direction  : str,
    entry      : float,
    exit_price : float,
    size_usd   : float,
    notes      : str = ""
) -> Dict:
    """
    Rekam hasil trade dan update balance.
    Otomatis trigger circuit breaker jika limit terlampaui.
    """
    global _risk_state
    check_and_reset_daily()

    pnl_per_unit = (exit_price - entry) if direction == "LONG" else (entry - exit_price)
    pnl_pct      = (pnl_per_unit / entry) * 100
    pnl_usd      = (pnl_pct / 100) * size_usd

    # Update balance
    _risk_state["account_balance"] += pnl_usd

    trade_record = {
        "id"         : len(_risk_state["trade_log"]) + 1,
        "timestamp"  : datetime.now().isoformat(),
        "ticker"     : ticker,
        "direction"  : direction,
        "entry"      : entry,
        "exit"       : exit_price,
        "size_usd"   : size_usd,
        "pnl_pct"    : round(pnl_pct, 4),
        "pnl_usd"    : round(pnl_usd, 2),
        "result"     : "WIN" if pnl_usd > 0 else "LOSS" if pnl_usd < 0 else "BREAK_EVEN",
        "notes"      : notes,
        "balance_after": round(_risk_state["account_balance"], 2)
    }

    _risk_state["session_trades"].append(trade_record)
    _risk_state["trade_log"].append(trade_record)

    # Recalculate daily PnL
    daily_dd = (_risk_state["account_balance"] - _risk_state["daily_start_balance"]) / _risk_state["daily_start_balance"] * 100
    _risk_state["daily_pnl_pct"] = round(daily_dd, 4)

    # Auto circuit breaker
    auto_lock_msg = None
    if daily_dd <= -_risk_state["rules"]["max_daily_loss_pct"]:
        lock_result  = trigger_circuit_breaker(f"Daily loss limit tercapai setelah trade #{trade_record['id']}")
        auto_lock_msg = lock_result["message"]

    return {
        "trade"          : trade_record,
        "new_balance"    : round(_risk_state["account_balance"], 2),
        "daily_pnl_pct"  : _risk_state["daily_pnl_pct"],
        "account_locked" : _risk_state["is_locked"],
        "auto_lock_msg"  : auto_lock_msg
    }


# ─────────────────────────────────────────────────────────────────
#  4. BACKTEST ENGINE (SIMPLIFIED)
# ─────────────────────────────────────────────────────────────────

def run_backtest(
    df           : pd.DataFrame,
    strategy_fn,                   # Callable(df, i) -> {"signal": "BUY"/"SELL"/None, "sl_pct": float, "tp_pct": float}
    initial_capital: float = 30_000,
    risk_per_trade : float = 0.01,  # 1% per trade
    commission_pct : float = 0.001  # 0.1% per trade
) -> Dict:
    """
    Runner backtesting sederhana dengan position sizing berbasis fixed-risk.

    Args:
        df             : OHLCV DataFrame historis
        strategy_fn    : Fungsi strategi kamu — dipanggil tiap candle
        initial_capital: Modal awal
        risk_per_trade : Fraksi modal yang di-risk per trade
        commission_pct : Komisi per trade (kedua sisi)
    """
    if df is None or df.empty:
        return {"error": "Data tidak valid"}

    capital    = initial_capital
    equity_curve = [capital]
    trades     = []
    in_trade   = False
    entry_p    = sl_p = tp_p = 0.0
    direction  = "LONG"

    for i in range(20, len(df)):
        df_slice = df.iloc[:i+1]
        price    = float(df['Close'].iloc[i])

        if in_trade:
            # Check SL/TP hit
            if direction == "LONG":
                if float(df['Low'].iloc[i]) <= sl_p:
                    pnl = (sl_p - entry_p) / entry_p
                    capital += capital * risk_per_trade * pnl - capital * risk_per_trade * commission_pct
                    trades.append({"type": "LONG_LOSS", "pnl_pct": round(pnl*100,4), "exit": sl_p})
                    in_trade = False
                elif float(df['High'].iloc[i]) >= tp_p:
                    pnl = (tp_p - entry_p) / entry_p
                    capital += capital * risk_per_trade * pnl - capital * risk_per_trade * commission_pct
                    trades.append({"type": "LONG_WIN", "pnl_pct": round(pnl*100,4), "exit": tp_p})
                    in_trade = False
            else:  # SHORT
                if float(df['High'].iloc[i]) >= sl_p:
                    pnl = (entry_p - sl_p) / entry_p
                    capital += capital * risk_per_trade * pnl - capital * risk_per_trade * commission_pct
                    trades.append({"type": "SHORT_LOSS", "pnl_pct": round(pnl*100,4), "exit": sl_p})
                    in_trade = False
                elif float(df['Low'].iloc[i]) <= tp_p:
                    pnl = (entry_p - tp_p) / entry_p
                    capital += capital * risk_per_trade * pnl - capital * risk_per_trade * commission_pct
                    trades.append({"type": "SHORT_WIN", "pnl_pct": round(pnl*100,4), "exit": tp_p})
                    in_trade = False
        else:
            # Ask strategy for signal
            try:
                signal = strategy_fn(df_slice, i)
            except Exception:
                signal = None

            if signal and signal.get("signal") in ("BUY", "SELL"):
                direction  = "LONG" if signal["signal"] == "BUY" else "SHORT"
                sl_pct     = signal.get("sl_pct", 0.02)
                tp_pct     = signal.get("tp_pct", 0.04)
                entry_p    = price
                sl_p       = price * (1 - sl_pct) if direction == "LONG" else price * (1 + sl_pct)
                tp_p       = price * (1 + tp_pct) if direction == "LONG" else price * (1 - tp_pct)
                in_trade   = True
                # Komisi entry
                capital   -= capital * risk_per_trade * commission_pct

        equity_curve.append(round(capital, 2))

    # ── Performance Metrics ──
    if not trades:
        return {"error": "Tidak ada trade yang terjadi dalam backtest. Periksa logika strategi."}

    pnls     = np.array([t['pnl_pct'] for t in trades])
    wins     = pnls[pnls > 0]
    losses   = np.abs(pnls[pnls < 0])
    win_rate = len(wins) / len(trades) if trades else 0

    eq  = np.array(equity_curve)
    mdd = float(((eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq)).min() * 100)

    total_return = (capital - initial_capital) / initial_capital * 100
    sharpe = (pnls.mean() / pnls.std()) * np.sqrt(252) if pnls.std() > 0 else 0
    profit_factor = float(np.sum(wins) / np.sum(losses)) if np.sum(losses) > 0 else 9999

    return {
        "backtest_summary": {
            "initial_capital"   : initial_capital,
            "final_capital"     : round(capital, 2),
            "total_return_pct"  : round(total_return, 4),
            "total_trades"      : len(trades),
            "win_rate_pct"      : round(win_rate * 100, 2),
            "avg_win_pct"       : round(float(np.mean(wins)), 4) if len(wins) else 0,
            "avg_loss_pct"      : round(-float(np.mean(losses)), 4) if len(losses) else 0,
            "profit_factor"     : round(profit_factor, 3),
            "sharpe_annualized" : round(sharpe, 3),
            "max_drawdown_pct"  : round(mdd, 2),
            "commission_pct"    : commission_pct * 100,
            "risk_per_trade_pct": risk_per_trade * 100,
        },
        "equity_curve": equity_curve,
        "trades"      : trades[-20:]  # Kirim 20 trade terakhir agar payload tidak terlalu besar
    }


# ─────────────────────────────────────────────────────────────────
#  5. ACCOUNT STATUS DASHBOARD
# ─────────────────────────────────────────────────────────────────

def get_satin_status() -> Dict:
    """Return full status Satin untuk dashboard."""
    check_and_reset_daily()

    balance = _risk_state["account_balance"]
    initial = _risk_state["initial_balance"]
    total_return = (balance - initial) / initial * 100

    all_trades = _risk_state["trade_log"]
    n_trades   = len(all_trades)
    n_wins     = sum(1 for t in all_trades if t.get("result") == "WIN")
    win_rate   = (n_wins / n_trades * 100) if n_trades > 0 else 0

    # Health indicator
    if _risk_state["is_locked"]:
        health = "LOCKED"
    elif _risk_state["daily_pnl_pct"] < -1.5:
        health = "DANGER"
    elif _risk_state["daily_pnl_pct"] < -0.5:
        health = "CAUTION"
    else:
        health = "HEALTHY"

    return {
        "satin_health"      : health,
        "account_balance"   : round(balance, 2),
        "initial_balance"   : initial,
        "total_return_pct"  : round(total_return, 4),
        "daily_pnl_pct"     : _risk_state["daily_pnl_pct"],
        "is_locked"         : _risk_state["is_locked"],
        "lock_reason"       : _risk_state["lock_reason"],
        "session_trades"    : len(_risk_state["session_trades"]),
        "total_trades_ever" : n_trades,
        "all_time_win_rate" : round(win_rate, 2),
        "rules"             : _risk_state["rules"],
        "last_5_trades"     : all_trades[-5:][::-1]
    }


def update_risk_rules(new_rules: Dict) -> Dict:
    """Update konfigurasi rules Satin secara dinamis."""
    global _risk_state
    _risk_state["rules"].update(new_rules)
    return {"status": "updated", "rules": _risk_state["rules"]}


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _detect_revenge_trading() -> Dict:
    """
    Deteksi pola revenge trading: banyak loss dalam waktu singkat.
    Trigger jika ada N losses dalam window M menit terakhir.
    """
    rules  = _risk_state["rules"]
    window = timedelta(minutes=rules["revenge_trade_window_min"])
    max_l  = rules["max_losses_in_window"]
    now    = datetime.now()

    recent_losses = [
        t for t in _risk_state["session_trades"]
        if t.get("result") == "LOSS"
        and (now - datetime.fromisoformat(t["timestamp"])) <= window
    ]

    detected = len(recent_losses) >= max_l

    return {
        "detected"     : detected,
        "recent_losses": len(recent_losses),
        "window_min"   : rules["revenge_trade_window_min"],
        "message"      : f"⚠️ {len(recent_losses)} losses dalam {rules['revenge_trade_window_min']} menit terakhir. Kemungkinan REVENGE TRADING." if detected else "OK"
    }