import numpy as np
import pandas as pd
from scipy.stats import norm

def calculate_quant_metrics(df, ticker):
    # Template data default jika terjadi error
    default = {"volatility": 0, "sortino": 0, "max_drawdown": 0, "var_95": 0, "action": "WAIT"}
    
    try:
        if df is None or df.empty:
            return default
        
        # Pastikan kolom Close ada
        if 'Close' not in df.columns:
            return default

        close_data = df['Close'].dropna()
        if len(close_data) < 10: # Minimal 10 hari data
            return default

        log_ret = np.log(close_data / close_data.shift(1)).dropna()
        if log_ret.empty: return default
        
        volatility = float(log_ret.std() * np.sqrt(252))
        mean_ret = float(log_ret.mean() * 252)

        # Sortino Ratio
        downside = log_ret[log_ret < 0]
        down_vol = float(downside.std() * np.sqrt(252))
        sortino = float((mean_ret - 0.05) / down_vol) if down_vol > 0 else 0.0

        # Max Drawdown
        rolling_max = close_data.cummax()
        drawdown = (close_data - rolling_max) / rolling_max
        mdd = float(drawdown.min() * 100)

        # VaR 95%
        var_95 = float(norm.ppf(0.05, loc=log_ret.mean(), scale=log_ret.std()) * 100)

        return {
            "volatility": round(volatility, 4),
            "sortino": round(sortino, 2),
            "max_drawdown": round(mdd, 2),
            "var_95": round(var_95, 2),
            "action": "BULLISH" if sortino > 0.5 else "BEARISH" if sortino < -0.2 else "NEUTRAL"
        }
    except Exception as e:
        print(f"Quant Engine Error: {e}")
        return default
    

def calculate_technicals(df):
    if df is None or df.empty: return {}
    
    # Ambil kolom Close
    close = df['Close']
    
    # 1. EMA (Exponential Moving Average)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    
    # 2. RSI (Relative Strength Index)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1+rs))
    
    return {
        "ema20": ema20.dropna().tolist(),
        "ema50": ema50.dropna().tolist(),
        "rsi": rsi.dropna().tolist(),
        "volume": df['Volume'].tolist(),
        "dates": df.index.strftime('%Y-%m-%d').tolist()
    }