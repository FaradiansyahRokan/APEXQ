"""
╔══════════════════════════════════════════════════════════════════╗
║               APEX QUANTUM COMMAND — main.py v3.0               ║
║         Institutional-Grade Quant Trading Intelligence           ║
╚══════════════════════════════════════════════════════════════════╝

Engine Registry:
  [EXISTING]
    quant_engine        → Sortino, VaR, MDD
    kelly_engine        → Position sizing, Kelly criterion
    stats_engine        → Z-Score, Monte Carlo, VaR/CVaR, Hurst
    ict_engine          → FVG, Order Block, Volume Profile, Liquidity, Structure
    risk_manager        → Circuit breaker, Pre-trade check, Trade journal
    price_analyzer      → Satin streaming AI
    macro_engine        → Cross-asset (DXY, Nasdaq, Gold)

  [NEW — Institutional Layer]
    regime_engine       → HMM, GARCH, Liquidity regime, Macro tagging
    factor_engine       → Momentum decay, VRP, Cross-asset factor, BTC dominance
    scenario_engine     → Historical replay, Custom shock, Tail risk report
    model_confidence_engine → Signal confidence, Model stability, Meta strategy
    data_quality_engine → Missing tick, Outlier, Spoof, Exchange anomaly
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np
import yfinance as yf
import json
import uvicorn

# ── Existing collectors ──
from app.collectors.market_collector import (
    get_binance_crypto_data, get_company_profile, get_global_indices,
    get_market_data, get_live_quote, get_ihsg_summary
)
from app.collectors.news_collector import get_smart_news, get_global_market_news
from app.collectors.fundamental_collector import get_fundamentals
from app.collectors.hyperliquid_collector import get_hl_crypto_data

# ── Existing engines ──
from app.engine.quant_engine import calculate_quant_metrics, calculate_technicals
from app.engine.kelly_engine import calculate_kelly, kelly_from_trade_history, calculate_position_size
from app.engine.stats_engine import (
    calculate_zscore_analysis, run_monte_carlo,
    calculate_var_cvar, detect_market_regime, get_full_statistics
)
from app.engine.ict_engine import (
    detect_fvg, detect_order_blocks, calculate_volume_profile,
    detect_liquidity_zones, detect_market_structure, get_ict_full_analysis
)
from app.engine.risk_manager import (
    pre_trade_check, record_trade, get_satin_status,
    trigger_circuit_breaker, release_lock, run_backtest, update_risk_rules
)
from app.engine.macro_engine import get_cross_asset_data, calculate_factor_lab

# ── NEW Institutional engines ──
from app.engine.regime_engine import (
    detect_hmm_regime, detect_vol_clustering, detect_liquidity_regime,
    tag_macro_regime, get_full_regime_analysis
)
from app.engine.factor_engine import (
    analyze_momentum_factor, calculate_vol_risk_premium,
    analyze_cross_asset_factor, analyze_btc_dominance_factor, get_factor_composite
)
from app.engine.scenario_engine import (
    replay_historical_scenario, simulate_custom_shock,
    generate_tail_risk_report, CRISIS_SCENARIOS
)
from app.engine.model_confidence_engine import (
    calculate_signal_confidence, calculate_model_stability,
    select_active_strategy, get_master_confidence_report
)
from app.engine.data_quality_engine import (
    detect_missing_ticks, detect_price_outliers,
    detect_volume_spoofing, detect_exchange_anomalies,
    generate_data_quality_report
)

# ── AI ──
from app.models.ai_analyzer import get_ai_analysis
from app.models.price_analyzer import get_satin_reasoning

from app.engine.screener_engine import run_screener, WATCHLISTS, SCORE_LEGEND

# ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title    = "APEX Quantum Command",
    description = "Institutional-Grade Quantitative Trading Intelligence Platform",
    version  = "3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════
#  HELPER: Fetch + Clean DataFrame
# ══════════════════════════════════════════════════════════════════

def _fetch_df(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """Ambil dataframe bersih untuk ticker apapun."""
    df = get_market_data(ticker, period=period)
    if df is not None and isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _fetch_crypto_df(ticker: str, tf: str = "1D"):
    """Auto-fallback: Binance → Hyperliquid."""
    df, chart_data, price, profile = get_hl_crypto_data(ticker, tf)
    if df is None or df.empty:
        df, chart_data, price, profile = get_binance_crypto_data(ticker, tf)
    return df, chart_data, price, profile


# ══════════════════════════════════════════════════════════════════
#  EXISTING ENDPOINTS (tidak diubah)
# ══════════════════════════════════════════════════════════════════

@app.get("/api/market-overview/{tf}")
def market_overview(tf: str):
    tf_map = {
        "1D": {"period": "1d",  "interval": "1m"},
        "1W": {"period": "5d",  "interval": "15m"},
        "1M": {"period": "1mo", "interval": "1h"},
        "1Y": {"period": "1y",  "interval": "1d"}
    }
    config = tf_map.get(tf, tf_map["1D"])
    try:
        asset = yf.Ticker("^JKSE")
        df    = asset.history(period=config["period"], interval=config["interval"])
        if df.empty: return {"error": "No data"}
        try:
            df.index = df.index.tz_convert('UTC') if df.index.tz else df.index.tz_localize('Asia/Jakarta').tz_convert('UTC')
        except Exception: pass
        open_price = df['Open'].iloc[0]
        history = [
            {"time": index.strftime('%Y-%m-%d') if tf == "1Y" else int(index.timestamp()), "value": float(row['Close'])}
            for index, row in df.iterrows()
        ]
        return {
            "ihsg"  : {"current": round(df['Close'].iloc[-1], 2), "open": round(open_price, 2), "high": round(df['High'].max(), 2), "history": history},
            "news"  : get_global_market_news(),
            "global": get_global_indices()
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/analyze/{ticker}")
def analyze_asset(ticker: str, tf: str = "1D"):
    is_crypto = ticker.endswith('-USD') or ticker.endswith('USDT')
    if is_crypto:
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

    return {
        "ticker"      : ticker.upper(),
        "profile"     : profile,
        "price"       : price,
        "metrics"     : calculate_quant_metrics(df, ticker),
        "news"        : get_smart_news(ticker, profile.get('full_name', ticker) if profile else ticker),
        "history"     : chart_data,
        "fundamentals": get_fundamentals(ticker, is_crypto),
        "ai_analysis" : "PENDING",
        "ai_reasoning": ""
    }


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 1: REGIME INTELLIGENCE ENGINE
# ══════════════════════════════════════════════════════════════════

@app.get("/api/regime/full/{ticker}")
def regime_full(ticker: str):
    """
    Full Market Regime Analysis:
    HMM state detection + GARCH vol clustering + Liquidity regime + Macro tagging.
    Output: active model recommendation + risk mode + sizing factor.
    """
    df           = _fetch_df(ticker)
    if df is None or df.empty:
        raise HTTPException(404, f"No data for {ticker}")
    cross_asset  = get_cross_asset_data()
    return get_full_regime_analysis(df, cross_asset_data=cross_asset)


@app.get("/api/regime/hmm/{ticker}")
def regime_hmm(ticker: str):
    """Hidden Markov Model regime: LOW_VOL_BULLISH / SIDEWAYS_CHOP / HIGH_VOL_BEARISH."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_hmm_regime(df)


@app.get("/api/regime/volatility/{ticker}")
def regime_vol(ticker: str):
    """GARCH(1,1) volatility clustering: ULTRA_LOW / LOW / NORMAL / HIGH / CRISIS."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_vol_clustering(df)


@app.get("/api/regime/liquidity/{ticker}")
def regime_liq(ticker: str):
    """Liquidity regime via Amihud illiquidity ratio + volume-price divergence."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_liquidity_regime(df)


@app.get("/api/regime/macro")
def regime_macro():
    """Macro regime tagging berdasarkan DXY, Nasdaq, Gold real-time."""
    cross_asset = get_cross_asset_data()
    return tag_macro_regime(cross_asset)


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 2: FACTOR RESEARCH LAB
# ══════════════════════════════════════════════════════════════════

@app.get("/api/factor/full/{ticker}")
def factor_full(ticker: str):
    """
    Full Factor Analysis:
    Momentum decay + VRP + Cross-asset sensitivity + Factor alpha score.
    """
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")

    # Fetch reference assets untuk cross-asset analysis
    df_nasdaq = _fetch_df("^IXIC")
    df_btc    = _fetch_df("BTC-USD")
    df_dxy    = _fetch_df("DX-Y.NYB")

    return get_factor_composite(df, cross_asset_dfs={
        "nasdaq": df_nasdaq, "btc": df_btc, "dxy": df_dxy
    })


@app.get("/api/factor/momentum/{ticker}")
def factor_momentum(ticker: str):
    """Momentum factor: ROC multi-timeframe, acceleration, vol-adjusted momentum, half-life."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return analyze_momentum_factor(df)


@app.get("/api/factor/vrp/{ticker}")
def factor_vrp(ticker: str):
    """Volatility Risk Premium: RV vs IV proxy, vol term structure, strategy recommendation."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return calculate_vol_risk_premium(df)


@app.get("/api/factor/btc-dominance")
def factor_btc_dom():
    """BTC Dominance factor — altcoin season detector."""
    # Fetch BTC dominance dari Yahoo Finance sebagai proxy
    df_dom = _fetch_df("BTC-USD")  # Proxy: gunakan BTC market data
    return analyze_btc_dominance_factor(None)  # No dominance data; returns guidance


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 3: CROSS-ASSET INTELLIGENCE (dari macro_engine yang sudah ada)
# ══════════════════════════════════════════════════════════════════

@app.get("/api/cross-asset/overview")
def cross_asset_overview():
    """
    Cross-Asset Intelligence Dashboard:
    DXY, Nasdaq, Gold — current state + trend + macro regime tagging.
    """
    cross_asset  = get_cross_asset_data()
    macro_regime = tag_macro_regime(cross_asset)
    return {
        "cross_asset_data": cross_asset,
        "macro_regime"    : macro_regime,
        "global_risk_score": _calculate_global_risk_score(cross_asset)
    }


@app.get("/api/cross-asset/sensitivity/{ticker}")
def cross_asset_sensitivity(ticker: str):
    """Seberapa besar aset ini dipengaruhi DXY, Nasdaq, dan BTC (beta & correlation)."""
    df_asset  = _fetch_df(ticker)
    df_nasdaq = _fetch_df("^IXIC")
    df_btc    = _fetch_df("BTC-USD")
    df_dxy    = _fetch_df("DX-Y.NYB")

    if df_asset is None or df_asset.empty:
        raise HTTPException(404, f"No data for {ticker}")

    return analyze_cross_asset_factor(df_asset, df_nasdaq, df_btc, df_dxy)


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 4: SCENARIO ENGINE
# ══════════════════════════════════════════════════════════════════

class ScenarioReplayRequest(BaseModel):
    current_price   : float
    scenario_key    : str        # e.g. "covid_crash_2020"
    account_balance : float = 30_000
    position_pct    : float = 10.0
    use_stop_loss   : bool  = True
    stop_loss_pct   : float = 5.0

class ShockSimRequest(BaseModel):
    ticker          : str
    shock_vol_sigma : float = 3.0
    shock_direction : str   = "DOWN"
    shock_duration  : int   = 5
    account_balance : float = 30_000
    position_pct    : float = 10.0

class TailRiskRequest(BaseModel):
    ticker          : str
    current_price   : float
    account_balance : float = 30_000
    position_pct    : float = 10.0


@app.get("/api/scenario/library")
def scenario_library():
    """List semua skenario historis yang tersedia untuk replay."""
    return {
        "scenarios": {
            k: {"name": v["name"], "description": v["description"], "duration_days": v["duration_days"], "key_stats": v["key_stats"]}
            for k, v in CRISIS_SCENARIOS.items()
        }
    }


@app.post("/api/scenario/replay")
def scenario_replay(req: ScenarioReplayRequest):
    """
    Replay krisis historis pada posisi saat ini.
    Lihat bagaimana saldo dan equity curve berubah selama event.
    """
    return replay_historical_scenario(
        current_price=req.current_price,
        scenario_key=req.scenario_key,
        account_balance=req.account_balance,
        position_pct=req.position_pct,
        use_stop_loss=req.use_stop_loss,
        stop_loss_pct=req.stop_loss_pct
    )


@app.post("/api/scenario/shock")
def scenario_shock(req: ShockSimRequest):
    """
    Custom shock simulation: inject N-sigma volatility spike ke data historis.
    Hitung dampak ke posisi dengan sizing saat ini.
    """
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    return simulate_custom_shock(
        df=df,
        shock_vol_sigma=req.shock_vol_sigma,
        shock_direction=req.shock_direction,
        shock_duration=req.shock_duration,
        account_balance=req.account_balance,
        position_pct=req.position_pct
    )


@app.post("/api/scenario/tail-risk")
def scenario_tail_risk(req: TailRiskRequest):
    """
    Jalankan SEMUA skenario sekaligus.
    Ranking dari skenario paling merusak hingga paling ringan.
    """
    df = _fetch_df(req.ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {req.ticker}")
    return generate_tail_risk_report(
        current_price=req.current_price,
        df=df,
        account_balance=req.account_balance,
        position_pct=req.position_pct
    )


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 5+6: MODEL CONFIDENCE + META STRATEGY
# ══════════════════════════════════════════════════════════════════

@app.get("/api/confidence/full/{ticker}")
def confidence_full(ticker: str, account_size: float = 30_000):
    """
    Master Confidence Report:
    Signal confidence + Model stability + Data quality + Active strategy selection.
    Output: Trade Gate (OPEN / RESTRICTED / CLOSED) + Active Strategy.
    """
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")

    # Gather inputs dari engine lain
    quant       = calculate_quant_metrics(df, ticker)
    ict         = get_ict_full_analysis(df)
    stats       = get_full_statistics(df, account_size=account_size)
    cross_asset = get_cross_asset_data()
    regime_full = get_full_regime_analysis(df, cross_asset)

    # Kelly dari return historis
    log_ret = (df['Close'].pct_change().dropna() * 100).tolist()
    kelly   = kelly_from_trade_history([{"pnl_pct": r} for r in log_ret[-252:]], account_balance=account_size)

    apex_score  = _calc_apex_score(quant, ict, stats)
    ict_bias    = ict.get("composite_bias", "NEUTRAL")
    kelly_edge  = kelly.get("edge_quality", "UNKNOWN")
    z_signal    = stats.get("zscore", {}).get("signal", "NEUTRAL")
    regime      = regime_full.get("composite_regime", {}).get("hmm_regime", "UNKNOWN")
    vol_regime  = regime_full.get("composite_regime", {}).get("vol_regime", "UNKNOWN")
    liq_regime  = regime_full.get("composite_regime", {}).get("liq_regime", "UNKNOWN")
    macro_regime = regime_full.get("composite_regime", {}).get("macro_regime", "UNKNOWN")
    prob_profit = stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50)
    sortino     = quant.get("sortino", 0)

    return get_master_confidence_report(
        df=df, apex_score=apex_score, ict_bias=ict_bias, kelly_edge=kelly_edge,
        zscore_signal=z_signal, regime=regime, vol_regime=vol_regime,
        liq_regime=liq_regime, macro_regime=macro_regime,
        prob_profit=prob_profit, sortino=sortino
    )


@app.get("/api/confidence/strategy/{ticker}")
def meta_strategy(ticker: str, account_size: float = 30_000):
    """
    Meta Strategy Selector — strategi mana yang AKTIF berdasarkan regime saat ini.
    Output: strategy name, entry/SL/TP logic, sizing factor.
    """
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")

    cross_asset  = get_cross_asset_data()
    regime_full  = get_full_regime_analysis(df, cross_asset)
    quant        = calculate_quant_metrics(df, ticker)
    ict          = get_ict_full_analysis(df)
    stats        = get_full_statistics(df, account_size=account_size)
    apex_score   = _calc_apex_score(quant, ict, stats)

    hmm    = regime_full.get("composite_regime", {}).get("hmm_regime", "UNKNOWN")
    vol_r  = regime_full.get("composite_regime", {}).get("vol_regime", "UNKNOWN")
    liq_r  = regime_full.get("composite_regime", {}).get("liq_regime", "UNKNOWN")
    macro_r = regime_full.get("composite_regime", {}).get("macro_regime", "UNKNOWN")

    return select_active_strategy(
        hmm_regime=hmm, vol_regime=vol_r, liq_regime=liq_r,
        macro_regime=macro_r, apex_score=apex_score, signal_confidence=50
    )


# ══════════════════════════════════════════════════════════════════
#  NEW LAYER 8: DATA QUALITY ENGINE
# ══════════════════════════════════════════════════════════════════

@app.get("/api/data-quality/{ticker}")
def data_quality(ticker: str, interval: str = "1D"):
    """
    Full Data Quality Report:
    Missing ticks + Price outliers + Volume spoof + Exchange anomaly.
    Output: composite quality score + cleaning recommendations.
    """
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return generate_data_quality_report(df, expected_interval=interval)


@app.get("/api/data-quality/outliers/{ticker}")
def data_outliers(ticker: str):
    """Deteksi outlier harga dengan Z-Score + IQR + OHLC consistency check."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_price_outliers(df)


@app.get("/api/data-quality/spoof/{ticker}")
def data_spoof(ticker: str):
    """Volume spoof/wash trade detection — flag high-vol no-price-move events."""
    df = _fetch_df(ticker)
    if df is None or df.empty: raise HTTPException(404, f"No data for {ticker}")
    return detect_volume_spoofing(df)


# ══════════════════════════════════════════════════════════════════
#  FLAGSHIP: APEX FULL INSTITUTIONAL ANALYSIS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/apex-institutional/{ticker}")
def apex_institutional(ticker: str, tf: str = "1D", account_size: float = 30_000):
    """
    🏛️ APEX INSTITUTIONAL INTELLIGENCE
    Semua 8 engine layer dalam satu endpoint.

    Output Structure:
      apex_score        → Composite signal score (0-100)
      regime            → HMM + GARCH + Liquidity + Macro
      factor            → Momentum + VRP + Cross-asset
      ict               → FVG + OB + VP + Liquidity zones
      statistics        → Z-Score + MC + VaR + Hurst
      kelly             → Edge quality + Position sizing
      confidence        → Signal confidence + Model stability + Active strategy
      data_quality      → Data integrity check
      signals           → All key signals aggregated
    """
    is_crypto  = ticker.endswith('-USD') or ticker.endswith('USDT')

    if is_crypto:
        df, _, price, profile = _fetch_crypto_df(ticker, tf)
    else:
        profile = get_company_profile(ticker)
        yf_tf_map = {
            "1m": {"period": "5d", "interval": "1m"}, 
            "15m": {"period": "60d", "interval": "15m"},
            "1H": {"period": "730d", "interval": "1h"}, 
            "1D": {"period": "1y", "interval": "1d"}
        }
        config = yf_tf_map.get(tf, {"period": "1y", "interval": "1d"})
        
        # 1. Download data sesuai Timeframe yang diminta
        df = yf.download(ticker, period=config["period"], interval=config["interval"], progress=False, auto_adjust=True)
        
        # 2. Bersihkan MultiIndex dari Yahoo Finance (PENTING!)
        if df is not None and not df.empty and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 3. Dapatkan harga real-time
        price = get_live_quote(ticker)

    if df is None or df.empty:
        raise HTTPException(404, f"No data for {ticker}")

    # ── Run all engines ──────────────────────────────────────────
    quant        = calculate_quant_metrics(df, ticker)
    ict          = get_ict_full_analysis(df)
    stats        = get_full_statistics(df, account_size=account_size)
    cross_asset  = get_cross_asset_data()
    regime       = get_full_regime_analysis(df, cross_asset)

    df_nasdaq    = _fetch_df("^IXIC")
    df_btc       = _fetch_df("BTC-USD")
    df_dxy       = _fetch_df("DX-Y.NYB")
    factor       = get_factor_composite(df, {"nasdaq": df_nasdaq, "btc": df_btc, "dxy": df_dxy})
    fundamentals = get_fundamentals(ticker, is_crypto)
    data_qual    = generate_data_quality_report(df)

    # Kelly
    log_ret      = (df['Close'].pct_change().dropna() * 100).tolist()
    kelly        = kelly_from_trade_history([{"pnl_pct": r} for r in log_ret[-252:]], account_balance=account_size)
    hmm_info = detect_hmm_regime(df)
    factor_lab_data = calculate_factor_lab(df, df_nasdaq)

    # Apex Score
    apex_score   = _calc_apex_score(quant, ict, stats)

    # Model Confidence + Strategy
    confidence   = get_master_confidence_report(
        df=df,
        apex_score=apex_score["score"],
        ict_bias=ict.get("composite_bias", "NEUTRAL"),
        kelly_edge=kelly.get("edge_quality", "UNKNOWN"),
        zscore_signal=stats.get("zscore", {}).get("signal", "NEUTRAL"),
        regime=regime.get("composite_regime", {}).get("hmm_regime", "UNKNOWN"),
        vol_regime=regime.get("composite_regime", {}).get("vol_regime", "UNKNOWN"),
        liq_regime=regime.get("composite_regime", {}).get("liq_regime", "UNKNOWN"),
        macro_regime=regime.get("composite_regime", {}).get("macro_regime", "UNKNOWN"),
        prob_profit=stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50),
        sortino=quant.get("sortino", 0)
    )

    # Key Signals Aggregation
    signals = {
        "quant_action"      : quant.get("action", "NEUTRAL"),
        "ict_bias"          : ict.get("composite_bias", "NEUTRAL"),
        "hmm_regime"        : regime.get("composite_regime", {}).get("hmm_regime", "UNKNOWN"),
        "vol_regime"        : regime.get("composite_regime", {}).get("vol_regime", "UNKNOWN"),
        "macro_regime"      : regime.get("composite_regime", {}).get("macro_regime", "UNKNOWN"),
        "active_model"      : regime.get("active_model", "UNKNOWN"),
        "zscore_signal"     : stats.get("zscore", {}).get("signal", "NEUTRAL"),
        "kelly_edge"        : kelly.get("edge_quality", "UNKNOWN"),
        "momentum_signal"   : factor.get("momentum_factor", {}).get("momentum_signal", "UNKNOWN"),
        "factor_alpha"      : factor.get("factor_alpha_score", 50),
        "trade_gate"        : confidence.get("final_trade_gate", "CLOSED"),
        "active_strategy"   : confidence.get("active_strategy", {}).get("active_strategy", "UNKNOWN"),
        "governance_score"  : confidence.get("governance_score", 0),
        "data_quality"      : data_qual.get("composite_quality_score", 0),
        "monte_carlo_profit": stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50),
        "regime_summary"    : regime.get("regime_summary", "")
    }

    return {
        "ticker"       : ticker.upper(),
        "price"        : price,
        "profile"      : profile,
        "apex_score"   : apex_score,
        "signals"      : signals,
        "quant"        : quant,
        "ict_analysis" : ict,
        "statistics"   : stats,
        "regime"       : regime,
        "factor"       : factor,
        "kelly"        : kelly,
        "confidence"   : confidence,
        "fundamentals" : fundamentals,
        "data_quality" : data_qual,
        "macro"        : cross_asset,
        "hmm_regime"   : hmm_info,
        "factor_lab"   : factor_lab_data,
    }


# ══════════════════════════════════════════════════════════════════
#  SATIN STREAMING (dari price_analyzer)
# ══════════════════════════════════════════════════════════════════

@app.get("/api/satin/stream/{ticker}")
async def satin_stream(ticker: str, tf: str = "1D", account_size: float = 30_000):
    """
    Satin AI streaming — baca apex_institutional data dan generate reasoning.
    """
    try:
        apex_data = apex_institutional(ticker, tf=tf, account_size=account_size)

        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
        return StreamingResponse(
            get_satin_reasoning(ticker, apex_data),
            media_type="text/plain",
            headers=headers
        )
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════
#  EXISTING ENDPOINTS: Kelly, Stats, ICT, Satin Risk, AI Synthesis
# ══════════════════════════════════════════════════════════════════

# (Semua endpoint dari main.py v2 tetap ada — dipotong untuk ringkas)
# /api/kelly/manual, /api/kelly/from-history, /api/kelly/position-size
# /api/stats/full/{ticker}, /api/stats/zscore, /api/stats/monte-carlo, /api/stats/var, /api/stats/regime
# /api/ict/full/{ticker}, /api/ict/fvg, /api/ict/orderblock, /api/ict/volume-profile, /api/ict/liquidity, /api/ict/structure
class KellyManualRequest(BaseModel):
    win_rate: float          # 0.0 - 1.0
    avg_win: float           # % profit rata-rata
    avg_loss: float          # % loss rata-rata
    fraction: float = 0.25   # Fractional Kelly safety
    account_balance: float = 30_000
    max_risk_pct: float = 2.0

class TradeHistoryRequest(BaseModel):
    trades: List[Dict[str, Any]]   # [{"pnl_pct": 2.5}, {"pnl_pct": -1.0}, ...]
    account_balance: float = 30_000
    fraction: float = 0.25

class PositionSizerRequest(BaseModel):
    entry_price: float
    stop_loss_price: float
    account_balance: float = 30_000
    risk_pct: float = 1.0
    leverage: float = 1.0
@app.post("/api/kelly/manual")
def kelly_manual(req: KellyManualRequest):
    return calculate_kelly(
        win_rate=req.win_rate,
        avg_win=req.avg_win,
        avg_loss=req.avg_loss,
        fraction=req.fraction,
        account_balance=req.account_balance,
        max_risk_pct=req.max_risk_pct
    )

@app.post("/api/kelly/from-history")
def kelly_history(req: TradeHistoryRequest):
    return kelly_from_trade_history(
        trades=req.trades,
        account_balance=req.account_balance,
        fraction=req.fraction
    )

@app.post("/api/kelly/position-size")
def position_sizer(req: PositionSizerRequest):
    return calculate_position_size(
        entry_price=req.entry_price,
        stop_loss_price=req.stop_loss_price,
        account_balance=req.account_balance,
        risk_pct=req.risk_pct,
        leverage=req.leverage
    )


# ══════════════════════════════════════════════════════════════════
#  NEW: STATISTICS & MONTE CARLO ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/stats/full/{ticker}")
def full_statistics(ticker: str, account_size: float = 30_000):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"Data tidak tersedia untuk {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return get_full_statistics(df, account_size=account_size)

@app.get("/api/stats/zscore/{ticker}")
def zscore_endpoint(ticker: str, window: int = 20):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return calculate_zscore_analysis(df, window=window)

@app.get("/api/stats/monte-carlo/{ticker}")
def monte_carlo_endpoint(
    ticker: str,
    days: int = 30,
    simulations: int = 10000,
    account_size: float = 30_000
):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return run_monte_carlo(df, days=days, simulations=simulations, account_size=account_size)

@app.get("/api/stats/var/{ticker}")
def var_endpoint(ticker: str, confidence: float = 0.95, horizon: int = 1, method: str = "historical"):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return calculate_var_cvar(df, confidence=confidence, horizon_days=horizon, method=method)

@app.get("/api/stats/regime/{ticker}")
def regime_endpoint(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return detect_market_regime(df)


# ══════════════════════════════════════════════════════════════════
#  NEW: ICT / SMC ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.get("/api/ict/full/{ticker}")
def ict_full(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return get_ict_full_analysis(df)

@app.get("/api/ict/fvg/{ticker}")
def fvg_endpoint(ticker: str, min_gap_pct: float = 0.1):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return detect_fvg(df, min_gap_pct=min_gap_pct)

@app.get("/api/ict/orderblock/{ticker}")
def ob_endpoint(ticker: str, lookback: int = 50):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return detect_order_blocks(df, lookback=lookback)

@app.get("/api/ict/volume-profile/{ticker}")
def volume_profile_endpoint(ticker: str, bins: int = 50):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return calculate_volume_profile(df, bins=bins)

@app.get("/api/ict/liquidity/{ticker}")
def liquidity_endpoint(ticker: str, tolerance_pct: float = 0.1):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return detect_liquidity_zones(df, tolerance_pct=tolerance_pct)

@app.get("/api/ict/structure/{ticker}")
def structure_endpoint(ticker: str):
    df = get_market_data(ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return detect_market_structure(df)
# /api/satin/status, /api/satin/pre-trade-check, /api/satin/record-trade, /api/satin/lock, /api/satin/unlock, /api/satin/backtest

# ══════════════════════════════════════════════════════════════════
#  NEW: SATIN RISK MANAGER ENDPOINTS
# ══════════════════════════════════════════════════════════════════

class PreTradeRequest(BaseModel):
    entry_price: float
    stop_loss_price: float
    position_size: float       # USD
    ticker: str
    direction: str = "LONG"    # LONG atau SHORT

class RecordTradeRequest(BaseModel):
    ticker: str
    direction: str
    entry: float
    exit_price: float
    size_usd: float
    notes: str = ""

class LockRequest(BaseModel):
    reason: str

class UnlockRequest(BaseModel):
    override_reason: str

class UpdateRulesRequest(BaseModel):
    rules: Dict[str, Any]

class BacktestRequest(BaseModel):
    ticker: str
    strategy_name: str = "ema_crossover" 
    initial_capital: float = 30_000
    risk_per_trade: float = 0.01
    commission_pct: float = 0.001


@app.get("/api/satin/status")
def satin_status():
    return get_satin_status()

@app.post("/api/satin/pre-trade-check")
def satin_pre_trade(req: PreTradeRequest):
    return pre_trade_check(
        entry_price=req.entry_price,
        stop_loss_price=req.stop_loss_price,
        position_size=req.position_size,
        ticker=req.ticker,
        direction=req.direction
    )

@app.post("/api/satin/record-trade")
def satin_record(req: RecordTradeRequest):
    return record_trade(
        ticker=req.ticker,
        direction=req.direction,
        entry=req.entry,
        exit_price=req.exit_price,
        size_usd=req.size_usd,
        notes=req.notes
    )

@app.post("/api/satin/lock")
def satin_lock(req: LockRequest):
    return trigger_circuit_breaker(req.reason)

@app.post("/api/satin/unlock")
def satin_unlock(req: UnlockRequest):
    return release_lock(req.override_reason)

@app.post("/api/satin/update-rules")
def satin_update_rules(req: UpdateRulesRequest):
    return update_risk_rules(req.rules)

@app.post("/api/satin/backtest")
def satin_backtest(req: BacktestRequest):
    df = get_market_data(req.ticker)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {req.ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    strategy_fn = _get_builtin_strategy(req.strategy_name)
    if strategy_fn is None:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy_name}")

    return run_backtest(
        df=df,
        strategy_fn=strategy_fn,
        initial_capital=req.initial_capital,
        risk_per_trade=req.risk_per_trade,
        commission_pct=req.commission_pct
    )


# ════════════════════════════════════════════════════════
#  BAGIAN B — TAMBAHKAN 3 ENDPOINT INI KE MAIN.PY
# ════════════════════════════════════════════════════════

@app.get("/api/screener/run")
def screener_run(
    markets   : str   = Query(default="IDX,US,CRYPTO",
                              description="Comma-separated: IDX, US, CRYPTO"),
    min_score : float = Query(default=0,
                              description="Filter minimum score 0-100"),
    workers   : int   = Query(default=8,
                              description="Jumlah thread paralel (max 12)")
):
    """
    ─────────────────────────────────────────────────────────────
    SATIN SCREENER — Auto-scan seluruh watchlist & ranking ticker

    Endpoint ini mem-paralel scan semua ticker di watchlist pilihan,
    menilai setiap ticker dari 5 dimensi kuantitatif, dan mengembalikan
    ranked list dari yang paling layak entry (SATIN_READY) ke bawah.

    Query Params:
      markets   → Pilih pasar: "IDX,US,CRYPTO" atau subset-nya
      min_score → Hanya tampilkan ticker dengan score ≥ nilai ini
      workers   → Jumlah thread paralel (lebih tinggi = lebih cepat)

    Returns:
      scan_metadata → Info durasi & total ticker yang di-scan
      summary       → Hitungan SATIN_READY / MARGINAL / REJECTED
      top_picks     → Best ticker per market
      satin_ready   → Semua ticker hijau (score ≥ 70)
      marginal      → Semua ticker kuning (50-69)
      ranked_list   → Full list terurut dari skor tertinggi
    ─────────────────────────────────────────────────────────────
    """
    market_list = [m.strip().upper() for m in markets.split(",") if m.strip()]
    workers     = min(max(workers, 1), 12)  # Clamp 1-12

    result = run_screener(
        markets    = market_list,
        min_score  = min_score,
        max_workers= workers
    )
    return result


@app.get("/api/screener/custom")
def screener_custom(
    tickers   : str   = Query(...,
                              description="Comma-separated ticker list, e.g. AAPL,BBCA.JK,BTC-USD"),
    min_score : float = Query(default=0)
):
    """
    ─────────────────────────────────────────────────────────────
    CUSTOM SCREENER — Scan daftar ticker buatan sendiri

    Gunakan endpoint ini jika kamu ingin screen ticker tertentu
    yang tidak ada di default watchlist, atau kamu punya shortlist
    sendiri yang mau di-rank.

    Contoh:
      GET /api/screener/custom?tickers=NVDA,AMD,AAPL,TSLA,GOOGL
      GET /api/screener/custom?tickers=BBCA.JK,BBRI.JK,TLKM.JK
      GET /api/screener/custom?tickers=BTC-USD,ETH-USD,SOL-USD
    ─────────────────────────────────────────────────────────────
    """
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(400, "Tidak ada ticker yang valid.")
    if len(ticker_list) > 50:
        raise HTTPException(400, "Maksimal 50 ticker per request.")

    result = run_screener(
        markets        = [],
        min_score      = min_score,
        custom_tickers = ticker_list
    )
    return result


@app.get("/api/screener/watchlist")
def screener_get_watchlist():
    """
    ─────────────────────────────────────────────────────────────
    WATCHLIST INFO — Lihat daftar ticker di setiap market

    Endpoint informatif untuk frontend: tampilkan daftar ticker
    apa saja yang akan di-scan sebelum screener dijalankan.
    Berguna untuk UI "Preview Watchlist" sebelum klik Scan.
    ─────────────────────────────────────────────────────────────
    """
    return {
        "watchlists"   : WATCHLISTS,
        "total_tickers": sum(len(v) for v in WATCHLISTS.values()),
        "score_legend" : SCORE_LEGEND
    }

from app.engine.portfolio_simulator import ( run_simulation, generate_json_report, SimulationConfig )

@app.post("/api/simulate")
async def simulate(config: SimulationConfig):
    """
    Quantum Portfolio Simulator Endpoint.
    Menerima konfigurasi simulasi dan mengembalikan hasil backtest 1 tahun.
    """
    result = run_simulation(config)
    return generate_json_report(result)

# ══════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _calc_apex_score(quant: Dict, ict: Dict, stats: Dict) -> Dict:
    """Hitung APEX composite score dari multi-engine output."""
    score = 50
    score += min(quant.get("sortino", 0) * 5, 15)
    bull_f = ict.get("bullish_factors", 0)
    bear_f = ict.get("bearish_factors", 0)
    score += max(-15, min((bull_f - bear_f) * 3, 15))
    regime = stats.get("regime", {}).get("market_regime", "RANDOM_WALK")
    if "TREND" in regime:  score += 10
    elif regime == "MEAN_REVERTING": score -= 5
    zsig = stats.get("zscore", {}).get("signal", "NEUTRAL")
    if "OVERSOLD"   in zsig: score += 7
    elif "OVERBOUGHT" in zsig: score -= 7
    score = max(0, min(100, score))
    verdict = "BULLISH" if score >= 70 else "BEARISH" if score <= 30 else "NEUTRAL"
    return {"score": round(score, 1), "verdict": verdict, "out_of": 100}


def _calculate_global_risk_score(cross_asset: Dict) -> Dict:
    """Synthetic Global Risk Score dari cross-asset data."""
    dxy_chg    = cross_asset.get("DXY",    {}).get("change_pct", 0)
    nasdaq_chg = cross_asset.get("NASDAQ", {}).get("change_pct", 0)
    gold_chg   = cross_asset.get("GOLD",   {}).get("change_pct", 0)

    # Risk-on = Nasdaq naik + DXY turun + Gold stabil
    risk_score = 50 + nasdaq_chg * 3 - dxy_chg * 2 - gold_chg * 1
    risk_score = max(0, min(100, risk_score))

    return {
        "global_risk_score": round(risk_score, 2),
        "label"            : "RISK_ON" if risk_score > 60 else "RISK_OFF" if risk_score < 40 else "NEUTRAL",
        "description"      : f"Score {risk_score:.1f}/100. {'Likuiditas global mengalir ke risk assets.' if risk_score > 60 else 'Likuiditas menarik diri dari risk assets.' if risk_score < 40 else 'Kondisi makro campuran.'}"
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
