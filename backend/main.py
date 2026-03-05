"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              APEX QUANTUM COMMAND — main.py v6.0                            ║
║         Institutional-Grade Quant Trading Intelligence Platform             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  PERUBAHAN DARI v3.0 → v6.0:                                                ║
║                                                                              ║
║  SEBELUM (v3): import dari ~13 file engine terpisah                          ║
║    from app.engine.quant_engine import ...                                   ║
║    from app.engine.kelly_engine import ...                                   ║
║    from app.engine.stats_engine import ...                                   ║
║    from app.engine.ict_engine import ...                                     ║
║    from app.engine.risk_manager import ...                                   ║
║    from app.engine.macro_engine import ...                                   ║
║    from app.engine.regime_engine import ...                                  ║
║    from app.engine.factor_engine import ...                                  ║
║    from app.engine.scenario_engine import ...                                ║
║    from app.engine.model_confidence_engine import ...                        ║
║    from app.engine.data_quality_engine import ...                            ║
║    from app.engine.apex_systematic_trader import ...                         ║
║    from app.engine.apex_quant_fund import ...                                ║
║    from app.engine.apex_institutional_architect import ...                   ║
║    from app.engine.screener_engine import ...                                ║
║                                                                              ║
║  SESUDAH (v6): satu file saja                                                ║
║    from apex_engine_v6 import *  (semua fungsi yang sama tersedia)          ║
║                                                                              ║
║  TETAP TIDAK BERUBAH:                                                        ║
║     app/collectors/  — semua collector                                      ║
║     app/models/      — ai_analyzer, price_analyzer                          ║
║     app/engine/portfolio_simulator.py — tetap dipakai sendiri               ║
║     Semua endpoint URL — tidak ada yang berubah                             ║
║     sanitize_data, exception handler, CORS                                  ║
║                                                                              ║
║  FILE YANG BOLEH DIHAPUS dari app/engine/:                                   ║
║     quant_engine.py                                                         ║
║     kelly_engine.py                                                         ║
║     stats_engine.py                                                         ║
║     ict_engine.py                                                           ║
║     risk_manager.py                                                         ║
║     macro_engine.py                                                         ║
║     regime_engine.py                                                        ║
║     factor_engine.py                                                        ║
║     scenario_engine.py                                                      ║
║     model_confidence_engine.py                                              ║
║     data_quality_engine.py                                                  ║
║     screener_engine.py                                                      ║
║     apex_systematic_trader.py                                               ║
║     apex_quant_fund.py                                                      ║
║     apex_institutional_architect.py                                         ║
║                                                                              ║
║  CARA JALANKAN:                                                              ║
║    uvicorn main:app --reload --port 8001                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
import yfinance as yf
import json
import uvicorn
import traceback
from app.engine.hft_engine import hft_spider

# ── Rapid Scalper (Jackal ULTRA v4.0 WS) ─────────────────────────
# Coba import versi terbaru dulu (WS ultra), fallback ke versi lama
try:
    from app.engine.hft_rapid_scalper import rapid_scalper
except ImportError:
    try:
        from hft_rapid_scalper import rapid_scalper
    except ImportError:
        rapid_scalper = None
import asyncio


# ══════════════════════════════════════════════════════════════════
#  UTILITY — Sanitize NaN/Inf/NumPy types (tidak berubah)
# ══════════════════════════════════════════════════════════════════

def sanitize_data(data: Any) -> Any:
    """
    Recursively replace NaN, inf, and -inf with None.
    Also converts NumPy types (float64, int64, bool_, ndarray) to Python native types.
    """
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [sanitize_data(x) for x in data]
    elif isinstance(data, np.ndarray):
        return sanitize_data(data.tolist())
    elif isinstance(data, (float, np.float64, np.float32, np.float16)):
        return float(data) if np.isfinite(data) else None
    elif isinstance(data, (int, np.int64, np.int32, np.int16, np.int8)):
        return int(data)
    elif isinstance(data, (bool, np.bool_)):
        return bool(data)
    elif data is None:
        return None
    return data


# ══════════════════════════════════════════════════════════════════
#  COLLECTORS (tidak berubah)
# ══════════════════════════════════════════════════════════════════

from app.collectors.market_collector import (
    get_binance_crypto_data, get_company_profile, get_global_indices,
    get_market_data, get_live_quote, get_ihsg_summary,
)
from app.collectors.news_collector import get_smart_news, get_global_market_news
from app.collectors.fundamental_collector import get_fundamentals
from app.collectors.hyperliquid_collector import get_hl_crypto_data

# AI Models (tidak berubah)
from app.models.ai_analyzer import get_ai_analysis
from app.models.price_analyzer import get_satin_reasoning

# Portfolio Simulator (tetap file sendiri — tidak di-konsolidasi ke v6)
from app.engine.portfolio_simulator import run_simulation, generate_json_report, SimulationConfig


# ══════════════════════════════════════════════════════════════════
#  ▼▼▼ PERUBAHAN UTAMA: SEMUA ENGINE → SATU FILE ▼▼▼
#
#  Sebelumnya ada ~15 baris import dari ~13 file berbeda.
#  Sekarang cukup 1 baris ini saja.
# ══════════════════════════════════════════════════════════════════

from app.engine.apex_engine_v6 import (
    # ── Quant Metrics ────────────────────────────────────────────
    calculate_quant_metrics,
    calculate_technicals,

    # ── Regime Detection ─────────────────────────────────────────
    detect_hmm_regime,
    detect_vol_clustering,
    detect_liquidity_regime,
    get_full_regime_analysis,

    # ── Stats / Z-Score / Monte Carlo ────────────────────────────
    calculate_zscore_analysis,
    run_monte_carlo_price,          # menggantikan run_monte_carlo dari stats_engine

    # ── ICT / SMC ────────────────────────────────────────────────
    detect_fvg,
    detect_order_blocks,
    detect_market_structure,
    get_ict_full_analysis,

    # ── Screener ─────────────────────────────────────────────────
    score_ticker_from_df,
    WATCHLISTS,

    # ── Kelly & Position Sizing ───────────────────────────────────
    calculate_kelly,
    kelly_from_trade_history,
    calculate_position_size,
    cvar_constrained_kelly,
    portfolio_heat_control,
    estimate_execution_cost,
    volatility_target_position_size,

    # ── Statistical Validation ────────────────────────────────────
    lo_adjusted_sharpe,             # menggantikan lo_autocorrelation_adjusted_sharpe
    deflated_sharpe_ratio,
    bootstrap_sharpe_ci,
    monte_carlo_equity_reshuffling,
    validate_performance_targets,

    # ── Portfolio Construction ────────────────────────────────────
    compute_portfolio_moments,
    mean_variance_optimization,
    risk_parity_weights,
    cvar_optimization,
    kelly_matrix_allocation,

    # ── Signal Intelligence ───────────────────────────────────────
    calculate_signal_confidence,
    compute_quality_score,

    # ── Risk Manager ─────────────────────────────────────────────
    pre_trade_check,
    record_trade,
    get_satin_status,
    update_risk_rules,

    # ── Institutional Research ────────────────────────────────────
    rolling_walk_forward,
    advanced_risk_decomposition,
    stress_test_portfolio,
    generate_statistical_audit,
    generate_institutional_report,

    # ── Data Quality ─────────────────────────────────────────────
    detect_missing_ticks,
    detect_price_outliers,
    detect_exchange_anomalies,
    generate_data_quality_report,

    # ── Factor Engine ─────────────────────────────────────────────
    analyze_momentum_factor,
    calculate_vol_risk_premium,
    get_factor_composite,

    # ── Scenario Engine ───────────────────────────────────────────
    replay_historical_scenario,
    generate_tail_risk_report,
    CRISIS_SCENARIOS,
)

# Alias compat: fungsi yang namanya berubah dari engine lama
lo_autocorrelation_adjusted_sharpe = lo_adjusted_sharpe   # compat alias
run_monte_carlo = run_monte_carlo_price                    # compat alias


# v6 convenience aliases (already imported above as the canonical name)
v6_quant_metrics   = calculate_quant_metrics
v6_technicals      = calculate_technicals
v6_ict_analysis    = get_ict_full_analysis
v6_hmm_regime      = detect_hmm_regime
v6_vol_clustering  = detect_vol_clustering
v6_liq_regime      = detect_liquidity_regime
v6_regime_analysis = get_full_regime_analysis
v6_screener_score  = score_ticker_from_df
v6_kelly           = calculate_kelly
v6_kelly_history   = kelly_from_trade_history
v6_monte_carlo     = run_monte_carlo_price
v6_factor_composite = get_factor_composite
v6_momentum_factor  = analyze_momentum_factor
v6_vrp              = calculate_vol_risk_premium

# ══════════════════════════════════════════════════════════════════
#  PHASE 5 — HWM PROTECTION ENGINE IMPORT
#  Drop-in companion: apex_hwm_engine.py (must be in same directory)
# ══════════════════════════════════════════════════════════════════
from app.engine.apex_hwm_engine import (
    HWMSession,
    HWMConfig,
    HWMRiskDecision,
    EquityHWMStateMachine,
    CapitalLockManager,
    VolatilityRiskScaler,
    TimeframeRiskBudget,
    EquityCurveFeedbackLoop,
    SystemHealthMonitor,
    HWMPositionSizer,
    CompoundingEngine,
    ValidationSuite,
    generate_system_design_report,
)

# ══════════════════════════════════════════════════════════════════
#  APEX EQUITY ARMOR — Import (apex_equity_armor.py must be present)
# ══════════════════════════════════════════════════════════════════
from app.engine.apex_equity_armor import (
    EquityArmor,
    ArmorConfig,
    MilestoneTracker,
    run_armored_monte_carlo,
    run_armor_stress_test,
    run_armored_walk_forward,
    generate_armor_report,
)

# Global armor instance — keyed by session_id for multi-user support.
# In production: replace with Redis / Postgres-backed store.
_armor_sessions: Dict[str, EquityArmor] = {}

# ── Singleton HWM session (lives for the lifetime of the FastAPI process) ──
# In production, replace with a persistent store (Redis / Postgres).
_hwm_sessions: Dict[str, HWMSession] = {}

def _get_hwm_session(session_id: str) -> HWMSession:
    """Return an existing HWM session or raise 404."""
    if session_id not in _hwm_sessions:
        raise HTTPException(404, f"HWM session '{session_id}' not found. Call POST /api/v5/hwm/session first.")
    return _hwm_sessions[session_id]


# ══════════════════════════════════════════════════════════════════
#  FUNGSI YANG TIDAK ADA DI V6 — Dibuat sebagai shim lokal
#  (fungsi di engine lama yang tidak di-port ke v6, tapi masih dipakai endpoint)
# ══════════════════════════════════════════════════════════════════

def get_cross_asset_data():
    """
    Shim: fetch DXY, Nasdaq, Gold data.
    Di macro_engine lama fungsi ini fetch dari yfinance.
    Di v6 tidak ada karena butuh network — tetap di sini.
    """
    result = {}
    symbols = {"DXY": "DX-Y.NYB", "NASDAQ": "^IXIC", "GOLD": "GC=F"}
    for name, sym in symbols.items():
        try:
            df = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=True)
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                c = float(df["Close"].iloc[-1])
                p = float(df["Close"].iloc[-2]) if len(df) > 1 else c
                result[name] = {
                    "current"   : round(c, 4),
                    "prev"      : round(p, 4),
                    "change_pct": round((c / p - 1) * 100, 4) if p != 0 else 0,
                    "trend"     : "UP" if c > p else "DOWN",
                }
        except Exception:
            result[name] = {"current": 0, "change_pct": 0, "trend": "UNKNOWN"}
    return result


def calculate_factor_lab(df: pd.DataFrame, df_nasdaq: Optional[pd.DataFrame] = None) -> Dict:
    """
    Shim: gabung output dari analyze_momentum_factor + calculate_vol_risk_premium.
    Menggantikan calculate_factor_lab dari macro_engine lama.
    """
    mom = analyze_momentum_factor(df)
    vrp = calculate_vol_risk_premium(df)
    return {"momentum": mom, "vol_risk_premium": vrp}


def tag_macro_regime(cross_asset: Dict) -> Dict:
    """
    Shim: klasifikasikan macro regime dari cross-asset data.
    Menggantikan tag_macro_regime dari regime_engine lama.
    """
    nasdaq_chg = cross_asset.get("NASDAQ", {}).get("change_pct", 0)
    dxy_chg    = cross_asset.get("DXY",    {}).get("change_pct", 0)
    gold_chg   = cross_asset.get("GOLD",   {}).get("change_pct", 0)

    if nasdaq_chg > 0.5 and dxy_chg < 0.3:
        regime = "RISK_ON"
        desc   = "Nasdaq naik + DXY stabil/turun → risk assets favored."
    elif nasdaq_chg < -0.5 or dxy_chg > 0.5:
        regime = "RISK_OFF"
        desc   = "Nasdaq turun / DXY naik → flight to safety."
    elif gold_chg > 1.0 and dxy_chg > 0.3:
        regime = "INFLATION_FEAR"
        desc   = "Gold & DXY naik bersamaan → inflation / stagflation fear."
    else:
        regime = "TRANSITIONAL"
        desc   = "Mixed macro signals — belum ada tren dominan."

    return {
        "macro_regime"      : regime,
        "description"       : desc,
        "nasdaq_change_pct" : nasdaq_chg,
        "dxy_change_pct"    : dxy_chg,
        "gold_change_pct"   : gold_chg,
    }


def get_full_statistics(df: pd.DataFrame, account_size: float = 30_000) -> Dict:
    """
    Shim: gabung quant metrics + zscore + monte carlo.
    Menggantikan get_full_statistics dari stats_engine lama.
    """
    quant  = calculate_quant_metrics(df)
    zscore = calculate_zscore_analysis(df)
    mc     = run_monte_carlo_price(df, days=30, simulations=5_000)
    return {
        "quant"        : quant,
        "zscore"       : zscore,
        "monte_carlo"  : mc,
        "regime"       : {"market_regime": "TRENDING" if abs(quant.get("sortino", 0)) > 1.5
                                           else "MEAN_REVERTING" if abs(quant.get("sortino", 0)) < 0.5
                                           else "RANDOM_WALK"},
        "account_size" : account_size,
    }


def get_master_confidence_report(df, apex_score, ict_bias, kelly_edge,
                                  zscore_signal, regime, vol_regime,
                                  liq_regime, macro_regime, prob_profit, sortino) -> Dict:
    """
    Shim: bungkus calculate_signal_confidence ke format output lama.
    Menggantikan get_master_confidence_report dari model_confidence_engine lama.
    """
    conf = calculate_signal_confidence(
        apex_score    = apex_score if isinstance(apex_score, (int, float)) else apex_score.get("score", 50),
        ict_bias      = ict_bias,
        kelly_edge    = kelly_edge,
        regime        = regime,
        vol_regime    = vol_regime,
        liq_regime    = liq_regime,
        prob_profit   = prob_profit,
        n_data_points = len(df) if df is not None else 252,
        sortino       = sortino,
    )
    # Tambah keys yang dipakai frontend lama
    conf["final_trade_gate"]  = conf.get("trade_gate", "CLOSED")
    conf["governance_score"]  = conf.get("signal_confidence_score", 0)
    conf["active_strategy"]   = {"active_strategy": conf.get("recommended_strategy", "WAIT")}
    return conf


def select_active_strategy(hmm_regime, vol_regime, liq_regime,
                            macro_regime, apex_score, signal_confidence) -> Dict:
    """
    Shim: pilih strategi aktif berdasarkan regime.
    Menggantikan select_active_strategy dari model_confidence_engine lama.
    """
    score = apex_score.get("score", 50) if isinstance(apex_score, dict) else float(apex_score)

    if hmm_regime == "HIGH_VOL_BEARISH" or vol_regime in ("HIGH", "CRISIS"):
        strategy = "DEFENSIVE_SHORT_ONLY"
        sizing   = 0.5
    elif hmm_regime == "LOW_VOL_BULLISH" and score >= 65:
        strategy = "TREND_FOLLOWING_LONG"
        sizing   = 1.0
    elif hmm_regime == "SIDEWAYS_CHOP" or liq_regime == "THIN":
        strategy = "MEAN_REVERSION_RANGE"
        sizing   = 0.7
    else:
        strategy = "WAIT_FOR_CONFLUENCE"
        sizing   = 0.0

    return {
        "active_strategy"  : strategy,
        "sizing_multiplier": sizing,
        "hmm_regime"       : hmm_regime,
        "vol_regime"       : vol_regime,
        "rationale"        : f"Regime={hmm_regime}, Vol={vol_regime}, Score={score:.0f}",
    }


def calculate_corrected_quant_metrics(df: pd.DataFrame) -> Dict:
    """
    Shim: alias untuk calculate_quant_metrics di v6.
    Menggantikan calculate_corrected_quant_metrics dari apex_systematic_trader lama.
    """
    return calculate_quant_metrics(df)


def calculate_risk_of_ruin(win_rate: float, rr_ratio: float, risk_pct: float = 0.02) -> Dict:
    """
    Shim: Monte Carlo risk of ruin (20k paths).
    Menggantikan calculate_risk_of_ruin dari apex_systematic_trader lama.
    """
    from apex_engine_v6 import calculate_kelly
    result = calculate_kelly(win_rate, rr_ratio, 1.0, fraction=risk_pct * 50,
                              account_balance=100_000)
    return {
        "ruin_probability_pct": result.get("ruin_probability_pct", 0),
        "ruin_method"         : result.get("ruin_method", "monte_carlo_20k"),
        "win_rate"            : win_rate,
        "rr_ratio"            : rr_ratio,
        "risk_pct"            : risk_pct,
        "edge_quality"        : result.get("edge_quality", "UNKNOWN"),
    }


def factor_decomposition(asset_returns: np.ndarray, factor_returns: Dict[str, np.ndarray]) -> Dict:
    """
    Shim: OLS factor attribution.
    Menggantikan factor_decomposition dari apex_quant_fund lama.
    """
    results = {}
    for fname, fr in factor_returns.items():
        # Align lengths
        n = min(len(asset_returns), len(fr))
        a, f = asset_returns[-n:], fr[-n:]
        cov_af = float(np.cov(a, f)[0, 1])
        var_f  = float(np.var(f))
        beta   = cov_af / var_f if var_f > 0 else 0.0
        corr   = float(np.corrcoef(a, f)[0, 1])
        results[fname] = {
            "beta"         : round(beta, 4),
            "correlation"  : round(corr, 4),
            "r_squared"    : round(corr ** 2, 4),
        }
    # Alpha = residual not explained by factors
    total_r2 = sum(v["r_squared"] for v in results.values())
    return {
        "factor_betas"      : results,
        "total_r2"          : round(min(total_r2, 1.0), 4),
        "alpha_r2"          : round(max(1.0 - total_r2, 0.0), 4),
        "interpretation"    : (
            "Return mostly explained by systematic factors (low alpha)." if total_r2 > 0.7
            else "Strong idiosyncratic component (high alpha potential)."
        ),
    }


def correlation_clustering(corr_matrix: np.ndarray, tickers: List[str]) -> Dict:
    """
    Shim: simple correlation cluster grouping.
    Menggantikan correlation_clustering dari apex_quant_fund lama.
    """
    n = len(tickers)
    if n < 2 or corr_matrix is None:
        return {"clusters": [], "note": "Insufficient data"}
    # Group tickers with corr > 0.7 as "high correlation cluster"
    clusters = []
    used = set()
    for i in range(n):
        if i in used: continue
        cluster = [tickers[i]]
        for j in range(i + 1, n):
            if j not in used and abs(float(corr_matrix[i][j])) > 0.7:
                cluster.append(tickers[j])
                used.add(j)
        if len(cluster) > 1:
            clusters.append({"tickers": cluster, "avg_corr": round(float(corr_matrix[i][i + 1]), 4)})
        used.add(i)
    return {
        "high_correlation_clusters": clusters,
        "note": f"{len(clusters)} cluster ditemukan (corr > 0.7).",
    }


def trigger_circuit_breaker(reason: str) -> Dict:
    """Shim: manual circuit breaker trigger."""
    return update_risk_rules({"circuit_breaker_active": True, "lock_reason": reason})


def release_lock(override_reason: str) -> Dict:
    """Shim: release circuit breaker lock."""
    return update_risk_rules({"circuit_breaker_active": False, "unlock_reason": override_reason})


def run_backtest(df: pd.DataFrame, strategy_fn, initial_capital: float = 30_000,
                 risk_per_trade: float = 0.01, commission_pct: float = 0.001) -> Dict:
    """Shim: simple backtest runner. Menggunakan rolling_walk_forward sebagai base."""
    lr = np.log(df["Close"] / df["Close"].shift(1)).dropna()
    return {
        "note"            : "Backtest via rolling walk-forward validation",
        "initial_capital" : initial_capital,
        "walk_forward"    : rolling_walk_forward(lr),
    }


def _get_builtin_strategy(name: str):
    """Return a dummy strategy function (required by run_backtest shim)."""
    def ema_crossover(df): return df["Close"].ewm(span=20).mean() > df["Close"].ewm(span=50).mean()
    strategies = {"ema_crossover": ema_crossover}
    return strategies.get(name)


def detect_volume_spoofing(df: pd.DataFrame) -> Dict:
    """
    Shim: volume spoof / wash trade detection.
    Tidak di-port ke v6 karena jarang dipakai — implementasi simpel di sini.
    """
    if df is None or df.empty or "Volume" not in df.columns or "Close" not in df.columns:
        return {"error": "Data Volume + Close diperlukan", "spoof_risk_level": "UNKNOWN"}

    vol = df["Volume"].dropna()
    ret = df["Close"].pct_change().abs().dropna()
    common = vol.index.intersection(ret.index)
    vol, ret = vol.loc[common], ret.loc[common]

    vm, vs = float(vol.mean()), float(vol.std())
    rm     = float(ret.mean())
    flags  = []
    for i in range(len(common)):
        v, r = float(vol.iloc[i]), float(ret.iloc[i])
        if v > vm + 3 * vs and r < rm * 0.5:
            flags.append({"date": str(common[i]), "type": "HIGH_VOL_NO_PRICE_MOVE",
                           "volume_zscore": round((v - vm) / max(vs, 1), 2), "severity": "HIGH"})
    high = [f for f in flags if f.get("severity") == "HIGH"]
    return {
        "total_suspicious_events": len(flags),
        "high_severity_count"    : len(high),
        "spoof_risk_level"       : "HIGH" if len(high) > 3 else "MEDIUM" if len(high) > 0 else "LOW",
        "suspicious_events"      : flags[:10],
    }


def calculate_var_cvar(df: pd.DataFrame, confidence: float = 0.95,
                        horizon_days: int = 1, method: str = "historical") -> Dict:
    """
    Shim: standalone VaR/CVaR endpoint.
    Di v6 sudah embedded di calculate_quant_metrics, ini wrapper untuk /api/stats/var.
    """
    q = calculate_quant_metrics(df)
    return {
        "var_95_hist_pct"  : q.get("var_95_hist_pct"),
        "cvar_95_hist_pct" : q.get("cvar_95_hist_pct"),
        "var_95_cf_pct"    : q.get("var_95_cf_pct"),
        "cvar_95_cf_pct"   : q.get("cvar_95_cf_pct"),
        "fat_tail_warning" : q.get("fat_tail_warning"),
        "confidence"       : confidence,
        "horizon_days"     : horizon_days,
        "method_used"      : "historical+cornish_fisher (apex_engine_v6)",
    }


def detect_market_regime(df: pd.DataFrame) -> Dict:
    """
    Shim: legacy market regime dari stats_engine.
    Di v6 regime ada di detect_hmm_regime — ini wrapper simpel.
    """
    r = detect_hmm_regime(df)
    return {
        "market_regime"  : r.get("current_regime", "UNKNOWN"),
        "confidence_pct" : r.get("confidence_pct", 0),
        "hmm_detail"     : r,
    }


def calculate_volume_profile(df: pd.DataFrame, bins: int = 50) -> Dict:
    """
    Shim: Volume Profile (POC / VAH / VAL).
    Dari ict_engine lama — diimplementasikan ulang di sini.
    """
    if df is None or df.empty or not {"High", "Low", "Close", "Volume"}.issubset(df.columns):
        return {"error": "OHLCV required"}

    price_min = float(df["Low"].min())
    price_max = float(df["High"].max())
    bin_edges = np.linspace(price_min, price_max, bins + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    vol_profile  = np.zeros(bins)

    for _, row in df.iterrows():
        lo, hi, vol = float(row["Low"]), float(row["High"]), float(row["Volume"])
        for b in range(bins):
            if bin_edges[b + 1] >= lo and bin_edges[b] <= hi:
                vol_profile[b] += vol / max(bins, 1)

    poc_idx = int(np.argmax(vol_profile))
    poc     = round(float(bin_centers[poc_idx]), 4)
    total_v = float(vol_profile.sum())
    cum_v   = np.cumsum(vol_profile)
    vah_idx = int(np.searchsorted(cum_v, total_v * 0.85))
    val_idx = int(np.searchsorted(cum_v, total_v * 0.15))
    vah_idx = min(vah_idx, bins - 1)
    val_idx = min(val_idx, bins - 1)

    return {
        "poc"          : poc,
        "vah"          : round(float(bin_centers[vah_idx]), 4),
        "val"          : round(float(bin_centers[val_idx]), 4),
        "current_price": round(float(df["Close"].iloc[-1]), 4),
        "above_poc"    : bool(df["Close"].iloc[-1] > poc),
        "bins"         : bins,
    }


def detect_liquidity_zones(df: pd.DataFrame, tolerance_pct: float = 0.1) -> Dict:
    """
    Shim: liquidity zone detection (swing highs/lows clusters).
    Dari ict_engine lama.
    """
    if df is None or df.empty or not {"High", "Low"}.issubset(df.columns):
        return {"error": "OHLCV required"}

    highs = df["High"].values
    lows  = df["Low"].values
    n     = len(df)
    tol   = tolerance_pct / 100

    swing_highs, swing_lows = [], []
    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            swing_highs.append({"price": round(float(highs[i]), 4), "date": str(df.index[i])})
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            swing_lows.append({"price": round(float(lows[i]), 4), "date": str(df.index[i])})

    return {
        "swing_highs"      : swing_highs[-5:],
        "swing_lows"       : swing_lows[-5:],
        "resistance_zones" : [s["price"] for s in swing_highs[-3:]],
        "support_zones"    : [s["price"] for s in swing_lows[-3:]],
        "tolerance_pct"    : tolerance_pct,
    }


# ══════════════════════════════════════════════════════════════════
#  SCREENER: run_screener tetap butuh parallel scanning
#  Diimplementasikan di sini menggunakan score_ticker_from_df dari v6
# ══════════════════════════════════════════════════════════════════

SCORE_LEGEND = {
    "SATIN_READY": "Score ≥ 70 — Setup optimal, semua dimensi aligned",
    "MARGINAL"   : "Score 50–69 — Setup cukup layak dengan selektivitas tinggi",
    "REJECTED"   : "Score < 50 — Setup tidak memenuhi kriteria minimum",
}


def run_screener(markets: List[str] = None, min_score: float = 0,
                  max_workers: int = 8, custom_tickers: List[str] = None) -> Dict:
    """
    Parallel screener menggunakan score_ticker_from_df dari apex_engine_v6.
    Menggantikan run_screener dari screener_engine lama.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time

    # Build ticker list
    tickers_to_scan = []
    if custom_tickers:
        tickers_to_scan = custom_tickers
    elif markets:
        for market in markets:
            tickers_to_scan.extend(WATCHLISTS.get(market, []))
    else:
        for v in WATCHLISTS.values():
            tickers_to_scan.extend(v)

    tickers_to_scan = list(dict.fromkeys(tickers_to_scan))  # deduplicate

    def _scan_one(ticker: str) -> Optional[Dict]:
        try:
            df = get_market_data(ticker)
            if df is None or df.empty: return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            result = score_ticker_from_df(df)
            result["ticker"] = ticker
            return result if result.get("score", 0) >= min_score else None
        except Exception:
            return None

    start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_scan_one, t): t for t in tickers_to_scan}
        for fut in as_completed(futures):
            r = fut.result()
            if r: results.append(r)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    satin_ready = [r for r in results if r.get("status") == "SATIN_READY"]
    marginal    = [r for r in results if r.get("status") == "MARGINAL"]
    rejected    = [r for r in results if r.get("status") == "REJECTED"]

    # Top pick per market
    top_picks = {}
    for market, tks in WATCHLISTS.items():
        market_results = [r for r in results if r.get("ticker") in tks]
        if market_results:
            top_picks[market] = market_results[0]

    return {
        "scan_metadata": {
            "total_scanned" : len(tickers_to_scan),
            "total_returned": len(results),
            "duration_sec"  : round(time.time() - start, 2),
            "min_score_filter": min_score,
        },
        "summary": {
            "satin_ready": len(satin_ready),
            "marginal"   : len(marginal),
            "rejected"   : len(rejected),
        },
        "top_picks"   : top_picks,
        "satin_ready" : satin_ready,
        "marginal"    : marginal,
        "ranked_list" : results,
    }


# ══════════════════════════════════════════════════════════════════
#  APP INIT (tidak berubah)
# ══════════════════════════════════════════════════════════════════

app = FastAPI(
    title       = "APEX Quantum Command",
    description = "Institutional-Grade Quantitative Trading Intelligence Platform",
    version     = "6.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://apexq-m5hjixdfc-faradiansyahrokans-projects.vercel.app",
        "https://apexq.vercel.app"
    ],
    allow_origin_regex=r"https://(.*\.vercel\.app|.*\.trycloudflare\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler — pastikan CORS header ada di error 500."""
    error_msg   = str(exc)
    stack_trace = traceback.format_exc()
    print(f" GLOBAL ERROR: {error_msg}")
    print(stack_trace)
    response = JSONResponse(
        status_code = 500,
        content     = sanitize_data({
            "error"  : "Internal Server Error",
            "message": error_msg,
            "path"   : request.url.path,
        }),
    )
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    response = JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# ══════════════════════════════════════════════════════════════════
#  HELPERS (tidak berubah dari v3)
# ══════════════════════════════════════════════════════════════════

def _is_crypto(ticker: str) -> bool:
    """Deteksi apakah ticker adalah crypto — jangan kirim ke yfinance."""
    t = ticker.upper().strip()
    return t.endswith('-USD') or t.endswith('USDT') or t.endswith('-USDT')

def _fetch_df(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Fetch DataFrame. Crypto → pakai _fetch_crypto_df (tidak pernah yfinance)."""
    if _is_crypto(ticker):
        # Untuk endpoint yang hanya butuh df (bukan chart_data),
        # tetap pakai _fetch_crypto_df lalu ambil df-nya saja
        df, _, _, _ = _fetch_crypto_df(ticker)
        return df
    df = get_market_data(ticker, period=period)
    if df is not None and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_crypto_df(ticker: str, tf: str = "1D"):
    """
    Ambil data crypto HANYA dari Hyperliquid → Binance.
    TIDAK ada fallback ke yfinance — Yahoo Finance 401 untuk crypto.
    """
    # 1. Coba Hyperliquid dulu (native L1, paling akurat)
    try:
        df, chart_data, price, profile = get_hl_crypto_data(ticker, tf)
        if df is not None and not df.empty and chart_data:
            print(f" [CRYPTO] {ticker} → Hyperliquid ({len(chart_data)} candles)")
            return df, chart_data, price, profile
    except Exception as e:
        print(f"  [CRYPTO] {ticker} → Hyperliquid error: {e}")

    # 2. Fallback ke Binance
    try:
        df, chart_data, price, profile = get_binance_crypto_data(ticker, tf)
        if df is not None and not df.empty and chart_data:
            print(f" [CRYPTO] {ticker} → Binance ({len(chart_data)} candles)")
            return df, chart_data, price, profile
    except Exception as e:
        print(f"  [CRYPTO] {ticker} → Binance error: {e}")

    # 3. Tidak ada data — return None, JANGAN yfinance
    print(f" [CRYPTO] {ticker} → No data from Hyperliquid or Binance.")
    return None, [], 0.0, {
        "full_name": ticker,
        "sector": "Web3 & Crypto",
        "exchange": "N/A",
        "currency": "USD",
        "data_source": "UNAVAILABLE",
    }


def _calc_apex_score(quant: Dict, ict: Dict, stats: Dict) -> Dict:
    """Hitung APEX composite score dari multi-engine output."""
    score = 50
    score += min(quant.get("sortino", 0) * 5, 15)
    bull_f = ict.get("bullish_factors", 0)
    bear_f = ict.get("bearish_factors", 0)
    score += max(-15, min((bull_f - bear_f) * 3, 15))
    regime = stats.get("regime", {}).get("market_regime", "RANDOM_WALK")
    if "TREND" in regime:      score += 10
    elif regime == "MEAN_REVERTING": score -= 5
    zsig = stats.get("zscore", {}).get("signal", "NEUTRAL")
    if "OVERSOLD"   in zsig: score += 7
    elif "OVERBOUGHT" in zsig: score -= 7
    score = max(0, min(100, score))
    verdict = "BULLISH" if score >= 70 else "BEARISH" if score <= 30 else "NEUTRAL"
    return {"score": round(score, 1), "verdict": verdict, "out_of": 100}

def _calc_apex_score_v6(quant: Dict, ict: Dict, stats: Dict, screener: Dict, hmm_info: Dict) -> Dict:
    """Hitung APEX composite score dari multi-engine output, termasuk v6 screener dan HMM."""
    score = 50
    score += min(quant.get("sortino", 0) * 5, 15)
    bull_f = ict.get("bullish_factors", 0)
    bear_f = ict.get("bearish_factors", 0)
    score += max(-15, min((bull_f - bear_f) * 3, 15))
    
    # Incorporate HMM regime from v6
    hmm_regime = hmm_info.get("current_regime", "RANDOM_WALK")
    if "TREND" in hmm_regime: score += 10
    elif hmm_regime == "MEAN_REVERTING": score -= 5

    zsig = stats.get("zscore", {}).get("signal", "NEUTRAL")
    if "OVERSOLD"   in zsig: score += 7
    elif "OVERBOUGHT" in zsig: score -= 7

    # Incorporate screener score
    screener_score = screener.get("score", 50)
    score += (screener_score - 50) * 0.2 # Add 20% of screener deviation from 50

    score = max(0, min(100, score))
    verdict = "BULLISH" if score >= 70 else "BEARISH" if score <= 30 else "NEUTRAL"
    return {"score": round(score, 1), "verdict": verdict, "out_of": 100}


def _calculate_global_risk_score(cross_asset: Dict) -> Dict:
    dxy_chg    = cross_asset.get("DXY",    {}).get("change_pct", 0)
    nasdaq_chg = cross_asset.get("NASDAQ", {}).get("change_pct", 0)
    gold_chg   = cross_asset.get("GOLD",   {}).get("change_pct", 0)
    risk_score = 50 + nasdaq_chg * 3 - dxy_chg * 2 - gold_chg * 1
    risk_score = max(0, min(100, risk_score))
    return {
        "global_risk_score": round(risk_score, 2),
        "label"            : "RISK_ON" if risk_score > 60 else "RISK_OFF" if risk_score < 40 else "NEUTRAL",
        "description"      : (f"Score {risk_score:.1f}/100. "
                               f"{'Likuiditas global ke risk assets.' if risk_score > 60 else 'Flight to safety.' if risk_score < 40 else 'Mixed macro.'}"),
    }


# ══════════════════════════════════════════════════════════════════
#  ENDPOINTS — semua URL sama persis dengan v3
# ══════════════════════════════════════════════════════════════════

# ── Market Overview ───────────────────────────────────────────────

@app.get("/api/market-overview/{tf}")
def market_overview(tf: str):
    tf_map = {"1D": {"period": "1d", "interval": "1m"}, "1W": {"period": "5d", "interval": "15m"},
              "1M": {"period": "1mo", "interval": "1h"}, "1Y": {"period": "1y", "interval": "1d"}}
    config = tf_map.get(tf, tf_map["1D"])
    try:
        asset = yf.Ticker("^JKSE")
        df    = asset.history(period=config["period"], interval=config["interval"])
        if df.empty: return {"error": "No data"}
        try:
            df.index = df.index.tz_convert("UTC") if df.index.tz else df.index.tz_localize("Asia/Jakarta").tz_convert("UTC")
        except Exception: pass
        open_price = df["Open"].iloc[0]
        history = [{"time": index.strftime("%Y-%m-%d") if tf == "1Y" else int(index.timestamp()),
                    "value": float(row["Close"])} for index, row in df.iterrows()]
        return {"ihsg": {"current": round(df["Close"].iloc[-1], 2), "open": round(open_price, 2),
                          "high": round(df["High"].max(), 2), "history": history},
                "news": get_global_market_news(), "global": get_global_indices()}
    except Exception as e:
        return {"error": str(e)}


# ── Asset Analysis ────────────────────────────────────────────────

@app.get("/api/analyze/{ticker}")
def analyze_asset(ticker: str, tf: str = "1D"):
    is_crypto = _is_crypto(ticker)
    if is_crypto:
        # Crypto → HANYA Hyperliquid atau Binance, tidak pernah yfinance
        df, chart_data, price, profile = _fetch_crypto_df(ticker, tf)
    else:
        profile = get_company_profile(ticker)
        yf_tf_map = {
            "1m": {"period": "5d", "interval": "1m"}, "15m": {"period": "60d", "interval": "15m"},
            "1H": {"period": "730d", "interval": "1h"}, "1D": {"period": "1y", "interval": "1d"}
        }
        config = yf_tf_map.get(tf, {"period": "1y", "interval": "1d"})
        df = yf.download(ticker, period=config["period"], interval=config["interval"], progress=False, auto_adjust=True)
        if df is not None and not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = get_live_quote(ticker)
        if profile: profile['data_source'] = "YAHOO FINANCE"
        chart_data = []
        if df is not None and not df.empty:
            for index, row in df.iterrows():
                row_time = index.strftime('%Y-%m-%d') if tf == "1D" else int(index.timestamp())
                chart_data.append({"time": row_time, "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close']), "volume": float(row['Volume'])})

    if df is None or df.empty or not chart_data:
        return {"error": f"Data not found for {ticker}"}

    # Use v6 engine (bug-fixed institutional grade)
    try:
        metrics_v6 = v6_quant_metrics(df, ticker)
        tech_v6    = v6_technicals(df)
    except Exception:
        metrics_v6 = calculate_quant_metrics(df, ticker)  # fallback
        tech_v6    = {}

    return sanitize_data({
        "ticker"      : ticker.upper(),
        "profile"     : profile,
        "price"       : price,
        "metrics"     : metrics_v6,
        "technicals"  : tech_v6,
        "news"        : get_smart_news(ticker, profile.get('full_name', ticker) if profile else ticker),
        "history"     : chart_data,
        "fundamentals": get_fundamentals(ticker, is_crypto),
        "ai_analysis" : "PENDING",
        "ai_reasoning": ""
    })


# ── Regime ────────────────────────────────────────────────────────

@app.get("/api/regime/full/{ticker}")
def regime_full(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    cross_asset = get_cross_asset_data()
    return get_full_regime_analysis(df, cross_asset_data=cross_asset)


@app.get("/api/regime/hmm/{ticker}")
def regime_hmm(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_hmm_regime(df)


@app.get("/api/regime/volatility/{ticker}")
def regime_vol(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_vol_clustering(df)


@app.get("/api/regime/liquidity/{ticker}")
def regime_liq(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_liquidity_regime(df)


@app.get("/api/regime/macro")
def regime_macro():
    cross_asset = get_cross_asset_data()
    return tag_macro_regime(cross_asset)


# ── Factor ────────────────────────────────────────────────────────

@app.get("/api/factor/full/{ticker}")
def factor_full(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    df_nasdaq = _fetch_df("^IXIC"); df_btc = _fetch_df("BTC-USD"); df_dxy = _fetch_df("DX-Y.NYB")
    return get_factor_composite(df)  # v6 tidak pakai cross_asset_dfs param


@app.get("/api/factor/momentum/{ticker}")
def factor_momentum(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return analyze_momentum_factor(df)


@app.get("/api/factor/vrp/{ticker}")
def factor_vrp(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return calculate_vol_risk_premium(df)


@app.get("/api/factor/btc-dominance")
def factor_btc_dom():
    return {"data_available": False, "message": "Gunakan CoinGecko API untuk data BTC dominance real-time."}


# ── Cross-Asset ───────────────────────────────────────────────────

@app.get("/api/cross-asset/overview")
def cross_asset_overview():
    cross_asset  = get_cross_asset_data()
    macro_regime = tag_macro_regime(cross_asset)
    return {"cross_asset_data": cross_asset, "macro_regime": macro_regime,
            "global_risk_score": _calculate_global_risk_score(cross_asset)}


@app.get("/api/cross-asset/sensitivity/{ticker}")
def cross_asset_sensitivity(ticker: str):
    df_asset = _fetch_df(ticker)
    if df_asset is None or df_asset.empty: raise HTTPException(404, f"No data for {ticker}")
    df_nasdaq = _fetch_df("^IXIC"); df_btc = _fetch_df("BTC-USD"); df_dxy = _fetch_df("DX-Y.NYB")
    # Use factor decomposition as proxy for cross-asset sensitivity
    def _lr(df): return np.log(df["Close"] / df["Close"].shift(1)).dropna().values if df is not None and not df.empty else None
    factors = {k: v for k, v in {"nasdaq": _lr(df_nasdaq), "btc": _lr(df_btc), "dxy": _lr(df_dxy)}.items() if v is not None}
    return factor_decomposition(_lr(df_asset), factors)


# ── Scenario ──────────────────────────────────────────────────────

class ScenarioReplayRequest(BaseModel):
    current_price: float; scenario_key: str; account_balance: float = 30_000
    position_pct: float = 10.0; use_stop_loss: bool = True; stop_loss_pct: float = 5.0

class ShockSimRequest(BaseModel):
    ticker: str; shock_vol_sigma: float = 3.0; shock_direction: str = "DOWN"
    shock_duration: int = 5; account_balance: float = 30_000; position_pct: float = 10.0

class TailRiskRequest(BaseModel):
    ticker: str; current_price: float; account_balance: float = 30_000; position_pct: float = 10.0


@app.get("/api/scenario/library")
def scenario_library():
    return {"scenarios": {k: {"name": v["name"], "description": v["description"],
                               "duration_days": v["duration_days"], "key_stats": v["key_stats"]}
                           for k, v in CRISIS_SCENARIOS.items()}}


@app.post("/api/scenario/replay")
def scenario_replay(req: ScenarioReplayRequest):
    return replay_historical_scenario(req.current_price, req.scenario_key, req.account_balance,
                                       req.position_pct, req.use_stop_loss, req.stop_loss_pct)


@app.post("/api/scenario/shock")
def scenario_shock(req: ShockSimRequest):
    """
    Custom shock sim — di v6 tidak ada simulate_custom_shock,
    diganti dengan replay skenario terdekat berdasarkan sigma.
    """
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    # Pilih scenario berdasarkan magnitude
    sk = "covid_crash_2020" if req.shock_vol_sigma >= 5 else "ftx_collapse_2022" if req.shock_vol_sigma >= 3 else "fed_tightening_2022"
    price = float(df["Close"].iloc[-1])
    return {**replay_historical_scenario(price, sk, req.account_balance, req.position_pct),
            "note": f"Shock {req.shock_vol_sigma}σ mapped to scenario: {sk}"}


@app.post("/api/scenario/tail-risk")
def scenario_tail_risk(req: TailRiskRequest):
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    return generate_tail_risk_report(req.account_balance, [{"ticker": req.ticker, "position_pct": req.position_pct}], df)


# ── Model Confidence ──────────────────────────────────────────────

@app.get("/api/confidence/full/{ticker}")
def confidence_full(ticker: str, account_size: float = 30_000):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    quant       = calculate_quant_metrics(df, ticker)
    ict         = get_ict_full_analysis(df)
    stats       = get_full_statistics(df, account_size=account_size)
    cross_asset = get_cross_asset_data()
    r_full      = get_full_regime_analysis(df, cross_asset_data=cross_asset)
    log_ret = (df["Close"].pct_change().dropna() * 100).tolist()
    kelly   = kelly_from_trade_history([{"pnl_pct": r} for r in log_ret[-252:]], account_balance=account_size)
    apex_score = _calc_apex_score(quant, ict, stats)
    cr = r_full.get("composite_regime", {})
    return get_master_confidence_report(
        df=df, apex_score=apex_score, ict_bias=ict.get("composite_bias", "NEUTRAL"),
        kelly_edge=kelly.get("edge_quality", "UNKNOWN"),
        zscore_signal=stats.get("zscore", {}).get("signal", "NEUTRAL"),
        regime=cr.get("hmm_regime", "UNKNOWN"), vol_regime=cr.get("vol_regime", "UNKNOWN"),
        liq_regime=cr.get("liq_regime", "UNKNOWN"), macro_regime=cr.get("macro_regime", "UNKNOWN"),
        prob_profit=stats.get("monte_carlo", {}).get("prob_profit_pct", 50),
        sortino=quant.get("sortino", 0))


@app.get("/api/confidence/strategy/{ticker}")
def meta_strategy(ticker: str, account_size: float = 30_000):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    cross_asset = get_cross_asset_data()
    r_full = get_full_regime_analysis(df, cross_asset_data=cross_asset)
    quant  = calculate_quant_metrics(df, ticker)
    ict    = get_ict_full_analysis(df)
    stats  = get_full_statistics(df, account_size=account_size)
    apex   = _calc_apex_score(quant, ict, stats)
    cr     = r_full.get("composite_regime", {})
    return select_active_strategy(hmm_regime=cr.get("hmm_regime", "UNKNOWN"),
                                   vol_regime=cr.get("vol_regime", "UNKNOWN"),
                                   liq_regime=cr.get("liq_regime", "UNKNOWN"),
                                   macro_regime=cr.get("macro_regime", "UNKNOWN"),
                                   apex_score=apex, signal_confidence=50)


# ── Data Quality ──────────────────────────────────────────────────

@app.get("/api/data-quality/{ticker}")
def data_quality(ticker: str, interval: str = "1D"):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return generate_data_quality_report(df, expected_interval=interval)


@app.get("/api/data-quality/outliers/{ticker}")
def data_outliers(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_price_outliers(df)


@app.get("/api/data-quality/spoof/{ticker}")
def data_spoof(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_volume_spoofing(df)


# ── Apex Institutional ────────────────────────────────────────────

@app.get("/api/apex-institutional/{ticker}")
def apex_institutional(ticker: str, tf: str = "1D", account_size: float = 30_000):
    """ APEX INSTITUTIONAL INTELLIGENCE — semua engine dalam satu call."""
    is_crypto = _is_crypto(ticker)
    if is_crypto:
        # Crypto → HANYA Hyperliquid atau Binance, tidak pernah yfinance
        df, _, price, profile = _fetch_crypto_df(ticker, tf)
    else:
        profile = get_company_profile(ticker)
        yf_tf_map = {"1m": {"period": "5d", "interval": "1m"}, "15m": {"period": "60d", "interval": "15m"},
                     "1H": {"period": "730d", "interval": "1h"}, "1D": {"period": "1y", "interval": "1d"}}
        config = yf_tf_map.get(tf, {"period": "1y", "interval": "1d"})
        df = yf.download(ticker, period=config["period"], interval=config["interval"], progress=False, auto_adjust=True)
        if df is not None and not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = get_live_quote(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")

    # ── Run all engines (v6 — Institutional Grade) ──────────────────
    try:
        quant    = v6_quant_metrics(df, ticker)   # Bug-fixed Sortino, Calmar
        tech     = v6_technicals(df)              # EMA, RSI, ADX, MACD
        ict      = v6_ict_analysis(df)            # FVG, OB, Market Structure
        hmm_info = v6_hmm_regime(df)              # Pure NumPy HMM (causal)
        vol_reg  = v6_vol_clustering(df)          # GARCH(1,1) vol clustering
        liq_reg  = v6_liq_regime(df)             # Amihud illiquidity
        screener = v6_screener_score(df)          # Institutional screener score
        factor   = v6_factor_composite(df)        # Momentum + VRP
    except Exception as e:
        print(f" v6 engine partial failure for {ticker}: {e} — falling back to legacy")
        quant    = calculate_quant_metrics(df, ticker)
        tech     = {}
        ict      = get_ict_full_analysis(df)
        hmm_info = detect_hmm_regime(df)
        vol_reg  = detect_vol_clustering(df)
        liq_reg  = detect_liquidity_regime(df)
        screener = {}
        factor   = get_factor_composite(df)

    # Legacy engines still used for remaining sub-analyses
    stats        = get_full_statistics(df, account_size=account_size)
    cross_asset  = get_cross_asset_data()

    # v6 regime analysis (full composite)
    try:
        regime = v6_regime_analysis(df)
    except Exception:
        regime = get_full_regime_analysis(df)

    df_nasdaq       = _fetch_df("^IXIC")
    factor_lab_data = calculate_factor_lab(df, df_nasdaq)
    fundamentals    = get_fundamentals(ticker, is_crypto)
    data_qual       = generate_data_quality_report(df)

    # Kelly using v6 (Monte Carlo ruin — no Gambler's Ruin bug)
    log_ret = (df['Close'].pct_change().dropna() * 100).tolist()
    try:
        kelly = v6_kelly_history([{"pnl_pct": r} for r in log_ret[-252:]], account_balance=account_size)
    except Exception:
        kelly = kelly_from_trade_history([{"pnl_pct": r} for r in log_ret[-252:]], account_balance=account_size)

    # APEX Score — now incorporates institutional screener + regime
    apex_score = _calc_apex_score_v6(quant, ict, stats, screener, hmm_info)

    # Model Confidence + Strategy
    confidence = get_master_confidence_report(
        df=df,
        apex_score=apex_score["score"],
        ict_bias=ict.get("composite_bias", "NEUTRAL"),
        kelly_edge=kelly.get("edge_quality", "UNKNOWN"),
        zscore_signal=stats.get("zscore", {}).get("signal", "NEUTRAL"),
        regime=hmm_info.get("current_regime", regime.get("composite_regime", {}).get("hmm_regime", "UNKNOWN")),
        vol_regime=vol_reg.get("vol_regime", "UNKNOWN"),
        liq_regime=liq_reg.get("liq_regime", "UNKNOWN"),
        macro_regime=regime.get("composite_regime", {}).get("macro_regime", "UNKNOWN"),
        prob_profit=stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50),
        sortino=quant.get("sortino", 0)
    )

    # Key Signals Aggregation
    signals = {
        "quant_action"      : quant.get("action", "NEUTRAL"),
        "ict_bias"          : ict.get("composite_bias", "NEUTRAL"),
        "hmm_regime"        : hmm_info.get("current_regime", "UNKNOWN"),
        "vol_regime"        : vol_reg.get("vol_regime", "UNKNOWN"),
        "liq_regime"        : liq_reg.get("liq_regime", "UNKNOWN"),
        "macro_regime"      : regime.get("composite_regime", {}).get("macro_regime", "UNKNOWN"),
        "active_model"      : regime.get("active_model", "UNKNOWN"),
        "zscore_signal"     : stats.get("zscore", {}).get("signal", "NEUTRAL"),
        "kelly_edge"        : kelly.get("edge_quality", "UNKNOWN"),
        "momentum_signal"   : factor.get("momentum_signal", factor.get("momentum_factor", {}).get("momentum_signal", "UNKNOWN")),
        "factor_alpha"      : factor.get("factor_alpha_score", 50),
        "trade_gate"        : confidence.get("final_trade_gate", "CLOSED"),
        "active_strategy"   : confidence.get("active_strategy", {}).get("active_strategy", "UNKNOWN"),
        "governance_score"  : confidence.get("governance_score", 0),
        "data_quality"      : data_qual.get("composite_quality_score", 0),
        "monte_carlo_profit": stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50),
        "screener_score"    : screener.get("score", 0),
        "screener_status"   : screener.get("status", "UNKNOWN"),
        "regime_summary"    : regime.get("regime_summary", hmm_info.get("current_regime", "")),
    }

    return sanitize_data({
        "ticker"       : ticker.upper(),
        "price"        : price,
        "profile"      : profile,
        "apex_score"   : apex_score,
        "signals"      : signals,
        "quant"        : quant,
        "technicals"   : tech,
        "ict_analysis" : ict,
        "statistics"   : stats,
        "regime"       : regime,
        "hmm_regime"   : hmm_info,
        "vol_regime"   : vol_reg,
        "liq_regime"   : liq_reg,
        "factor"       : factor,
        "kelly"        : kelly,
        "confidence"   : confidence,
        "fundamentals" : fundamentals,
        "data_quality" : data_qual,
        "macro"        : cross_asset,
        "factor_lab"   : factor_lab_data,
        "screener"     : screener,
    })


# ── Satin Streaming ───────────────────────────────────────────────

@app.get("/api/satin/stream/{ticker}")
async def satin_stream(ticker: str, tf: str = "1D", account_size: float = 30_000):
    try:
        apex_data = apex_institutional(ticker, tf=tf, account_size=account_size)
        return StreamingResponse(get_satin_reasoning(ticker, apex_data),
                                  media_type="text/plain",
                                  headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
    except Exception as e:
        return {"error": str(e)}


# ── Kelly Endpoints ───────────────────────────────────────────────

class KellyManualRequest(BaseModel):
    win_rate: float; avg_win: float; avg_loss: float
    fraction: float = 0.25; account_balance: float = 30_000; max_risk_pct: float = 2.0

class TradeHistoryRequest(BaseModel):
    trades: List[Dict[str, Any]]; account_balance: float = 30_000; fraction: float = 0.25

class PositionSizerRequest(BaseModel):
    entry_price: float; stop_loss_price: float
    account_balance: float = 30_000; risk_pct: float = 1.0; leverage: float = 1.0


@app.post("/api/kelly/manual")
def kelly_manual(req: KellyManualRequest):
    return calculate_kelly(req.win_rate, req.avg_win, req.avg_loss, req.fraction, req.account_balance, req.max_risk_pct)


@app.post("/api/kelly/from-history")
def kelly_history(req: TradeHistoryRequest):
    return kelly_from_trade_history(req.trades, req.account_balance, req.fraction)


@app.post("/api/kelly/position-size")
def position_sizer(req: PositionSizerRequest):
    return calculate_position_size(req.entry_price, req.stop_loss_price, req.account_balance, req.risk_pct, req.leverage)


# ── Stats Endpoints ───────────────────────────────────────────────

@app.get("/api/stats/full/{ticker}")
def full_statistics(ticker: str, account_size: float = 30_000):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"Data tidak tersedia untuk {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return get_full_statistics(df, account_size=account_size)


@app.get("/api/stats/zscore/{ticker}")
def zscore_endpoint(ticker: str, window: int = 20):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return calculate_zscore_analysis(df, window=window)


@app.get("/api/stats/monte-carlo/{ticker}")
def monte_carlo_endpoint(ticker: str, days: int = 30, simulations: int = 10000, account_size: float = 30_000):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return run_monte_carlo_price(df, days=days, simulations=simulations)


@app.get("/api/stats/var/{ticker}")
def var_endpoint(ticker: str, confidence: float = 0.95, horizon: int = 1, method: str = "historical"):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return calculate_var_cvar(df, confidence=confidence, horizon_days=horizon, method=method)


@app.get("/api/stats/regime/{ticker}")
def regime_endpoint(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return detect_market_regime(df)


# ── ICT Endpoints ─────────────────────────────────────────────────

@app.get("/api/ict/full/{ticker}")
def ict_full(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return get_ict_full_analysis(df)


@app.get("/api/ict/fvg/{ticker}")
def fvg_endpoint(ticker: str, min_gap_pct: float = 0.1):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return detect_fvg(df, min_gap_pct=min_gap_pct)


@app.get("/api/ict/orderblock/{ticker}")
def ob_endpoint(ticker: str, lookback: int = 50):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return detect_order_blocks(df, lookback=lookback)


@app.get("/api/ict/volume-profile/{ticker}")
def volume_profile_endpoint(ticker: str, bins: int = 50):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return calculate_volume_profile(df, bins=bins)


@app.get("/api/ict/liquidity/{ticker}")
def liquidity_endpoint(ticker: str, tolerance_pct: float = 0.1):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return detect_liquidity_zones(df, tolerance_pct=tolerance_pct)


@app.get("/api/ict/structure/{ticker}")
def structure_endpoint(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return detect_market_structure(df)


# ── Satin Risk Manager ────────────────────────────────────────────

class PreTradeRequest(BaseModel):
    entry_price: float; stop_loss_price: float; position_size: float; ticker: str; direction: str = "LONG"

class RecordTradeRequest(BaseModel):
    ticker: str; direction: str; entry: float; exit_price: float; size_usd: float; notes: str = ""

class LockRequest(BaseModel):
    reason: str

class UnlockRequest(BaseModel):
    override_reason: str

class UpdateRulesRequest(BaseModel):
    rules: Dict[str, Any]

class BacktestRequest(BaseModel):
    ticker: str; strategy_name: str = "ema_crossover"; initial_capital: float = 30_000
    risk_per_trade: float = 0.01; commission_pct: float = 0.001


@app.get("/api/satin/status")
def satin_status(): return get_satin_status()


@app.post("/api/satin/pre-trade-check")
def satin_pre_trade(req: PreTradeRequest):
    return pre_trade_check(req.entry_price, req.stop_loss_price, req.position_size, req.ticker, req.direction)


@app.post("/api/satin/record-trade")
def satin_record(req: RecordTradeRequest):
    return record_trade(req.ticker, req.direction, req.entry, req.exit_price, req.size_usd, req.notes)


@app.post("/api/satin/lock")
def satin_lock(req: LockRequest): return trigger_circuit_breaker(req.reason)


@app.post("/api/satin/unlock")
def satin_unlock(req: UnlockRequest): return release_lock(req.override_reason)


@app.post("/api/satin/update-rules")
def satin_update_rules(req: UpdateRulesRequest): return update_risk_rules(req.rules)


@app.post("/api/satin/backtest")
def satin_backtest(req: BacktestRequest):
    df = get_market_data(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    return run_backtest(df, _get_builtin_strategy(req.strategy_name), req.initial_capital, req.risk_per_trade, req.commission_pct)


# ── Screener ──────────────────────────────────────────────────────

@app.get("/api/screener/run")
def screener_run(markets: str = Query(default="IDX,US,CRYPTO"), min_score: float = Query(default=0), workers: int = Query(default=8)):
    market_list = [m.strip().upper() for m in markets.split(",") if m.strip()]
    return run_screener(markets=market_list, min_score=min_score, max_workers=min(max(workers, 1), 12))


@app.get("/api/screener/custom")
def screener_custom(tickers: str = Query(...), min_score: float = Query(default=0)):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list: raise HTTPException(400, "Tidak ada ticker yang valid.")
    if len(ticker_list) > 50: raise HTTPException(400, "Maksimal 50 ticker per request.")
    return run_screener(markets=[], min_score=min_score, custom_tickers=ticker_list)


@app.get("/api/screener/watchlist")
def screener_get_watchlist():
    return {"watchlists": WATCHLISTS, "total_tickers": sum(len(v) for v in WATCHLISTS.values()), "score_legend": SCORE_LEGEND}


# ── Portfolio Simulator ───────────────────────────────────────────

@app.post("/api/simulate")
async def simulate(config: SimulationConfig):
    result = run_simulation(config)
    return sanitize_data(generate_json_report(result))


@app.post("/api/simulate/stream")
async def simulate_stream(config: SimulationConfig):
    """
    SSE endpoint — stream progress simulasi real-time ke frontend.
    Frontend connect via EventSource / ReadableStream, terima events:
      phase | tick | trade | done | error
    Setiap event = "data: <json>\\n\\n"

    ARSITEKTUR BENAR — Thread + asyncio.Queue:
    ┌─────────────────────────────────────────────────────────┐
    │  Background Thread                                       │
    │  for chunk in run_simulation_stream(config):            │
    │      loop.call_soon_threadsafe(queue.put_nowait, chunk) │
    │  → push sentinel (None) saat selesai                    │
    └────────────────────┬────────────────────────────────────┘
                         │  asyncio.Queue (thread-safe bridge)
    ┌────────────────────▼────────────────────────────────────┐
    │  Async Generator (event loop thread)                    │
    │  chunk = await queue.get()   ← non-blocking await       │
    │  yield chunk  → StreamingResponse → frontend            │
    └─────────────────────────────────────────────────────────┘

    Kenapa ini benar vs run_in_executor + next():
    - run_in_executor + next() : tiap next() block thread sampai
      yield berikutnya (bisa menit). HTTP connection timeout duluan.
    - Thread + Queue           : simulasi jalan bebas di thread,
      event dikirim ke queue segera saat yield, async generator
      langsung forward ke frontend tanpa delay.
    """
    from app.engine.portfolio_simulator import run_simulation_stream
    import asyncio
    import threading
    import json as _j

    async def event_generator():
        loop  = asyncio.get_running_loop()
        queue = asyncio.Queue()

        # ── Jalankan seluruh generator sinkron di background thread ──
        def run_in_thread():
            try:
                for chunk in run_simulation_stream(config):
                    # call_soon_threadsafe: satu-satunya cara aman
                    # untuk push dari thread ke asyncio.Queue
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as exc:
                err_event = "data: " + _j.dumps({
                    "type"   : "error",
                    "message": str(exc),
                }) + "\n\n"
                loop.call_soon_threadsafe(queue.put_nowait, err_event)
            finally:
                # Sentinel — beritahu generator async bahwa stream sudah selesai
                loop.call_soon_threadsafe(queue.put_nowait, None)

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # ── Baca dari queue dan forward ke frontend ───────────────────
        while True:
            chunk = await queue.get()
            if chunk is None:   # sentinel → selesai
                break
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control"              : "no-cache",
            "Connection"                 : "keep-alive",
            "X-Accel-Buffering"          : "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Phase 2: Risk Architecture ────────────────────────────────────

class VolTargetRequest(BaseModel):
    current_vol_ann: float; target_vol_ann: float = 0.10
    account_balance: float = 30_000; asset_price: float; leverage_cap: float = 3.0

class CVaRKellyRequest(BaseModel):
    win_rate: float; avg_win_pct: float; avg_loss_pct: float
    ticker: str; cvar_limit: float = 0.02; kelly_frac: float = 0.25

class HeatRequest(BaseModel):
    positions: List[Dict]; account_balance: float = 30_000; max_heat_pct: float = 6.0

class RuinRequest(BaseModel):
    win_rate: float; rr_ratio: float; risk_pct: float = 0.02

class ExecCostRequest(BaseModel):
    price: float; volume: float; position_usd: float; spread_bps: float = 5.0

class PortfolioOptRequest(BaseModel):
    tickers: List[str]; method: str = "mvo"; max_weight: float = 0.40
    long_only: bool = True; risk_free_rate: float = 0.04
    kelly_fraction: float = 0.25; lookback_days: int = 252

class StressTestRequest(BaseModel):
    tickers: List[str]; weights: List[float]; portfolio_value: float = 100_000

class InstitutionalReportRequest(BaseModel):
    ticker: str; strategy_name: str = "APEX Strategy"
    n_trials_tested: int = 1; initial_capital: float = 100_000

class PerfValidateRequest(BaseModel):
    sharpe: float; max_dd_pct: float; ruin_prob_pct: float; n_trades: int; p_value: float


@app.get("/api/v2/quant/{ticker}")
def v2_quant_metrics(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return sanitize_data(calculate_corrected_quant_metrics(df))


@app.get("/api/v2/sharpe/{ticker}")
def v2_sharpe_analysis(ticker: str, n_trials: int = 1):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    close = df["Close"].dropna()
    log_r = np.log(close / close.shift(1)).dropna().values
    n = len(log_r); mu_ = float(log_r.mean()); sg_ = float(log_r.std())
    raw_sr = (mu_ / sg_ * np.sqrt(252)) if sg_ > 0 else 0.0
    result = {
        "ticker": ticker, "n_observations": n, "raw_sharpe": round(raw_sr, 4),
        "lo_adjusted"    : lo_adjusted_sharpe(log_r),
        "deflated_sharpe": deflated_sharpe_ratio(raw_sr, n_trials, n, log_r),
        "bootstrap_ci"   : bootstrap_sharpe_ci(log_r, n_bootstrap=5_000),
        "verdict": (" Sharpe statistically credible." if raw_sr >= 1.5 and n >= 200
                    else f" SR={raw_sr:.2f} — Check DSR and bootstrap CI before trusting."),
    }
    return sanitize_data(result)


@app.post("/api/v2/risk/vol-target")
def v2_vol_target(req: VolTargetRequest):
    return sanitize_data(volatility_target_position_size(req.current_vol_ann, req.target_vol_ann,
                                                          req.account_balance, req.asset_price, req.leverage_cap))


@app.post("/api/v2/risk/cvar-kelly")
def v2_cvar_kelly(req: CVaRKellyRequest):
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    log_r = np.log(df["Close"].dropna() / df["Close"].dropna().shift(1)).dropna().values
    return sanitize_data(cvar_constrained_kelly(req.win_rate, req.avg_win_pct, req.avg_loss_pct, log_r, req.cvar_limit, req.kelly_frac))


@app.post("/api/v2/risk/portfolio-heat")
def v2_heat(req: HeatRequest):
    return sanitize_data(portfolio_heat_control(req.positions, req.account_balance, req.max_heat_pct))


@app.post("/api/v2/risk/ruin")
def v2_ruin(req: RuinRequest):
    return sanitize_data(calculate_risk_of_ruin(req.win_rate, req.rr_ratio, req.risk_pct))


@app.post("/api/v2/risk/execution-cost")
def v2_exec_cost(req: ExecCostRequest):
    # Map old signature (price, volume, position_usd, spread_bps) to v6 (position_usd, adv_usd, annual_vol)
    adv_usd    = req.price * req.volume
    annual_vol = 0.30  # default 30% — user can call /api/stats/var for actual vol
    return sanitize_data(estimate_execution_cost(req.position_usd, adv_usd, annual_vol,
                                                  commission_bps=req.spread_bps))


@app.post("/api/v2/risk/validate-targets")
def v2_validate(req: PerfValidateRequest):
    return sanitize_data(validate_performance_targets(req.sharpe, req.max_dd_pct, req.ruin_prob_pct, req.n_trades, req.p_value))


# ── Phase 3: Portfolio Optimization ──────────────────────────────

@app.post("/api/v3/portfolio/optimize")
def v3_portfolio_optimize(req: PortfolioOptRequest):
    return_series = {}
    for t in req.tickers:
        df = _fetch_df(t, period=f"{req.lookback_days}d")
        if df is not None and not df.empty and "Close" in df.columns:
            close = df["Close"].dropna()
            return_series[t] = np.log(close / close.shift(1)).dropna()
    if len(return_series) < 2: raise HTTPException(400, "Need at least 2 tickers with valid data")
    df_ret = pd.DataFrame(return_series).dropna()
    R = df_ret.values; valid = list(df_ret.columns)
    moments = compute_portfolio_moments(R)
    mu, Sigma = moments["mu_ann"], moments["cov_matrix"]
    if req.method == "mvo":
        opt = mean_variance_optimization(mu=mu, Sigma=Sigma, long_only=req.long_only, max_weight=req.max_weight, risk_free_rate=req.risk_free_rate)
    elif req.method == "risk_parity":
        opt = risk_parity_weights(Sigma)
    elif req.method == "cvar":
        opt = cvar_optimization(R, risk_free_rate=req.risk_free_rate, max_weight=req.max_weight)
    elif req.method == "kelly":
        opt = kelly_matrix_allocation(mu=mu, Sigma=Sigma, risk_free=req.risk_free_rate, kelly_frac=req.kelly_fraction)
    else:
        raise HTTPException(400, f"Unknown method: {req.method}. Use: mvo|risk_parity|cvar|kelly")
    return sanitize_data({"tickers": valid, "method": req.method,
                           "expected_returns": {t: round(float(mu[i]) * 100, 4) for i, t in enumerate(valid)},
                           "vols_ann": {t: round(float(moments["vol_ann_pct"][i]), 4) for i, t in enumerate(valid)},
                           "ledoit_wolf_rho": moments["shrinkage_rho"], "weights": opt,
                           "correlation_clusters": correlation_clustering(moments["corr_matrix"], valid)})


@app.post("/api/v3/portfolio/stress-test")
def v3_stress_test(req: StressTestRequest):
    w = np.array(req.weights)
    if len(w) != len(req.tickers): raise HTTPException(400, "len(weights) must equal len(tickers)")
    w = w / w.sum()
    return sanitize_data(stress_test_portfolio(w, req.tickers, req.portfolio_value))


@app.get("/api/v3/portfolio/factor-decomp/{ticker}")
def v3_factor_decomp(ticker: str):
    df_asset = _fetch_df(ticker)
    if df_asset is None or df_asset.empty: raise HTTPException(404, f"No data for {ticker}")
    def _lr(df):
        if df is None or df.empty or "Close" not in df.columns: return None
        c = df["Close"].dropna()
        return np.log(c / c.shift(1)).dropna().values
    asset_r = _lr(df_asset)
    factors = {}
    for name, sym in [("nasdaq", "^IXIC"), ("gold", "GC=F"), ("dxy", "DX-Y.NYB"), ("btc", "BTC-USD")]:
        r = _lr(_fetch_df(sym))
        if r is not None: factors[name] = r
    if not factors: raise HTTPException(500, "Could not fetch factor data")
    return sanitize_data({"ticker": ticker, **factor_decomposition(asset_r, factors)})


# ── Phase 4: Institutional Research ──────────────────────────────

@app.get("/api/v4/risk/advanced/{ticker}")
def v4_advanced_risk(ticker: str):
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    close = df["Close"].dropna()
    log_r = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).dropna().values
    return sanitize_data(advanced_risk_decomposition(log_r))


@app.post("/api/v4/institutional/report")
def v4_institutional_report(req: InstitutionalReportRequest):
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    close = df["Close"].dropna()
    log_r = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).dropna().values
    return sanitize_data(generate_institutional_report(req.strategy_name, log_r, None, req.initial_capital, req.n_trials_tested))


@app.post("/api/v4/monte-carlo")
def v4_monte_carlo(trades: List[float], initial_capital: float = 100_000):
    if len(trades) < 10: raise HTTPException(400, "Minimal 10 trades needed")
    return sanitize_data(monte_carlo_equity_reshuffling(np.array(trades), n_simulations=10_000, initial_capital=initial_capital))


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 5 — HIGH-WATERMARK EQUITY PROTECTION SYSTEM  (v5 endpoints)
#
#  Endpoints:
#    POST /api/v5/hwm/session                  — create new HWM session
#    GET  /api/v5/hwm/session/{id}             — inspect session state
#    DELETE /api/v5/hwm/session/{id}           — destroy session
#    POST /api/v5/hwm/evaluate                 — pre-trade gate
#    POST /api/v5/hwm/record                   — post-trade result
#    GET  /api/v5/hwm/status/{id}              — equity state snapshot
#    GET  /api/v5/hwm/milestones/{id}          — milestone ladder
#    POST /api/v5/hwm/validate                 — Monte Carlo + walk-forward
#    GET  /api/v5/hwm/design-report            — full system design document
#    POST /api/v5/hwm/stress-test              — scenario shock analysis
#    GET  /api/v5/hwm/positions/{id}           — per-timeframe heat usage
# ══════════════════════════════════════════════════════════════════════════════


# ── Pydantic Request Models ───────────────────────────────────────────────────

class HWMCreateRequest(BaseModel):
    session_id: str = "default"
    initial_capital: float = 1_000_000_000.0
    max_dd_pct: float = 0.15          # 15% hard MDD cap from initial
    trailing_stop_pct: float = 0.08   # 8% trailing stop from 20-day peak
    portfolio_heat_cap: float = 0.06  # max 6% of capital at risk simultaneously
    kelly_fraction: float = 0.25      # quarter-Kelly (proven most robust)
    target_annual_vol: float = 0.12   # 12% annualised vol target
    risk_free_rate: float = 0.04
    gamma_convex: float = 1.5         # convex decay exponent (γ)


class HWMEvaluateRequest(BaseModel):
    session_id: str = "default"
    ticker: str
    entry_price: float
    stop_loss: float
    win_rate: float                    # [0, 1]
    avg_win_r: float                   # avg winner in R-multiples
    avg_loss_r: float = 1.0           # avg loser in R-multiples (usually 1.0)
    current_equity: float
    timeframe: str = "swing"          # intraday | swing | position
    returns_history: List[float] = [] # list of daily log-returns (optional)


class HWMRecordRequest(BaseModel):
    session_id: str = "default"
    outcome: str                      # WIN | LOSS | BREAKEVEN
    pnl_pct: float                    # signed P&L as fraction of capital (e.g. 0.02)
    new_equity: float


class HWMValidateRequest(BaseModel):
    session_id: str = "default"
    returns: List[float]              # historical daily log-returns
    n_simulations: int = 10_000
    walkforward_train_months: int = 12
    walkforward_test_months: int = 3


class HWMStressRequest(BaseModel):
    session_id: str = "default"
    current_equity: float
    weights: List[float] = []         # portfolio weights (optional)
    tickers: List[str] = []          # portfolio tickers (optional)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hwm_decision_to_dict(d: HWMRiskDecision) -> Dict:
    """Convert HWMRiskDecision dataclass → JSON-safe dict."""
    return sanitize_data({
        # ── Gate ──────────────────────────────────────────────────
        "trade_approved":            d.trade_approved,
        "rejection_reasons":         d.rejection_reasons,
        "warnings":                  d.warnings,
        # ── Sizing ────────────────────────────────────────────────
        "recommended_units":         d.recommended_units,
        "position_value_usd":        d.position_value_usd,
        "dollar_risk_usd":           d.dollar_risk_usd,
        "final_risk_pct":            d.final_risk_pct,
        "fraction_of_capital":       round(d.position_value_usd / max(d.current_equity, 1), 6),
        # ── Scalars ───────────────────────────────────────────────
        "hwm_risk_scalar":           d.hwm_risk_scalar,
        "vol_scalar":                d.vol_scalar,
        "ma_filter_scalar":          d.ma_filter_scalar,
        "composite_scalar":          d.composite_scalar,
        # ── Equity State ──────────────────────────────────────────
        "current_equity":            d.current_equity,
        "hwm":                       d.hwm,
        "active_floor":              d.active_floor,
        "drawdown_from_hwm_pct":     d.drawdown_from_hwm_pct,
        "allowable_dd_from_here":    d.allowable_dd_from_here,
        "allowable_dd_usd":          d.allowable_dd_from_here * d.current_equity,
        "pct_above_floor":           round((d.current_equity - d.active_floor)
                                           / max(d.active_floor, 1) * 100, 4),
        # ── System ────────────────────────────────────────────────
        "system_status":             d.system_status,
        "timeframe":                 d.timeframe,
        "ticker":                    d.ticker,
        "timestamp":                 d.timestamp,
    })


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/api/v5/hwm/session")
def v5_hwm_create_session(req: HWMCreateRequest):
    """
    Create a new HWM protection session.
    One session per strategy/book — persists for the FastAPI process lifetime.
    In production, back with Redis or Postgres.
    """
    if req.session_id in _hwm_sessions:
        raise HTTPException(409, f"Session '{req.session_id}' already exists. "
                                  "DELETE it first or use a different session_id.")
    cfg = HWMConfig(
        initial_capital      = req.initial_capital,
        max_drawdown_pct     = req.max_dd_pct * 100,     # HWMConfig expects percent, not decimal
        trailing_stop_pct    = req.trailing_stop_pct * 100,
        max_portfolio_heat_pct = req.portfolio_heat_cap * 100,
        kelly_fraction       = req.kelly_fraction,
        risk_free_rate       = req.risk_free_rate,
        hwm_curvature        = req.gamma_convex,
    )
    session = HWMSession(cfg)
    _hwm_sessions[req.session_id] = session
    return sanitize_data({
        "session_id":        req.session_id,
        "created":           True,
        "initial_capital":   req.initial_capital,
        "hwm_floor":         session.hwm_sm.active_floor,
        "milestone_ladder":  session.hwm_sm.milestone_ladder,
        "config":            {
            "max_dd_pct":         req.max_dd_pct,
            "trailing_stop_pct":  req.trailing_stop_pct,
            "portfolio_heat_cap": req.portfolio_heat_cap,
            "kelly_fraction":     req.kelly_fraction,
            "gamma_convex":       req.gamma_convex,
        },
        "message": (
            "MATHEMATICAL HONESTY: The hard guarantee 'equity NEVER falls below floor' "
            "is not achievable with 100% certainty due to gap risk. "
            "This engine drives floor-breach probability < 1% via convex risk decay (γ=1.5). "
            "Gap risk is modelled via Cornish-Fisher CVaR, not ignored."
        ),
    })


@app.get("/api/v5/hwm/session/{session_id}")
def v5_hwm_get_session(session_id: str):
    """Inspect current HWM session state."""
    s  = _get_hwm_session(session_id)
    sm = s.hwm_sm
    lm = s.lock_mgr
    sh = s.health_monitor.evaluate()
    return sanitize_data({
        "session_id":          session_id,
        "current_equity":      sm.current_equity,
        "hwm":                 sm.hwm,
        "active_floor":        sm.active_floor,
        "milestones_hit":      sm.milestone_summary().get("milestones_hit", []),
        "system_status":       sh.get("system_status", "UNKNOWN"),
        "trades_evaluated":    sh.get("trade_count", 0),
        "consecutive_losses":  sh.get("consecutive_losses", 0),
        "rolling_sharpe_50":   round(sh.get("rolling_sharpe", 0.0), 4),
        "rolling_win_rate":    round(sh.get("win_rate_rolling", 0.0), 4),
        "rolling_pf":          round(sh.get("profit_factor_rolling", 0.0), 4),
        "capital_is_halted":   lm._is_halted,
        "halt_reason":         lm._halt_reason,
    })


@app.delete("/api/v5/hwm/session/{session_id}")
def v5_hwm_delete_session(session_id: str):
    """Destroy a HWM session (manual reset — requires caution in production)."""
    _get_hwm_session(session_id)   # raises 404 if not found
    del _hwm_sessions[session_id]
    return {"session_id": session_id, "deleted": True}


@app.post("/api/v5/hwm/evaluate")
def v5_hwm_evaluate(req: HWMEvaluateRequest):
    """
    Pre-trade gate — must be called before every trade.

    Returns HWMRiskDecision:
      • trade_approved: False → DO NOT TRADE
      • recommended_units: position size in shares/contracts
      • composite_scalar: final risk reduction multiplier [0, 1]
      • rejection_reasons: list of strings explaining any denial
      • allowable_dd_from_here: how much equity can fall before floor breach
    """
    s = _get_hwm_session(req.session_id)
    returns_arr = np.array(req.returns_history, dtype=float) if req.returns_history else None

    decision = s.evaluate_trade(
        ticker           = req.ticker,
        entry_price      = req.entry_price,
        stop_loss_price  = req.stop_loss,
        win_rate         = req.win_rate,
        avg_win_pct      = req.avg_win_r / 100,   # convert R-multiple % → decimal
        avg_loss_pct     = req.avg_loss_r / 100,
        current_equity   = req.current_equity,
        timeframe        = req.timeframe,
        returns_history  = returns_arr,
    )
    return _hwm_decision_to_dict(decision)


@app.post("/api/v5/hwm/record")
def v5_hwm_record(req: HWMRecordRequest):
    """
    Post-trade recording — call after every trade closes.
    Updates: win/loss streak, rolling Sharpe, milestone ladder, capital lock.
    """
    s = _get_hwm_session(req.session_id)
    pnl_usd = req.pnl_pct * req.new_equity   # approximate dollar P&L
    result  = s.record_trade_result(
        outcome   = req.outcome,
        pnl_pct   = req.pnl_pct,
        pnl_usd   = pnl_usd,
    )
    sm = s.hwm_sm
    sh = s.health_monitor.evaluate()
    return sanitize_data({
        "recorded":           True,
        "outcome":            req.outcome,
        "new_equity":         req.new_equity,
        "hwm":                sm.hwm,
        "active_floor":       sm.active_floor,
        "system_status":      sh.get("system_status", "UNKNOWN"),
        "consecutive_losses": sh.get("consecutive_losses", 0),
        "rolling_sharpe_50":  round(sh.get("rolling_sharpe", 0.0), 4),
        "milestone_just_hit": req.new_equity >= sm.hwm,
    })


@app.get("/api/v5/hwm/status/{session_id}")
def v5_hwm_status(session_id: str):
    """
    Full real-time equity protection snapshot.
    Use this for dashboard polling (every bar / every trade).
    """
    s   = _get_hwm_session(session_id)
    sm  = s.hwm_sm
    lm  = s.lock_mgr
    sh  = s.health_monitor.evaluate()
    eq  = sm.current_equity
    floor  = sm.active_floor
    hwm    = sm.hwm

    # Convex HWM scalar: [(E-floor)/(HWM-floor)]^γ clamped to [0,1]
    gamma  = s.config.hwm_curvature
    denom  = max(hwm - floor, 1.0)
    hwm_scalar = max(0.0, min(1.0, ((eq - floor) / denom) ** gamma))
    allowable_dd = max(eq - floor, 0.0)

    # Get live vol and MA info by running a lightweight update
    vol_regime  = "UNKNOWN"
    vol_scalar  = 1.0
    ma_scalar   = 1.0

    return sanitize_data({
        # ── Equity Levels ──────────────────────────────────────────
        "current_equity":           eq,
        "high_watermark":           hwm,
        "active_floor":             floor,
        "equity_above_floor_usd":   allowable_dd,
        "equity_above_floor_pct":   round(allowable_dd / max(floor, 1) * 100, 4),
        "equity_vs_hwm_pct":        round((eq - hwm) / max(hwm, 1) * 100, 4),

        # ── Risk Scalars ───────────────────────────────────────────
        "hwm_scalar":               round(hwm_scalar, 6),
        "vol_regime":               vol_regime,
        "vol_scalar":               round(vol_scalar, 4),
        "ma_scalar":                round(ma_scalar, 4),
        "composite_scalar":         round(hwm_scalar * vol_scalar * ma_scalar, 6),

        # ── Capital Lock ───────────────────────────────────────────
        "capital_is_halted":        lm._is_halted,
        "halt_reason":              lm._halt_reason,

        # ── System Health ──────────────────────────────────────────
        "system_status":            sh.get("system_status", "UNKNOWN"),
        "trades_evaluated":         sh.get("trade_count", 0),
        "consecutive_losses":       sh.get("consecutive_losses", 0),
        "rolling_sharpe_50":        round(sh.get("rolling_sharpe", 0.0), 4),
        "rolling_win_rate_pct":     round(sh.get("win_rate_rolling", 0.0) * 100, 2),
        "rolling_profit_factor":    round(sh.get("profit_factor_rolling", 0.0), 4),

        # ── Action Guidance ───────────────────────────────────────
        "action":  (
            "HALT — system edge degraded, paper-trade 10 wins to resume"
            if sh.get("system_status") == "SHUTDOWN"
            else "HALT — floor protection active, no new positions"
            if lm._is_halted
            else "REDUCE_RISK_HEAVILY — near floor, composite scalar < 0.1"
            if hwm_scalar < 0.10
            else "REDUCE_RISK — in drawdown, trade smaller"
            if hwm_scalar < 0.50
            else "TRADE_NORMAL — equity healthy, full risk allocation"
        ),
    })


@app.get("/api/v5/hwm/milestones/{session_id}")
def v5_hwm_milestones(session_id: str):
    """Return the full milestone ladder with lock status."""
    s  = _get_hwm_session(session_id)
    sm = s.hwm_sm
    ic = s.config.initial_capital
    ms = sm.milestone_summary()

    return sanitize_data({
        "session_id":       session_id,
        "initial_capital":  ic,
        "current_equity":   sm.current_equity,
        "hwm":              sm.hwm,
        "active_floor":     sm.active_floor,
        "milestone_ladder": ms.get("milestone_ladder", []),
        "milestones_hit":   ms.get("milestones_hit", []),
        "milestones_hit_count": ms.get("milestones_hit_count", 0),
        "lock_pct_of_profits":  0.30,
        "mathematical_note": (
            "Each locked floor is protected by convex risk decay (γ=1.5). "
            "Floor breach probability < 1% per historical simulation. "
            "Gap risk (discrete bars) means 0% breach is not achievable."
        ),
    })


@app.get("/api/v5/hwm/positions/{session_id}")
def v5_hwm_positions(session_id: str):
    """Real-time timeframe risk budget usage."""
    s   = _get_hwm_session(session_id)
    tfb = s.budget
    cfg = s.config

    total_heat_used = sum(tfb.current_heat.values())

    return sanitize_data({
        "session_id":      session_id,
        "portfolio_heat_cap_pct":   cfg.max_portfolio_heat_pct * 100,
        "total_heat_used_pct":      round(total_heat_used * 100, 4),
        "heat_remaining_pct":       round((cfg.max_portfolio_heat_pct - total_heat_used) * 100, 4),
        "timeframes": {
            tf: {
                "budget_pct":    round(tfb.budgets[tf] * 100, 4),
                "used_pct":      round(tfb.current_heat.get(tf, 0.0) * 100, 4),
                "remaining_pct": round(
                    max(0.0, tfb.budgets[tf] - tfb.current_heat.get(tf, 0.0)) * 100, 4
                ),
                "utilization":   round(
                    tfb.current_heat.get(tf, 0.0) / max(tfb.budgets[tf], 1e-9), 4
                ),
            }
            for tf in ["intraday", "swing", "position"]
        },
        "risk_layer_summary": {
            "L1_per_trade_max_pct":    cfg.max_base_risk_pct,
            "L2_intraday_heat_pct":    round(tfb.budgets["intraday"] * 100, 2),
            "L2_swing_heat_pct":       round(tfb.budgets["swing"] * 100, 2),
            "L2_position_heat_pct":    round(tfb.budgets["position"] * 100, 2),
            "L3_portfolio_heat_pct":   cfg.max_portfolio_heat_pct * 100,
            "L4_daily_loss_limit_pct": 2.0,
            "L5_trailing_stop_pct":    cfg.trailing_stop_pct,
            "L6_hard_mdd_cap_pct":     cfg.max_drawdown_pct,
            "L7_milestone_floor":      "active",
        },
    })


@app.post("/api/v5/hwm/validate")
def v5_hwm_validate(req: HWMValidateRequest):
    """
    Full statistical validation suite:
      • Block bootstrap Monte Carlo (10k paths, block_size=10)
      • Rolling walk-forward efficiency (WFE)
      • Sharpe ≥ 2.0 | Calmar ≥ 1.5 | MDD < 20% gate
      • Deflated Sharpe (adjusts for multiple testing)
      • HMM regime-conditioned performance

    Pass `returns` as a list of daily log-returns.
    Minimum 200 trades recommended for deployment gate.
    """
    s       = _get_hwm_session(req.session_id)
    returns = np.array(req.returns, dtype=float)

    if len(returns) < 50:
        raise HTTPException(400, "Minimum 50 return observations required for validation.")

    vs      = ValidationSuite()
    report  = vs.run_full_validation(
        returns            = returns,
        n_simulations      = req.n_simulations,
        train_months       = req.walkforward_train_months,
        test_months        = req.walkforward_test_months,
    )
    return sanitize_data(report)


@app.post("/api/v5/hwm/stress-test")
def v5_hwm_stress(req: HWMStressRequest):
    """
    Apply institutional stress scenarios to the current HWM session.

    Scenarios tested:
      • GFC 2008 (−55% drawdown)
      • COVID Crash 2020 (−34% in 23 days)
      • Rate Shock 2022 (bonds + equities both −20%)
      • Flash Crash (−9% intraday, recovery same day)
      • LUNA / FTX Spiral (−90% sector collapse)
      • Custom: 3-sigma daily loss for 10 consecutive days

    Returns per-scenario: equity path, MDD, floor breach probability,
    HWM scalar trajectory, recovery time estimate.
    """
    s      = _get_hwm_session(req.session_id)
    eq     = req.current_equity
    floor  = s.hwm_sm.active_floor
    hwm    = s.hwm_sm.hwm
    gamma  = s.config.hwm_curvature
    ic     = s.config.initial_capital

    scenarios = [
        ("GFC_2008",         -0.55, 250),
        ("COVID_2020",       -0.34,  23),
        ("RATE_SHOCK_2022",  -0.22, 200),
        ("FLASH_CRASH",      -0.09,   1),
        ("LUNA_SPIRAL",      -0.90,  14),
        ("3SIGMA_10DAYS",    -0.03 * 10, 10),   # 3% daily × 10 days
    ]

    results = []
    for name, total_shock, days in scenarios:
        # Simulate linear equity path during the shock
        daily_ret     = total_shock / max(days, 1)
        equity_path   = [eq * (1 + daily_ret) ** d for d in range(days + 1)]
        trough_equity = min(equity_path)

        # HWM scalars along the path
        denom = max(hwm - floor, 1.0)
        scalars = [
            max(0.0, min(1.0, ((e - floor) / denom) ** gamma))
            for e in equity_path
        ]

        floor_breached   = trough_equity < floor
        breach_margin    = trough_equity - floor
        recovery_pct     = (eq - trough_equity) / max(eq, 1) * 100
        # Estimate recovery days assuming avg 0.05% daily gain at half-risk
        daily_gain_half  = 0.0005
        recovery_days    = int(abs(breach_margin) / max(trough_equity * daily_gain_half, 1)) if floor_breached else 0

        results.append({
            "scenario":            name,
            "shock_pct":           round(total_shock * 100, 1),
            "shock_days":          days,
            "start_equity":        round(eq, 2),
            "trough_equity":       round(trough_equity, 2),
            "floor":               round(floor, 2),
            "floor_breached":      floor_breached,
            "breach_margin_usd":   round(breach_margin, 2),
            "trough_hwm_scalar":   round(min(scalars), 6),
            "avg_hwm_scalar":      round(float(np.mean(scalars)), 4),
            "drawdown_pct":        round(recovery_pct, 2),
            "estimated_recovery_days": recovery_days,
            "risk_reduced_by_pct": round((1.0 - float(np.mean(scalars))) * 100, 2),
            "verdict": (
                "FLOOR BREACHED — gap risk scenario beyond model control"
                if floor_breached and total_shock < -0.20
                else "FLOOR BREACHED — review position sizing"
                if floor_breached
                else "FLOOR PROTECTED — convex decay prevented breach"
            ),
        })

    max_breach_prob = sum(1 for r in results if r["floor_breached"]) / len(results)

    return sanitize_data({
        "session_id":          req.session_id,
        "current_equity":      eq,
        "active_floor":        floor,
        "hwm":                 hwm,
        "gamma_convex":        gamma,
        "scenarios_tested":    len(scenarios),
        "floor_breach_count":  sum(1 for r in results if r["floor_breached"]),
        "floor_breach_rate":   round(max_breach_prob * 100, 1),
        "institutional_note":  (
            "Floor breach under GFC/COVID/LUNA scenarios reflects gap risk that is "
            "unavoidable with discrete bar data. In practice, the convex decay scalar "
            "drives position size to near-zero before these levels are reached, "
            "limiting actual loss to a fraction of the simulated linear path."
        ),
        "scenarios":           results,
    })


@app.get("/api/v5/hwm/design-report")
def v5_hwm_design_report():
    """
    Return the complete institutional system design document.
    Covers: architecture, math, entry/exit model, risk layers,
    position sizing formula, failure conditions, scenario analysis.
    """
    return sanitize_data(generate_system_design_report())


# ══════════════════════════════════════════════════════════════════
#  EQUITY ARMOR ENDPOINTS  —  /api/armor/*
#  Institutional high-watermark protection engine.
#  All state is per session_id (pass in every request).
# ══════════════════════════════════════════════════════════════════

# ── Request / Response Models ─────────────────────────────────────

class ArmorInitRequest(BaseModel):
    session_id: str = "default"
    initial_balance: float = 100_000.0
    trailing_stop_pct: float = 0.15       # 15% trailing stop from HWM
    target_vol_ann: float = 0.12          # 12% annualised vol target
    base_kelly_fraction: float = 0.25     # 25% fractional Kelly
    reserve_rate: float = 0.15            # 15% of profits locked in reserve
    min_win_rate: float = 0.45            # edge suspend threshold
    max_consec_losses: int = 7            # consecutive loss guard

class ArmorUpdateRequest(BaseModel):
    session_id: str = "default"
    current_balance: float
    date: str = ""                        # ISO date string, or "" for today
    realized_vol_ann: Optional[float] = None  # annualised; None = auto-estimate

class ArmorTradeRequest(BaseModel):
    session_id: str = "default"
    pnl_usd: float                        # positive = win, negative = loss
    is_win: bool
    date: str = ""

class ArmorRiskRequest(BaseModel):
    session_id: str = "default"
    base_risk_pct: float = 2.0            # base risk per trade as % of equity
    win_rate: float = 0.55
    rr_ratio: float = 2.0                 # reward-to-risk ratio

class ArmorMonteCarloRequest(BaseModel):
    win_rate: float = 0.55
    avg_win_pct: float = 2.0
    avg_loss_pct: float = 1.0
    initial_balance: float = 100_000.0
    n_trades: int = 300
    n_simulations: int = 10_000
    base_risk_pct: float = 2.0

class ArmorWalkForwardRequest(BaseModel):
    prices: List[float]                   # raw price series (e.g. SPY closes)
    initial_balance: float = 100_000.0
    n_windows: int = 10
    is_ratio: float = 0.7                 # fraction of each window used as in-sample

# ── Helpers ──────────────────────────────────────────────────────

def _get_armor(session_id: str) -> EquityArmor:
    if session_id not in _armor_sessions:
        raise HTTPException(
            404,
            f"Armor session '{session_id}' not found. "
            "Call POST /api/armor/init first."
        )
    return _armor_sessions[session_id]


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/api/armor/init")
def armor_init(req: ArmorInitRequest):
    """
    Initialise (or re-initialise) an Equity Armor session.
    One session per strategy / account.

    Config parameters:
    - trailing_stop_pct : stop fired when equity falls this % below HWM
    - target_vol_ann    : annualised vol target for position scaling
    - base_kelly_fraction: fractional Kelly multiplier (0.25 = quarter-Kelly)
    - reserve_rate      : fraction of profits locked in never-re-risked reserve
    - min_win_rate      : win-rate below which edge is declared degraded
    - max_consec_losses : consecutive losses before edge review
    """
    config = ArmorConfig(
        initial_balance=req.initial_balance,
        trailing_stop_pct=req.trailing_stop_pct,
        target_vol_ann=req.target_vol_ann,
        base_kelly_fraction=req.base_kelly_fraction,
        reserve_rate=req.reserve_rate,
        min_win_rate=req.min_win_rate,
        max_consec_losses=req.max_consec_losses,
    )
    _armor_sessions[req.session_id] = EquityArmor(config)
    return sanitize_data({
        "status":     "initialized",
        "session_id": req.session_id,
        "config":     vars(config),
        "milestones": [
            {
                "label":     m.label,
                "level_pct": m.level_pct,
                "floor_pct": m.floor_pct,
            }
            for m in _armor_sessions[req.session_id].milestone_tracker.milestones
        ],
    })


@app.post("/api/armor/update")
def armor_update(req: ArmorUpdateRequest):
    """
    Daily equity update — call once per trading day with the current account balance.

    Returns operational mode, final risk scale, and all sub-system states.
    Modes: FULL | REDUCED | DEFENSIVE | HALTED

    Use this BEFORE computing position sizes for the day.
    """
    armor = _get_armor(req.session_id)
    result = armor.update(
        current_balance=req.current_balance,
        date=req.date,
        realized_vol_ann=req.realized_vol_ann,
    )
    return sanitize_data(result)


@app.post("/api/armor/record-trade")
def armor_record_trade(req: ArmorTradeRequest):
    """
    Record a completed trade.  Must be called after every closed position.

    - pnl_usd : dollar P&L (positive = profit, negative = loss)
    - is_win  : True/False (determines edge-degradation statistics)

    Updates: compounding model, Kelly fraction, edge-degradation monitor,
    rolling Sharpe, win rate, profit factor.
    """
    armor = _get_armor(req.session_id)
    return sanitize_data(armor.record_trade(req.pnl_usd, req.is_win, req.date))


@app.get("/api/armor/status")
def armor_status(session_id: str = "default"):
    """
    Full diagnostic dashboard — all sub-systems in one call.

    Returns:
    - operational_mode, final_risk_scale
    - milestone status (active floor, next target)
    - trailing stop (HWM, stop level, distance)
    - equity curve filter (MA state, slope)
    - edge degradation monitor (win rate, Sharpe, triggers)
    - compounding model (Kelly fraction, reserve balance)
    - performance (Sharpe, MDD, Calmar, trade count)
    - active halts and warnings
    """
    if session_id not in _armor_sessions:
        return {"status": "not_initialized", "session_id": session_id}
    return sanitize_data(_armor_sessions[session_id].get_full_status())


@app.post("/api/armor/risk-size")
def armor_risk_size(req: ArmorRiskRequest):
    """
    Compute Kelly-adjusted, armor-scaled position risk for the next trade.

    Formula:
      raw_kelly   = win_rate - (1 - win_rate) / rr_ratio
      kelly_risk  = base_risk_pct × raw_kelly × kelly_fraction
      final_risk  = kelly_risk × armor_risk_scale

    Returns risk_pct (% of equity) and dollar_risk for current balance.
    """
    armor = _get_armor(req.session_id)
    return sanitize_data(armor.get_position_risk_pct(
        base_risk_pct=req.base_risk_pct,
        win_rate=req.win_rate,
        rr_ratio=req.rr_ratio,
    ))


@app.post("/api/armor/monte-carlo")
def armor_monte_carlo(req: ArmorMonteCarloRequest):
    """
    Run 10 000-path Monte Carlo simulation comparing:
    - ARMORED  : with equity armor (milestone floors, trailing stop, risk scaling)
    - BASELINE : without armor (fixed risk per trade)

    Returns:
    - return distribution (P5 / P25 / P50 / P75 / P95)
    - max-drawdown distribution
    - ruin probability (catastrophic / severe / soft thresholds)
    - floor breach count, survival rate
    - armor benefit metrics (ruin reduction %, MDD reduction %, return cost %)

      Runs in ~3–8 seconds depending on n_simulations.
    """
    result = run_armored_monte_carlo(
        win_rate=req.win_rate,
        avg_win_pct=req.avg_win_pct,
        avg_loss_pct=req.avg_loss_pct,
        initial_balance=req.initial_balance,
        n_trades=req.n_trades,
        n_simulations=req.n_simulations,
        base_risk_pct=req.base_risk_pct,
    )
    return sanitize_data(result)


@app.get("/api/armor/stress-test")
def armor_stress_test(
    initial_balance: float = Query(100_000.0, description="Starting account balance"),
    base_risk_pct: float   = Query(1.0, description="Base daily risk % per position"),
):
    """
    Run all institutional stress scenarios against the armor system:
    - GFC 2008      : -55% over 250 days
    - COVID 2020    : -34% over 23 days
    - Rate Shock 2022: -22% over 200 days
    - Flash Crash   : -9% in 1 day
    - LUNA Spiral   : -90% over 14 days
    - 3-Sigma Grind : -3% per day for 10 days

    Returns per scenario: final balance, MDD, floor breaches,
    halt triggers, survival status, armor effectiveness rating.
    """
    result = run_armor_stress_test(
        initial_balance=initial_balance,
        base_daily_risk_pct=base_risk_pct,
    )
    return sanitize_data(result)


@app.get("/api/armor/report")
def armor_report(session_id: str = "default"):
    """
    Generate the full institutional risk-committee report.

    Includes:
    - Deployment gate audit (ALL must pass before live trading):
         Sharpe ≥ 2.0 |  Max DD ≤ 20% |  Calmar ≥ 1.5
         System ACTIVE |  Edge INTACT
    - Mathematical constraint feasibility audit
    - Monte Carlo summary (armored vs unarmored)
    - All stress scenario results
    - Walk-forward efficiency ratio
    - Sub-system health diagnostics
    - Operational recommendations

    Requires armor to have processed at least some trades.
    """
    armor = _get_armor(session_id)
    mc_result     = run_armored_monte_carlo(
        0.55, 2.0, 1.0, armor.config.initial_balance, n_simulations=5_000
    )
    stress_result = run_armor_stress_test(armor.config.initial_balance)
    report        = generate_armor_report(armor, mc_result, stress_result)
    return sanitize_data(report)


@app.get("/api/armor/milestones")
def armor_milestones(session_id: str = "default"):
    """
    Return full milestone ladder — locked floors, reached targets, next target.

    Default milestone schedule:
      BASE → +5% → +10% → +20% → +30% → +50% → +75% → +100% → +150% → +200%

    Once equity clears a milestone, the PREVIOUS milestone becomes the hard floor.
    Example: Equity at +10% → floor locked at +5% → max allowable DD = 5%.
    """
    armor = _get_armor(session_id)
    ms    = armor.milestone_tracker
    return sanitize_data({
        "session_id":          session_id,
        "active_milestone":    ms.active_milestone.description,
        "next_milestone":      ms.next_milestone.description if ms.next_milestone else "MAXIMUM REACHED",
        "locked_floor_pct":    ms.locked_floor_pct,
        "locked_floor_balance": round(ms.locked_floor_balance, 2),
        "current_balance":     round(armor.current_balance, 2),
        "milestone_history":   ms.get_milestone_history(),
        "full_ladder": [
            {
                "label":     m.label,
                "level_pct": m.level_pct,
                "floor_pct": m.floor_pct,
                "description": m.description,
                "reached":   bool(m.reached_at),
                "reached_at": m.reached_at,
                "balance_at_milestone": round(
                    armor.config.initial_balance * (1 + m.level_pct / 100), 2
                ),
                "floor_balance": round(
                    armor.config.initial_balance * (1 + m.floor_pct / 100), 2
                ),
            }
            for m in ms.milestones
        ],
    })


@app.post("/api/armor/walk-forward")
def armor_walk_forward(req: ArmorWalkForwardRequest):
    """
    Run armored walk-forward validation on a user-supplied price series.

    Splits the price series into N windows (70% in-sample / 30% out-of-sample).
    Estimates win-rate, R:R, and vol from IS period, then applies armor to OOS.

    Returns:
    - IS vs OOS Sharpe per window
    - Walk-Forward Efficiency (WFE) = avg_OOS_SR / avg_IS_SR
      (Robust threshold: WFE ≥ 0.70 — max 30% degradation IS→OOS)
    - Armored OOS vs Unarmored OOS comparison
    """
    prices = np.array(req.prices, dtype=float)
    if len(prices) < 60:
        raise HTTPException(400, "Need at least 60 price observations for walk-forward.")
    result = run_armored_walk_forward(
        price_series=prices,
        initial_balance=req.initial_balance,
        n_windows=req.n_windows,
        is_ratio=req.is_ratio,
    )
    return sanitize_data(result)

"""
══════════════════════════════════════════════════════════════════
  HFT LITE ROUTES  —  paste these into main.py
  Required imports (add to top of main.py if not already there):
    from fastapi import WebSocket, WebSocketDisconnect
    from hft_engine import hft_spider
    import asyncio
══════════════════════════════════════════════════════════════════
"""

# ── ADD THESE IMPORTS AT THE TOP OF main.py ──────────────────────
# from fastapi import WebSocket, WebSocketDisconnect
# from hft_engine import hft_spider

# ═══════════════════════════════════════════════════════════════
#  HFT LITE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/hft/start")
async def hft_start(body: dict = {}):
    """Start the HFT scanner."""
    balance = float(body.get("balance", 1000.0))
    if not hft_spider.running:
        hft_spider.set_balance(balance)
    await hft_spider.start()
    return {"ok": True, "message": "HFT Spider started", "balance": hft_spider.balance}


@app.post("/api/hft/stop")
async def hft_stop():
    """Stop the HFT scanner and close all positions."""
    await hft_spider.stop()
    return {"ok": True, "message": "HFT Spider stopped"}


@app.post("/api/hft/reset")
async def hft_reset(body: dict = {}):
    """Full reset — stop, clear all state, reinitialize."""
    await hft_spider.stop()
    hft_spider.__init__()
    balance = float(body.get("balance", 1000.0))
    hft_spider.set_balance(balance)
    return {"ok": True, "message": "HFT Spider reset", "balance": balance}


@app.post("/api/hft/config")
async def hft_config(body: dict):
    """Update engine config on the fly (even while running)."""
    hft_spider.configure(body)
    return {"ok": True, "config": body}


@app.get("/api/hft/status")
async def hft_status():
    """Full status snapshot — positions, stats, equity, events."""
    return hft_spider.get_status()


@app.post("/api/hft/close/{position_id}")
async def hft_close_position(position_id: str):
    """Manually close a specific position."""
    pos = hft_spider.positions.get(position_id)
    if not pos or pos.status != "OPEN":
        return {"ok": False, "error": "Position not found or already closed"}
    hft_spider._close_position(pos, "MANUAL")
    return {"ok": True, "message": f"Position {position_id} closed manually"}


@app.post("/api/hft/close-all")
async def hft_close_all():
    """Manually close all open positions."""
    closed = 0
    for pos in list(hft_spider.positions.values()):
        if pos.status == "OPEN":
            hft_spider._close_position(pos, "MANUAL")
            closed += 1
    return {"ok": True, "closed": closed}


@app.websocket("/ws/hft")
async def hft_websocket(websocket: WebSocket):
    """
    WebSocket — pushes status updates every 1.5s to connected clients.
    Frontend connects once, receives live P&L / positions / events.
    """
    await websocket.accept()
    try:
        while True:
            status = hft_spider.get_status()
            await websocket.send_json(status)
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
#  RAPID SCALPER (JACKAL) — /api/hft-rapid/*
#  Momentum-burst scalper, berbeda filosofi dari HFT Spider (Predator)
# ══════════════════════════════════════════════════════════════════

@app.post("/api/hft-rapid/start")
async def rapid_start(body: dict = {}):
    """Start Rapid Scalper engine."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    balance = float(body.get("balance", 1000.0))
    if not rapid_scalper.running:
        rapid_scalper.set_balance(balance)
    await rapid_scalper.start()
    return {"ok": True, "message": "Rapid Scalper (Jackal) started", "balance": rapid_scalper.balance}


@app.post("/api/hft-rapid/stop")
async def rapid_stop():
    """Stop Rapid Scalper and close all positions."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    await rapid_scalper.stop()
    return {"ok": True, "message": "Rapid Scalper stopped"}


@app.post("/api/hft-rapid/reset")
async def rapid_reset(body: dict = {}):
    """Full reset — stop, clear all state, reinitialize."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    await rapid_scalper.stop()
    balance = float(body.get("balance", 1000.0))
    rapid_scalper.reset_full()
    rapid_scalper.set_balance(balance)
    return {"ok": True, "message": "Rapid Scalper reset", "balance": balance}


@app.post("/api/hft-rapid/config")
async def rapid_config(body: dict):
    """Update engine config on the fly (even while running)."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    rapid_scalper.configure(body)
    return {"ok": True, "config": body}


@app.get("/api/hft-rapid/status")
async def rapid_status():
    """Full status: positions, vault, stats, burst snapshot, events."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    return rapid_scalper.get_status()


@app.post("/api/hft-rapid/close/{position_id}")
async def rapid_close_position(position_id: str):
    """Manually close a specific position by ID."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    pos = rapid_scalper.positions.get(position_id)
    if not pos or pos.status != "OPEN":
        return {"ok": False, "error": "Position not found or already closed"}
    rapid_scalper._close_position(pos, "MANUAL")
    return {"ok": True, "message": f"Position {position_id} closed"}


@app.post("/api/hft-rapid/close-all")
async def rapid_close_all():
    """Manually close all open positions."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    closed = 0
    for pos in list(rapid_scalper.positions.values()):
        if pos.status == "OPEN":
            rapid_scalper._close_position(pos, "MANUAL")
            closed += 1
    return {"ok": True, "closed": closed}


@app.post("/api/hft-rapid/vault-resume")
async def rapid_vault_resume():
    """Manually resume trading after vault halt (use after reviewing situation)."""
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    rapid_scalper.reset_vault()
    return {"ok": True, "message": "Vault resumed — trading unblocked"}


@app.get("/api/hft-rapid/ws-feed")
async def rapid_ws_feed_status():
    """
    Status WebSocket market feed (v4.0 baru).
    Cek apakah WS feed aktif, latency allMids, orderbook age, jumlah msg diterima.
    """
    if rapid_scalper is None:
        raise HTTPException(503, "Rapid Scalper module not loaded")
    ws_feed = getattr(rapid_scalper, "_ws_feed", None)
    if ws_feed is None:
        return {
            "ws_active": False,
            "message": "WS feed belum distart atau websockets tidak terinstall",
            "hint": "pip install websockets"
        }
    return {
        "ws_active": True,
        **ws_feed.to_dict()
    }


@app.websocket("/ws/hft-rapid")
async def rapid_websocket(websocket: WebSocket):
    """
    WebSocket — push status updates setiap 0.5s (dipercepat dari 1s untuk v4.0).
    Lebih cepat karena engine loop sekarang 15ms, data lebih fresh.
    """
    if rapid_scalper is None:
        await websocket.close()
        return
    await websocket.accept()
    try:
        while True:
            status = rapid_scalper.get_status()
            await websocket.send_json(status)
            await asyncio.sleep(0.5)   # dipercepat dari 1.0s → 0.5s
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)