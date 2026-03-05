import yfinance as yf

def get_fundamentals(ticker, is_crypto=False):

    try:
        yf_ticker = ticker.replace('USDT', '-USD').replace(' ', '') if is_crypto else ticker
        asset = yf.Ticker(yf_ticker)

        # ===== SAFE FETCH =====
        info = {}
        try:
            info = asset.get_info()
        except:
            try:
                info = dict(asset.fast_info)
            except:
                info = {}

        if not info or not isinstance(info, dict):
            return {
                "stats": {},
                "ownership": {}
            }

        # ===== STATS =====
        stats = {
            "market_cap": info.get("marketCap", 0),
            "volume_24h": info.get("regularMarketVolume", info.get("volume24Hr", 0)),
            "pe_ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else "N/A",
            "pb_ratio": round(info.get("priceToBook", 0), 2) if info.get("priceToBook") else "N/A",
            "eps": round(info.get("trailingEps", 0), 2) if info.get("trailingEps") else "N/A",
            "shares_outstanding": info.get("sharesOutstanding", 0),
            "float_shares": info.get("floatShares", 0),
        }

        # ===== OWNERSHIP =====
        insider_pct = info.get("heldPercentInsiders", 0) or 0
        inst_pct = info.get("heldPercentInstitutions", 0) or 0

        insider = round(insider_pct * 100, 2)
        institutions = round(inst_pct * 100, 2)

        public = max(0, round(100 - (insider + institutions), 2)) if (insider > 0 or institutions > 0) else 100

        ownership = {
            "insider": insider,
            "institutions": institutions,
            "public": public
        }

        return {
            "stats": stats,
            "ownership": ownership
        }

    except Exception as e:
        print(f" [FUNDAMENTAL ENGINE] Error fetching {ticker}: {e}")
        return {
            "stats": {},
            "ownership": {}
        }