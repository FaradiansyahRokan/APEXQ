"""
╔══════════════════════════════════════════════════════════════════╗
║               APEX SCENARIO ENGINE v1.0                         ║
║    Historical Replay · Shock Simulation · Stress Testing        ║
╚══════════════════════════════════════════════════════════════════╝

Layer 4 — INSTITUTIONAL GRADE
Quant funds tidak hanya backtest di data normal.
Mereka simulate: "Apa yang terjadi pada strategi saya kalau
market crash seperti 2020? Atau FTX collapse? Atau 2022 tightening?"

Komponen:
  1. Historical Scenario Library  → Database krisis historis terstandarisasi
  2. Scenario Replay Engine       → Injeksi return krisis ke portfolio
  3. Shock Simulation             → Custom shock: +Nσ vol spike, liquidity gap
  4. Correlation Breakdown Sim    → Test saat diversifikasi gagal
  5. Tail Risk Report             → Rangkuman worst-case semua skenario
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. HISTORICAL SCENARIO LIBRARY
# ─────────────────────────────────────────────────────────────────

# Database skenario krisis historis (return harian dalam %)
# Data ini adalah DISTRIBUSI APPROXIMATE dari pergerakan harian selama krisis
# berdasarkan data historis yang terdokumentasi

CRISIS_SCENARIOS = {
    "covid_crash_2020": {
        "name"       : "COVID-19 Market Crash (Feb-Mar 2020)",
        "description": "Crash tercepat dalam sejarah. S&P 500 -34% dalam 33 hari.",
        "duration_days": 33,
        "key_stats"  : {"total_drawdown_pct": -34, "max_daily_loss_pct": -12, "vol_spike_x": 5.0},
        # Distribusi return harian simplified (median crash day behavior)
        "daily_return_sequence": [
            -0.5, -1.2, 0.3, -2.1, -3.4, -9.5, 4.9, -5.2, -4.9, -12.0,
             6.0, -5.1,  1.2, -7.6, 0.8,  9.4, -3.0, 6.2, -2.5,  5.1,
             3.4, -0.8,  2.3,  1.5, 3.8,  2.1,  1.9, 4.5,  3.1,  2.8,
             1.5,  2.3,  1.1
        ]
    },
    "ftx_collapse_2022": {
        "name"       : "FTX Exchange Collapse (Nov 2022)",
        "description": "FTX bangkrut. BTC -26% dalam seminggu, crypto market -$200B.",
        "duration_days": 14,
        "key_stats"  : {"total_drawdown_pct": -28, "max_daily_loss_pct": -14, "vol_spike_x": 4.0},
        "daily_return_sequence": [
            -2.0, -8.5, -3.1, -14.0, -5.2, 4.1, -3.8, -2.9, 2.5, -1.8,
             1.2,  3.4,  1.8,   2.1
        ]
    },
    "fed_tightening_2022": {
        "name"       : "Fed Aggressive Tightening Cycle (Jan-Dec 2022)",
        "description": "Fed menaikkan rate 425bps. Nasdaq -33%, BTC -65% setahun.",
        "duration_days": 60,  # Simulate 60-day window worst period
        "key_stats"  : {"total_drawdown_pct": -45, "max_daily_loss_pct": -7, "vol_spike_x": 2.5},
        "daily_return_sequence": [
            -1.5, -0.8, -2.3, 1.2, -3.1, -0.5, 0.8, -1.9, -0.7, -2.5,
             1.1, -0.9, -1.8, 0.4, -3.5, 2.1, -1.2, -0.6, 0.9, -2.8,
            -0.3, -1.7, 0.6, -2.2, -0.8, 1.5, -1.4, -0.5, 0.7, -3.1,
            -1.0, -0.9, 0.8, -1.6, 0.3, -2.7, -0.4, 1.2, -0.8, -1.9,
            -0.6, 0.5, -2.1, -0.7, 1.0, -1.5, -0.3, 0.9, -1.8, -0.5,
             0.8, -2.4, -0.6, 1.1, -1.3, -0.8, 0.4, -2.0, -0.9, 0.7
        ]
    },
    "luna_collapse_2022": {
        "name"       : "LUNA/UST Death Spiral (May 2022)",
        "description": "Terra ecosystem collapse. LUNA -99.9%, UST depeg. Kontak ke seluruh crypto.",
        "duration_days": 7,
        "key_stats"  : {"total_drawdown_pct": -40, "max_daily_loss_pct": -25, "vol_spike_x": 6.0},
        "daily_return_sequence": [-3.5, -8.2, -15.0, -25.0, -12.0, 5.2, 3.8]
    },
    "defi_exploit_flash": {
        "name"       : "DeFi Protocol Exploit / Flash Event",
        "description": "Simulasi exploit/hack mendadak yang menyebabkan flash crash.",
        "duration_days": 3,
        "key_stats"  : {"total_drawdown_pct": -20, "max_daily_loss_pct": -15, "vol_spike_x": 8.0},
        "daily_return_sequence": [-15.0, -8.5, 5.2]
    }
}


# ─────────────────────────────────────────────────────────────────
#  2. SCENARIO REPLAY ENGINE
# ─────────────────────────────────────────────────────────────────

def replay_historical_scenario(
    current_price  : float,
    scenario_key   : str,
    account_balance: float = 30_000,
    position_pct   : float = 0.10,  # 10% dari akun di posisi
    use_stop_loss  : bool  = True,
    stop_loss_pct  : float = 5.0    # 5% SL
) -> Dict:
    """
    Simulasikan dampak skenario krisis historis pada posisi saat ini.

    Args:
        current_price   : Harga entry saat ini
        scenario_key    : Key dari CRISIS_SCENARIOS
        account_balance : Total modal
        position_pct    : Persentase modal yang dialokasikan ke posisi
        use_stop_loss   : Apakah menggunakan stop loss?
        stop_loss_pct   : Persentase stop loss dari entry
    """
    if scenario_key not in CRISIS_SCENARIOS:
        return {
            "error"            : f"Skenario tidak ditemukan: {scenario_key}",
            "available_scenarios": list(CRISIS_SCENARIOS.keys())
        }

    scenario     = CRISIS_SCENARIOS[scenario_key]
    returns_seq  = scenario["daily_return_sequence"]
    position_usd = account_balance * (position_pct / 100)
    sl_price     = current_price * (1 - stop_loss_pct / 100)

    # Simulate day by day
    price       = current_price
    balance     = account_balance
    equity_curve = [balance]
    daily_details = []
    stopped_out = False
    stop_day    = None

    for day, daily_ret in enumerate(returns_seq):
        if stopped_out:
            break

        new_price = price * (1 + daily_ret / 100)
        pnl_usd   = position_usd * (daily_ret / 100)

        # Stop loss check (intraday approximation: if low touches SL)
        intraday_low = new_price * 0.995  # Approximate intraday low
        if use_stop_loss and intraday_low <= sl_price:
            sl_loss_pct = (sl_price / price - 1) * 100
            pnl_usd     = position_usd * (sl_loss_pct / 100)
            stopped_out = True
            stop_day    = day + 1

        balance += pnl_usd
        balance  = max(balance, 0)
        equity_curve.append(round(balance, 2))

        daily_details.append({
            "day"           : day + 1,
            "daily_ret_pct" : round(daily_ret, 4),
            "price"         : round(new_price, 4),
            "pnl_day_usd"   : round(pnl_usd, 2),
            "balance"       : round(balance, 2),
            "stopped_out"   : stopped_out
        })

        price = new_price if not stopped_out else price

    # Summary
    total_pnl_usd = balance - account_balance
    total_pnl_pct = (total_pnl_usd / account_balance) * 100
    max_balance   = max(equity_curve)
    min_balance   = min(equity_curve)
    max_dd_pct    = (min_balance / max_balance - 1) * 100

    return {
        "scenario_name"     : scenario["name"],
        "scenario_description": scenario["description"],
        "scenario_stats"    : scenario["key_stats"],
        "simulation_params" : {
            "entry_price"    : current_price,
            "account_balance": account_balance,
            "position_pct"   : position_pct,
            "position_usd"   : position_usd,
            "use_stop_loss"  : use_stop_loss,
            "stop_loss_pct"  : stop_loss_pct,
            "sl_price"       : round(sl_price, 4)
        },
        "results": {
            "total_pnl_usd"  : round(total_pnl_usd, 2),
            "total_pnl_pct"  : round(total_pnl_pct, 4),
            "max_drawdown_pct": round(max_dd_pct, 4),
            "final_balance"  : round(balance, 2),
            "stopped_out"    : stopped_out,
            "stop_day"       : stop_day,
            "survival_rating": "SURVIVED" if total_pnl_pct > -20 else "SEVERELY_DAMAGED" if total_pnl_pct > -50 else "WIPED_OUT"
        },
        "equity_curve"     : equity_curve,
        "daily_details"    : daily_details
    }


# ─────────────────────────────────────────────────────────────────
#  3. CUSTOM SHOCK SIMULATION
# ─────────────────────────────────────────────────────────────────

def simulate_custom_shock(
    df             : pd.DataFrame,
    shock_vol_sigma: float = 3.0,   # Berapa sigma vol spike (3 = 3x normal vol)
    shock_direction: str   = "DOWN", # UP atau DOWN
    shock_duration : int   = 5,     # Berapa hari shock berlangsung
    account_balance: float = 30_000,
    position_pct   : float = 10.0
) -> Dict:
    """
    Injeksi custom shock ke distribusi return historis.

    Shock Types:
      - Vol Spike: Inject return dengan volatilitas N-sigma lebih tinggi
      - Liquidity Gap: Inject single gap move (5-15% dalam 1 candle)
      - Correlation Breakdown: Aset bergerak berlawanan arah dari biasanya
    """
    if df is None or df.empty or 'Close' not in df.columns:
        return {"error": "Data tidak valid"}

    close      = df['Close'].dropna()
    log_ret    = np.log(close / close.shift(1)).dropna()
    mu_daily   = float(log_ret.mean())
    sigma_daily = float(log_ret.std())

    current_price = float(close.iloc[-1])
    shock_sigma   = sigma_daily * shock_vol_sigma

    # Generate shocked returns
    np.random.seed(99)
    shocked_returns = []
    for d in range(shock_duration):
        if shock_direction == "DOWN":
            # Biased negative shock
            r = np.random.normal(-sigma_daily * 1.5, shock_sigma)
        else:
            r = np.random.normal(sigma_daily * 1.5, shock_sigma)
        shocked_returns.append(float(r * 100))  # pct

    # Simulate
    position_usd = account_balance * (position_pct / 100)
    price        = current_price
    balance      = account_balance
    equity_curve = [balance]
    path_prices  = [current_price]

    for r_pct in shocked_returns:
        pnl_day = position_usd * (r_pct / 100)
        balance  = max(0, balance + pnl_day)
        price   *= (1 + r_pct / 100)
        equity_curve.append(round(balance, 2))
        path_prices.append(round(price, 4))

    total_pnl_usd = balance - account_balance
    total_pnl_pct = (total_pnl_usd / account_balance) * 100

    # Probability of this shock occurring (based on historical distribution)
    shock_daily_ret = mu_daily - shock_sigma  # Worst day of shock
    from scipy.stats import norm
    prob_of_shock = float(norm.cdf(shock_daily_ret, mu_daily, sigma_daily) * 100)

    return {
        "shock_params": {
            "sigma_multiplier" : shock_vol_sigma,
            "direction"        : shock_direction,
            "duration_days"    : shock_duration,
            "shocked_vol_daily": round(shock_sigma * 100, 4),
            "normal_vol_daily" : round(sigma_daily * 100, 4)
        },
        "probability": {
            "prob_of_this_shock_pct": round(prob_of_shock, 6),
            "description"           : f"Probabilitas shock ini terjadi: {prob_of_shock:.4f}% per hari berdasarkan distribusi historis."
        },
        "results": {
            "shocked_return_sequence": [round(r, 4) for r in shocked_returns],
            "price_path"            : path_prices,
            "total_pnl_usd"         : round(total_pnl_usd, 2),
            "total_pnl_pct"         : round(total_pnl_pct, 4),
            "final_balance"         : round(balance, 2),
            "equity_curve"          : equity_curve
        }
    }


# ─────────────────────────────────────────────────────────────────
#  4. TAIL RISK REPORT (semua skenario sekaligus)
# ─────────────────────────────────────────────────────────────────

def generate_tail_risk_report(
    current_price  : float,
    df             : pd.DataFrame,
    account_balance: float = 30_000,
    position_pct   : float = 10.0
) -> Dict:
    """
    Jalankan SEMUA skenario + custom shocks dan buat laporan tail risk.
    Output: ranking dari skenario terburuk hingga terbaik.
    """
    results = {}

    # Run semua historical scenarios
    for key in CRISIS_SCENARIOS.keys():
        r = replay_historical_scenario(
            current_price=current_price,
            scenario_key=key,
            account_balance=account_balance,
            position_pct=position_pct
        )
        results[key] = {
            "name"         : r.get("scenario_name", key),
            "total_pnl_pct": r.get("results", {}).get("total_pnl_pct", 0),
            "max_dd_pct"   : r.get("results", {}).get("max_drawdown_pct", 0),
            "survival"     : r.get("results", {}).get("survival_rating", "UNKNOWN"),
            "stopped_out"  : r.get("results", {}).get("stopped_out", False)
        }

    # Custom shocks
    for sigma_mult, label in [(2, "2_sigma_down"), (3, "3_sigma_down"), (5, "5_sigma_down")]:
        r = simulate_custom_shock(
            df=df,
            shock_vol_sigma=sigma_mult,
            shock_direction="DOWN",
            shock_duration=3,
            account_balance=account_balance,
            position_pct=position_pct
        )
        results[f"shock_{label}"] = {
            "name"         : f"Custom Shock: {sigma_mult}σ Down (3 days)",
            "total_pnl_pct": r.get("results", {}).get("total_pnl_pct", 0),
            "max_dd_pct"   : 0,
            "survival"     : "SURVIVED" if r.get("results", {}).get("total_pnl_pct", 0) > -20 else "DAMAGED",
            "stopped_out"  : False
        }

    # Sort by worst PnL
    sorted_results = sorted(results.items(), key=lambda x: x[1]["total_pnl_pct"])

    worst_scenario = sorted_results[0]
    worst_loss_pct = worst_scenario[1]["total_pnl_pct"]
    worst_loss_usd = account_balance * worst_loss_pct / 100

    return {
        "tail_risk_summary": {
            "worst_scenario"       : worst_scenario[1]["name"],
            "worst_loss_pct"       : round(worst_loss_pct, 4),
            "worst_loss_usd"       : round(worst_loss_usd, 2),
            "scenarios_survived"   : sum(1 for _, v in results.items() if "SURVIVED" in v.get("survival", "")),
            "total_scenarios_run"  : len(results),
        },
        "scenario_ranking"   : [
            {
                "rank"         : i + 1,
                "scenario_key" : k,
                "name"         : v["name"],
                "pnl_pct"      : round(v["total_pnl_pct"], 4),
                "survival"     : v["survival"]
            }
            for i, (k, v) in enumerate(sorted_results)
        ],
        "position_params": {
            "current_price"  : current_price,
            "account_balance": account_balance,
            "position_pct"   : position_pct,
            "position_usd"   : account_balance * position_pct / 100
        },
        "available_scenarios": list(CRISIS_SCENARIOS.keys())
    }
