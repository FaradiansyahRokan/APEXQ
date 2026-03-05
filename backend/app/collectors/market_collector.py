import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timezone

def get_market_data(ticker, period="1y"):
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except: return None

def get_company_profile(ticker):
    """Mencari identitas asli emiten agar pencarian berita akurat."""
    try:
        asset = yf.Ticker(ticker)
        info = asset.info
        return {
            "full_name": info.get('longName', ticker),
            "sector": info.get('sector', 'N/A'),
            "exchange": info.get('exchange', 'N/A'),
            "currency": info.get('currency', 'IDR' if '.JK' in ticker else 'USD')
        }
    except:
        return {"full_name": ticker, "sector": "N/A", "exchange": "N/A", "currency": "N/A"}

def get_live_quote(ticker):
    try:
        asset = yf.Ticker(ticker)
        hist = asset.history(period="1d")
        return float(hist['Close'].iloc[-1]) if not hist.empty else 0.0
    except: return 0.0

def get_ihsg_summary():
    try:
        # ^JKSE adalah simbol untuk IHSG
        asset = yf.Ticker("^JKSE")
        # Ambil data 1 hari dengan interval 5 menit untuk grafik area
        df = asset.history(period="1d", interval="1m")
        
        if df.empty: return None

        current_price = df['Close'].iloc[-1]
        high_price = df['High'].max()

        # Ambil TRUE open price dari fast_info (harga resmi bursa, bukan open candle pertama)
        try:
            open_price = float(asset.fast_info.open)
        except Exception:
            open_price = float(df['Open'].iloc[0])  # fallback

        # Format history untuk Lightweight Charts Area
        history = [
            {"time": int(t.timestamp()), "value": float(v)}
            for t, v in df['Close'].items()
        ]

        # FIX: Paksa titik pertama chart = harga open, supaya chart
        # selalu mulai tepat di garis OPEN, tidak loncat ke atas/bawah.
        if history:
            history[0]["value"] = open_price

        return {
            "current": round(current_price, 2),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "history": history
        }
    except:
        return None
    
def get_global_indices():
    tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq 100": "^NDX",
        "Dow Jones": "^DJI",
        "IHSG": "^JKSE"
    }
    
    results = []
    for name, sym in tickers.items():
        try:
            asset = yf.Ticker(sym)
            # Ambil data 5 hari terakhir biar dapet High/Low yang akurat
            hist = asset.history(period="1mo", interval="1d")
            
            if not hist.empty:
                latest = hist.iloc[-1]
                prev_day = asset.history(period="2d")
                
                # Hitung change %
                current_price = latest['Close']
                last_close = prev_day['Close'].iloc[0]
                change_pct = ((current_price - last_close) / last_close) * 100
                
                results.append({
                    "name": name,
                    "symbol": sym.replace("^", ""),
                    "price": round(current_price, 2),
                    "open": round(latest['Open'], 2), # INI YANG BIKIN KOSONG TADI
                    "high": round(hist['High'].max(), 2), # High tertinggi dalam 5 hari
                    "low": round(hist['Low'].min(), 2),   # Low terendah dalam 5 hari
                    "change": round(change_pct, 2),
                    # Format sparkline harus array of objects biar dibaca Lightweight Charts
                    "sparkline": [
                        {"time": int(t.timestamp()), "value": float(v)} 
                        for t, v in hist['Close'].tail(24).items()
                    ]
                })
        except Exception as e:
            print(f"Error fetching {sym}: {e}")
            continue
    return results

def get_binance_crypto_data(ticker, tf="1D"):
    symbol = ticker.replace('-USD', 'USDT').replace(' ', '').upper()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    tf_map = {"1m": "1m", "15m": "15m", "1H": "1h", "1D": "1d"}
    interval = tf_map.get(tf, "1d")

    try:
        print(f"🔄 [BINANCE] Mencoba mengambil data untuk: {symbol}")
        
        url_klines = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=300"
        res_klines = requests.get(url_klines, headers=headers)
        
        if res_klines.status_code != 200:
            return None, [], 0.0, {}

        klines_data = res_klines.json()
        chart_data = []
        df_rows = []
        
        for k in klines_data:
            ts_ms = int(k[0]) 
            
            # ─── PISAHKAN FORMAT 1D & INTRADAY ───
            if interval == "1d":
                date_obj = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                row_time = date_obj.strftime('%Y-%m-%d') # String untuk 1D
            else:
                row_time = int(ts_ms / 1000) # Angka murni untuk intraday
            
            row = {
                "time": row_time,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            }
            chart_data.append(row)
            
            # Gunakan ts_ms untuk pandas DataFrame
            df_rows.append({
                "Date": pd.to_datetime(ts_ms, unit='ms', utc=True),
                "Open": row["open"], "High": row["high"], 
                "Low": row["low"], "Close": row["close"], "Volume": row["volume"]
            })
            
        df = pd.DataFrame(df_rows).set_index("Date") if df_rows else None
        
        url_price = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        res_price = requests.get(url_price, headers=headers)
        live_price = float(res_price.json()['price']) if res_price.status_code == 200 else 0.0
        
        # Kamus nama
        base_coin = symbol.replace('USDT', '')
        crypto_names = {
            "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
            "BNB": "Binance Coin", "XRP": "Ripple", "DOGE": "Dogecoin",
            "ADA": "Cardano", "SHIB": "Shiba Inu", "PEPE": "Pepe",
            "HYPE": "Hyperliquid", "LINK": "Chainlink", "AVAX": "Avalanche"
        }
        real_name = crypto_names.get(base_coin, f"{base_coin} Token")
        
        profile = {
            "full_name": real_name,
            "sector": "Web3 & Crypto",
            "exchange": "Binance API",
            "currency": "USD",
            "data_source": "BINANCE"
        }
        
        return df, chart_data, live_price, profile

    except Exception as e:
        print(f"🚨 [BINANCE ENGINE] Exception fetching {ticker}: {e}")
        return None, [], 0.0, {}