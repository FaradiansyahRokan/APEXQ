import yfinance as yf
import pandas as pd
import numpy as np

def get_cross_asset_data():
    """Mengambil data DXY (Dollar), NASDAQ (Tech Beta), dan GOLD"""
    assets = {
        "DXY": "DX-Y.NYB",
        "NASDAQ": "^IXIC",
        "GOLD": "GC=F"
    }
    data = {}
    for name, ticker in assets.items():
        df = yf.download(ticker, period="60d", interval="1d", progress=False)
        if not df.empty:
            # FIX 1: Hancurkan MultiIndex kolom bawaan yfinance baru
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            current_val = df['Close'].iloc[-1]
            prev_val = df['Close'].iloc[-2]
            
            # FIX 2: Kalau masih berbentuk Series, paksa ambil angkanya saja
            if isinstance(current_val, pd.Series):
                current_val = current_val.iloc[0]
                prev_val = prev_val.iloc[0]

            change = ((current_val - prev_val) / prev_val) * 100
            data[name] = {
                "current": float(current_val),
                "change_pct": float(change),
                "trend": "UP" if change > 0 else "DOWN"
            }
    return data

def detect_hmm_regime(df):
    """
    Redirects to regime_engine.detect_hmm_regime() — the canonical HMM implementation.
    This avoids duplicate HMM with inconsistent state labeling (audit finding C4).
    """
    from app.engine.regime_engine import detect_hmm_regime as _regime_hmm
    return _regime_hmm(df)

def calculate_factor_lab(df, ticker_df_compare):
    """Factor Research: Momentum Decay & Correlation"""
    # FIX 3: Hancurkan MultiIndex di data pembanding (Nasdaq)
    if isinstance(ticker_df_compare.columns, pd.MultiIndex):
        ticker_df_compare.columns = ticker_df_compare.columns.get_level_values(0)
        
    # 1. Momentum Decay (ROC Acceleration)
    roc = df['Close'].pct_change(periods=10)
    momentum_accel = roc.diff()
    
    macel_val = momentum_accel.iloc[-1]
    if isinstance(macel_val, pd.Series):
        macel_val = macel_val.iloc[0]
    if pd.isna(macel_val):
        macel_val = 0.0
        
    # 2. Correlation with Nasdaq (Beta)
    # FIX ZONA WAKTU: Hapus timezone dari kedua data agar bisa digabungkan!
    close_asset = df['Close'].copy()
    close_nasdaq = ticker_df_compare['Close'].copy()

    if close_asset.index.tz is not None:
        close_asset.index = close_asset.index.tz_localize(None)
    if close_nasdaq.index.tz is not None:
        close_nasdaq.index = close_nasdaq.index.tz_localize(None)

    # Setelah timezone dibuang, baru selaraskan index tanggal
    df_aligned, nasdaq_aligned = close_asset.align(close_nasdaq, join='inner')
    corr = df_aligned.corr(nasdaq_aligned)
    
    if pd.isna(corr):
        corr = 0.0

    return {
        "momentum_acceleration": "ACCELERATING" if macel_val > 0 else "DECAYING",
        "market_beta_nasdaq": float(corr),
        "risk_mode": "RISK_ON" if corr > 0.5 else "IDIOSYNCRATIC"
    }