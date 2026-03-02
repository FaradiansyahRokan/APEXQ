"""
╔══════════════════════════════════════════════════════════════════╗
║             HYPERLIQUID NATIVE DATA COLLECTOR                    ║
║   Direct L1 Data Feed · Klines · L2 Orderbook · Smart Money      ║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests
import pandas as pd
from datetime import datetime
import time

HL_INFO_URL = "https://api.hyperliquid.xyz/info"

def get_hl_klines(coin: str, interval: str = "1h", lookback_days: int = 30) -> pd.DataFrame:
    """
    Tarik data OHLCV langsung dari server L1 Hyperliquid.
    Interval support: "1m", "5m", "15m", "1h", "4h", "1d"
    """
    # Bersihkan nama koin (misal dari "BTC-USD" jadi "BTC")
    clean_coin = coin.replace('-USD', '').replace('USDT', '').strip().upper()
    
    end_time = int(time.time() * 1000)
    start_time = end_time - (lookback_days * 24 * 60 * 60 * 1000)

    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": clean_coin,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time
        }
    }

    try:
        response = requests.post(HL_INFO_URL, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return pd.DataFrame()

        # Parse data HL ke format standar APEX (Pandas DataFrame)
        df_data = []
        for candle in data:
            df_data.append({
                "Date": pd.to_datetime(candle["t"], unit="ms"),
                "Open": float(candle["o"]),
                "High": float(candle["h"]),
                "Low": float(candle["l"]),
                "Close": float(candle["c"]),
                "Volume": float(candle["v"])
            })

        df = pd.DataFrame(df_data)
        if not df.empty:
            df.set_index("Date", inplace=True)
            
        return df

    except Exception as e:
        print(f"Hyperliquid API Error for {clean_coin}: {e}")
        return pd.DataFrame()


def get_hl_crypto_data(ticker: str, tf: str = "1D"):
    """
    Fungsi jembatan (Adapter) agar Hyperliquid bisa langsung 
    menggantikan Binance di dalam main.py kamu.
    """
    # Mapping TF ke format HL
    tf_map = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1H": "1h",
        "1D": "1d"
    }
    hl_tf = tf_map.get(tf, "1d")
    lookback = 60 if hl_tf == "1d" else 7  # Intraday ambil 7 hari, Daily ambil 60 hari
    
    clean_coin = ticker.split('-')[0].upper()
    
    # 1. Tarik Data Klines
    df = get_hl_klines(clean_coin, interval=hl_tf, lookback_days=lookback)
    
    if df.empty:
        return None, [], 0, None

    # 2. Siapkan Chart Data untuk Frontend
    chart_data = []
    for index, row in df.iterrows():
        # HL timestamp format logic
        row_time = index.strftime('%Y-%m-%d') if hl_tf == "1d" else int(index.timestamp())
        chart_data.append({
            "time": row_time,
            "open": row["Open"],
            "high": row["High"],
            "low": row["Low"],
            "close": row["Close"],
            "volume": row["Volume"]
        })

    current_price = df["Close"].iloc[-1]

    # 3. Siapkan Profile Mockup
    profile = {
        "full_name": f"{clean_coin} Perpetual (Hyperliquid L1)",
        "sector": "Web3 / DeFi",
        "exchange": "HYPERLIQUID",
        "currency": "USD",
        "data_source": "HYPERLIQUID"
    }

    return df, chart_data, current_price, profile