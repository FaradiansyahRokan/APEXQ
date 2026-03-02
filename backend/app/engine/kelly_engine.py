"""
╔══════════════════════════════════════════════════════════════╗
║              APEX KELLY CRITERION ENGINE                     ║
║   Optimal Position Sizing via Kelly & Fractional Kelly       ║
╚══════════════════════════════════════════════════════════════╝

Rumus Inti:
  Kelly % = W - [(1 - W) / R]
  Dimana: W = Win Rate, R = Reward-to-Risk Ratio

Fractional Kelly (lebih aman untuk futures):
  F* = (Full Kelly) * fraction  →  rekomendasi 0.25 (Quarter Kelly)
"""

import numpy as np
from scipy.stats import norm, t as t_dist
from typing import List, Dict, Optional
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. KELLY CRITERION CORE
# ─────────────────────────────────────────────────────────────────

def calculate_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.25,
    account_balance: float = 30_000,
    max_risk_pct: float = 2.0
) -> Dict:
    """
    Hitung posisi optimal berdasarkan Kelly Criterion.

    Args:
        win_rate        : Probabilitas menang (0.0 - 1.0)
        avg_win         : Rata-rata profit per trade (dalam %, e.g. 2.5 = 2.5%)
        avg_loss        : Rata-rata loss per trade (dalam %, e.g. 1.0 = 1.0%)
        fraction        : Fractional Kelly safety factor (default 0.25 = Quarter Kelly)
        account_balance : Total modal (default $30,000)
        max_risk_pct    : Cap risiko per trade yang diizinkan (%)
    """
    if not (0 < win_rate < 1):
        return {"error": "Win rate harus antara 0 dan 1 (exclusive)"}
    if avg_loss <= 0:
        return {"error": "avg_loss harus > 0"}

    loss_rate = 1.0 - win_rate
    reward_risk_ratio = avg_win / avg_loss

    # ── Full Kelly: K% = W - (L / R) ──
    full_kelly_pct = win_rate - (loss_rate / reward_risk_ratio)

    # ── Fractional Kelly ──
    fractional_kelly_pct = full_kelly_pct * fraction

    # ── Safety Cap ──
    safe_kelly_pct = min(max(fractional_kelly_pct, 0), max_risk_pct / 100)

    dollar_risk      = account_balance * safe_kelly_pct
    dollar_full_kell = account_balance * max(full_kelly_pct, 0)

    # Expected Value per Trade
    ev_per_trade = (win_rate * avg_win) - (loss_rate * avg_loss)

    # Edge Quality
    if full_kelly_pct < 0:
        verdict      = "❌ NEGATIVE EDGE — Jangan trade setup ini. Expected Value negatif."
        edge_quality = "NO_EDGE"
    elif full_kelly_pct < 0.05:
        verdict      = "⚠️  EDGE LEMAH — Setup marginal, kurangi size drastis."
        edge_quality = "WEAK"
    elif full_kelly_pct < 0.15:
        verdict      = "✅ EDGE SOLID — Gunakan Quarter Kelly untuk keamanan."
        edge_quality = "MODERATE"
    else:
        verdict      = "🔥 STRONG EDGE — Kelly tinggi, tetap pakai Fractional Kelly."
        edge_quality = "STRONG"

    return {
        "win_rate_pct"           : round(win_rate * 100, 2),
        "loss_rate_pct"          : round(loss_rate * 100, 2),
        "avg_win_pct"            : round(avg_win, 4),
        "avg_loss_pct"           : round(avg_loss, 4),
        "reward_risk_ratio"      : round(reward_risk_ratio, 3),
        "expected_value_pct"     : round(ev_per_trade, 4),
        "full_kelly_pct"         : round(full_kelly_pct * 100, 4),
        "fractional_kelly_pct"   : round(fractional_kelly_pct * 100, 4),
        "safe_kelly_pct"         : round(safe_kelly_pct * 100, 4),
        "fraction_used"          : fraction,
        "dollar_risk_safe"       : round(dollar_risk, 2),
        "dollar_risk_full_kelly" : round(dollar_full_kell, 2),
        "account_balance"        : account_balance,
        "max_risk_pct_cap"       : max_risk_pct,
        "edge_quality"           : edge_quality,
        "verdict"                : verdict,
        "ruin_probability_pct"   : _estimate_ruin_probability(win_rate, reward_risk_ratio, safe_kelly_pct)
    }


# ─────────────────────────────────────────────────────────────────
#  2. KELLY FROM TRADE HISTORY (AUTO-COMPUTE)
# ─────────────────────────────────────────────────────────────────

def kelly_from_trade_history(
    trades: List[Dict],
    account_balance: float = 30_000,
    fraction: float = 0.25,
    confidence_level: float = 0.95
) -> Dict:
    """
    Hitung Kelly otomatis dari riwayat trade.

    Args:
        trades: List of dicts → [{"pnl_pct": 2.5}, {"pnl_pct": -1.0}, ...]
    """
    if not trades or len(trades) < 5:
        return {"error": "Minimal 5 data trade diperlukan"}

    pnls    = np.array([t.get('pnl_pct', 0) for t in trades], dtype=float)
    wins    = pnls[pnls > 0]
    losses  = np.abs(pnls[pnls < 0])
    n_total = len(pnls)
    n_wins  = len(wins)
    n_loss  = len(losses)

    if n_wins == 0 or n_loss == 0:
        return {"error": "Data win/loss tidak lengkap"}

    win_rate = n_wins / n_total
    avg_win  = float(np.mean(wins))
    avg_loss = float(np.mean(losses))

    # Confidence Interval Win Rate (T-distribution)
    se_wr      = np.sqrt((win_rate * (1 - win_rate)) / n_total)
    ci_margin  = t_dist.ppf((1 + confidence_level) / 2, df=n_total - 1) * se_wr

    kelly_result = calculate_kelly(
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        fraction=fraction,
        account_balance=account_balance
    )

    gross_profit  = float(np.sum(wins))
    gross_loss    = float(np.sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 9999
    sharpe        = (pnls.mean() / pnls.std()) * np.sqrt(252) if pnls.std() > 0 else 0

    max_win_streak, max_loss_streak = _calculate_streaks(pnls)

    trade_stats = {
        "total_trades"    : n_total,
        "winning_trades"  : int(n_wins),
        "losing_trades"   : int(n_loss),
        "win_rate_pct"    : round(win_rate * 100, 2),
        "win_rate_ci_95"  : {
            "lower": round(max(0, (win_rate - ci_margin) * 100), 2),
            "upper": round(min(100, (win_rate + ci_margin) * 100), 2)
        },
        "avg_win_pct"     : round(avg_win, 4),
        "avg_loss_pct"    : round(avg_loss, 4),
        "profit_factor"   : round(profit_factor, 3),
        "sharpe_annualized": round(sharpe, 3),
        "max_win_streak"  : max_win_streak,
        "max_loss_streak" : max_loss_streak,
        "total_pnl_pct"   : round(float(np.sum(pnls)), 4),
        "best_trade_pct"  : round(float(np.max(wins)), 4) if len(wins) else 0,
        "worst_trade_pct" : round(-float(np.max(losses)), 4) if len(losses) else 0,
    }

    return {**kelly_result, "trade_stats": trade_stats}


# ─────────────────────────────────────────────────────────────────
#  3. DYNAMIC POSITION SIZER (BERBASIS STOP LOSS)
# ─────────────────────────────────────────────────────────────────

def calculate_position_size(
    entry_price    : float,
    stop_loss_price: float,
    account_balance: float,
    risk_pct       : float,
    leverage       : float = 1.0
) -> Dict:
    """
    Hitung lot/unit yang harus dibuka berdasarkan Stop Loss jarak nyata.

    Formula: Units = (Account × Risk%) / (|Entry − SL| × Leverage)
    """
    if entry_price <= 0 or stop_loss_price <= 0:
        return {"error": "Harga tidak valid"}

    risk_per_unit = abs(entry_price - stop_loss_price) * leverage
    if risk_per_unit == 0:
        return {"error": "Entry dan SL tidak boleh sama"}

    dollar_risk    = account_balance * (risk_pct / 100)
    units          = dollar_risk / risk_per_unit
    position_value = units * entry_price
    direction      = "LONG" if stop_loss_price < entry_price else "SHORT"

    # Auto TP levels (R-multiple)
    sl_dist = abs(entry_price - stop_loss_price)
    if direction == "LONG":
        rr_targets = {
            "1R_TP": round(entry_price + sl_dist, 6),
            "2R_TP": round(entry_price + 2 * sl_dist, 6),
            "3R_TP": round(entry_price + 3 * sl_dist, 6),
        }
    else:
        rr_targets = {
            "1R_TP": round(entry_price - sl_dist, 6),
            "2R_TP": round(entry_price - 2 * sl_dist, 6),
            "3R_TP": round(entry_price - 3 * sl_dist, 6),
        }

    return {
        "direction"              : direction,
        "entry_price"            : entry_price,
        "stop_loss_price"        : stop_loss_price,
        "sl_distance_pct"        : round((sl_dist / entry_price) * 100, 4),
        "dollar_risk"            : round(dollar_risk, 2),
        "recommended_units"      : round(units, 6),
        "position_value_usd"     : round(position_value, 2),
        "position_pct_of_account": round((position_value / account_balance) * 100, 2),
        "leverage"               : leverage,
        "margin_required_usd"    : round(position_value / leverage, 2),
        "rr_targets"             : rr_targets,
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _estimate_ruin_probability(win_rate: float, rr: float, kelly_pct: float) -> float:
    """
    Estimasi P(Ruin) menggunakan Gambler's Ruin approximation.
    P(ruin) = ((1-p)/p)^k  dimana k = initial capital in betting units.
    """
    try:
        q = 1 - win_rate
        if kelly_pct <= 0 or win_rate >= 1:
            return 99.99
        k = 1.0 / kelly_pct
        ruin = (q / win_rate) ** k
        return round(min(ruin * 100, 99.99), 4)
    except Exception:
        return 99.99


def _calculate_streaks(pnls: np.ndarray):
    """Hitung streak win/loss terpanjang dalam riwayat trade."""
    max_win = max_loss = cur_win = cur_loss = 0
    for p in pnls:
        if p > 0:
            cur_win  += 1; cur_loss = 0
            max_win   = max(max_win, cur_win)
        elif p < 0:
            cur_loss += 1; cur_win  = 0
            max_loss  = max(max_loss, cur_loss)
        else:
            cur_win = cur_loss = 0
    return max_win, max_loss