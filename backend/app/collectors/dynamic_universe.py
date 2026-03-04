"""
╔══════════════════════════════════════════════════════════════════════╗
║           DYNAMIC UNIVERSE ENGINE — Auto Discovery v1.1             ║
║   Live Screener · Zero Manual Input · Self-Cleaning Watchlists      ║
╠══════════════════════════════════════════════════════════════════════╣
║  v1.1 FIXES:                                                         ║
║  ✅ SSL verify=False  (corporate proxy / firewall workaround)        ║
║  ✅ Wikipedia tanpa lxml  (html.parser / bs4 / regex fallback)       ║
║  ✅ IDX multi-endpoint  (3 URL dicoba + yfinance seed fallback)      ║
║  ✅ Hardcoded fallback lengkap jika SEMUA sumber gagal               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import requests
import urllib3
import pandas as pd
import yfinance as yf
import time, re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_SESSION = requests.Session()
_SESSION.verify = False
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════

_CACHE: Dict[str, dict] = {}
_CACHE_TTL_HOURS = 6

def _is_cache_valid(key):
    return key in _CACHE and datetime.now() - _CACHE[key]["at"] < timedelta(hours=_CACHE_TTL_HOURS)

def _set_cache(key, data):
    _CACHE[key] = {"data": data, "at": datetime.now()}

def _get_cache(key):
    return _CACHE[key]["data"]

# ══════════════════════════════════════════════════════════════════
#  CRYPTO
# ══════════════════════════════════════════════════════════════════

_BLACKLIST = {"USDT","USDC","BUSD","TUSD","USDP","DAI","FDUSD","PYUSD",
              "WBTC","WETH","WBNB","BTCUP","BTCDOWN","ETHUP","ETHDOWN","BTTC","LUNC"}

_CRYPTO_CATS = {
    "CRYPTO_MAJOR"      : ["BTC","ETH","BNB","SOL","XRP"],
    "CRYPTO_L1_ALT"     : ["ADA","AVAX","DOT","TRX","LINK","NEAR","ATOM","APT","SUI","INJ","TAO","SEI","TON"],
    "CRYPTO_L2_SCALING" : ["MATIC","ARB","OP","IMX","MNT","STX"],
    "CRYPTO_AI_DEPIN"   : ["RNDR","FET","WLD","FIL","AR","GRT","THETA"],
    "CRYPTO_MEME"       : ["DOGE","SHIB","PEPE","WIF","FLOKI","BONK"],
}
_COIN_CAT = {c: cat for cat, coins in _CRYPTO_CATS.items() for c in coins}


def _fetch_binance_top_crypto(top_n=20, min_vol=5_000_000):
    key = "binance_univ"
    if _is_cache_valid(key):
        print("📦 [UNIVERSE] Crypto from cache.")
        return _get_cache(key)

    print("🔄 [UNIVERSE] Fetching crypto from Binance...")
    try:
        r = _SESSION.get("https://api.binance.com/api/v3/ticker/24hr", timeout=15)
        r.raise_for_status()
        pairs = []
        for t in r.json():
            sym = t["symbol"]
            if not sym.endswith("USDT"): continue
            coin = sym[:-4]
            if coin in _BLACKLIST: continue
            vol = float(t.get("quoteVolume", 0))
            if vol < min_vol: continue
            pairs.append({"coin": coin, "vol": vol})
        pairs.sort(key=lambda x: x["vol"], reverse=True)
        print(f"   ✅ Binance: {len(pairs)} valid pairs")

        result = {cat: [] for cat in _CRYPTO_CATS}
        result["CRYPTO_TOP_VOLUME"] = []
        assigned = set()
        for p in pairs:
            cat = _COIN_CAT.get(p["coin"])
            if cat and len(result[cat]) < top_n:
                result[cat].append(f"{p['coin']}-USD")
                assigned.add(p["coin"])
        result["CRYPTO_TOP_VOLUME"] = [f"{p['coin']}-USD" for p in pairs[:50]]
        result["CRYPTO_OTHER"] = [f"{p['coin']}-USD" for p in pairs if p["coin"] not in assigned][:25]
        result["CRYPTO"] = list({t for sub in result.values() for t in sub})
        _set_cache(key, result)
        return result
    except Exception as e:
        print(f"⚠️ [UNIVERSE] Binance failed: {e}. Using hardcoded.")
        return _hardcoded_crypto()


def _fetch_hl_perps():
    key = "hl_perps"
    if _is_cache_valid(key): return _get_cache(key)
    try:
        r = _SESSION.post("https://api.hyperliquid.xyz/info", json={"type": "meta"}, timeout=10)
        coins = [u["name"] for u in r.json().get("universe", []) if u.get("name") and u["name"] not in _BLACKLIST]
        print(f"   ✅ Hyperliquid: {len(coins)} perp markets")
        _set_cache(key, coins)
        return coins
    except Exception as e:
        print(f"⚠️ [UNIVERSE] Hyperliquid failed: {e}")
        return []


def _get_crypto_universe(top_n=25, min_vol=5_000_000):
    result = _fetch_binance_top_crypto(top_n, min_vol)
    hl     = set(_fetch_hl_perps())
    if hl:
        confirmed = [t for t in result.get("CRYPTO_TOP_VOLUME", []) if t.replace("-USD","") in hl]
        result["CRYPTO_HL_CONFIRMED"] = confirmed
        print(f"   ✅ HL-confirmed: {len(confirmed)} coins")
    return result

# ══════════════════════════════════════════════════════════════════
#  US STOCKS
# ══════════════════════════════════════════════════════════════════

def _scrape_wiki_tickers(url, col_hints):
    """Scrape Wikipedia tanpa lxml — coba html5lib → bs4 → regex."""
    try:
        r = _SESSION.get(url, timeout=15)
        from io import StringIO
        for flavor in ("html5lib", "bs4", "lxml"):
            try:
                tbls = pd.read_html(StringIO(r.text), flavor=flavor)
                for tbl in tbls:
                    for hint in col_hints:
                        matches = [c for c in tbl.columns if hint.lower() in str(c).lower()]
                        if matches:
                            col = matches[0]
                            tks = tbl[col].dropna().astype(str).str.strip().tolist()
                            tks = [t.replace(".", "-") for t in tks if 1 < len(t) <= 5]
                            if len(tks) > 50: return tks
            except Exception:
                continue
    except Exception:
        pass
    # Regex fallback
    try:
        r    = _SESSION.get(url, timeout=15)
        hits = re.findall(r'<td[^>]*>([A-Z]{2,5})</td>', r.text)
        return list(dict.fromkeys(hits))[:500]
    except Exception:
        return []


def _fetch_sp500():
    key = "sp500"
    if _is_cache_valid(key): return _get_cache(key)
    print("🔄 [UNIVERSE] Fetching S&P 500 from Wikipedia...")
    tickers = _scrape_wiki_tickers(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        ["Symbol","Ticker"]
    )
    if len(tickers) < 100:
        print("   ⚠️  Wikipedia parse thin — using curated SP500 top 150")
        tickers = _sp500_hardcoded()
    print(f"   ✅ S&P 500: {len(tickers)} tickers")
    _set_cache(key, tickers)
    return tickers


def _fetch_ndx100():
    key = "ndx100"
    if _is_cache_valid(key): return _get_cache(key)
    print("🔄 [UNIVERSE] Fetching Nasdaq 100 from Wikipedia...")
    tickers = _scrape_wiki_tickers(
        "https://en.wikipedia.org/wiki/Nasdaq-100",
        ["Ticker","Symbol"]
    )
    if len(tickers) < 80:
        tickers = _ndx100_hardcoded()
    print(f"   ✅ Nasdaq 100: {len(tickers)} tickers")
    _set_cache(key, tickers)
    return tickers


def _yf_extract(data, ticker, metric):
    """Robust MultiIndex extractor — handles (metric, ticker) & (ticker, metric)."""
    try:
        if isinstance(data.columns, pd.MultiIndex):
            lvl0 = data.columns.get_level_values(0).unique()
            # Format: (metric, ticker)  e.g. data["Close"]["AAPL"]
            if metric in lvl0:
                return data[metric][ticker].dropna()
            # Format: (ticker, metric)  e.g. data["AAPL"]["Close"]
            if ticker in lvl0:
                return data[ticker][metric].dropna()
        else:
            return data[metric].dropna()
    except Exception:
        pass
    return pd.Series(dtype=float)


def _screen_us(tickers, top_n=60, min_vol=1_000_000):
    key = f"us_{top_n}"
    if _is_cache_valid(key):
        print("📦 [UNIVERSE] US stocks from cache.")
        return _get_cache(key)

    print(f"🔄 [UNIVERSE] Screening {len(tickers)} US stocks by turnover (top {top_n})...")
    scored = []

    # Batch kecil 100 — lebih stabil dari 500+ sekaligus
    batch_size = 100
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            raw = yf.download(
                batch if len(batch) > 1 else batch[0],
                period="5d", interval="1d",
                progress=False, auto_adjust=True,
            )
            if raw.empty:
                continue
            for t in batch:
                try:
                    vol = _yf_extract(raw, t, "Volume")
                    cls = _yf_extract(raw, t, "Close")
                    if vol.empty or cls.empty:
                        continue
                    av = float(vol.mean())
                    if av >= min_vol:
                        scored.append({"t": t, "to": av * float(cls.iloc[-1])})
                except Exception:
                    continue
        except Exception as e:
            print(f"   ⚠️ Batch {i//batch_size+1} error: {e}")
            continue
        time.sleep(0.2)

    scored.sort(key=lambda x: x["to"], reverse=True)
    top = [s["t"] for s in scored[:top_n]]
    if len(top) < 10:
        print("   ⚠️  Too few results → hardcoded fallback")
        return _us_hardcoded()

    _MAG7  = {"AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA"}
    _SEMI  = {"AMD","AVGO","TSM","QCOM","INTC","MU","ARM","SMCI","LRCX","AMAT"}
    _SAAS  = {"CRM","PLTR","SNOW","CRWD","PANW","ADBE","NFLX","SHOP","PYPL","NET","DDOG"}
    _CPRXY = {"MSTR","COIN","MARA","RIOT","CLSK","HOOD"}

    result = {
        "US_MAG7_TECH"    : [t for t in top if t in _MAG7],
        "US_SEMICONDUCTOR": [t for t in top if t in _SEMI],
        "US_GROWTH_SAAS"  : [t for t in top if t in _SAAS],
        "US_CRYPTO_PROXY" : [t for t in top if t in _CPRXY],
        "US_TOP_VOLUME"   : top,
        "US"              : top,
    }
    print(f"   ✅ US screened: {len(top)} stocks")
    _set_cache(key, result)
    return result


def _get_us_universe(top_n=60):
    combined = list(dict.fromkeys(_fetch_sp500() + _fetch_ndx100()))
    if not combined: return _us_hardcoded()
    return _screen_us(combined, top_n=top_n)


# ══════════════════════════════════════════════════════════════════
#  IDX
# ══════════════════════════════════════════════════════════════════

_IDX_SEED = [
    "BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","BRIS.JK","BTPS.JK","BNGA.JK","BBTN.JK",
    "NISP.JK","MEGA.JK","BJBR.JK","BJTM.JK","BNLI.JK",
    "ADRO.JK","PTBA.JK","ITMG.JK","HRUM.JK","BRMS.JK","DEWA.JK","BUMI.JK",
    "ESSA.JK","MEDC.JK","PGAS.JK","MDKA.JK","ANTM.JK","TINS.JK","INCO.JK",
    "UNVR.JK","ICBP.JK","INDF.JK","MYOR.JK","JPFA.JK","CPIN.JK","AMRT.JK",
    "MAPI.JK","ACES.JK","KLBF.JK","SIDO.JK","ULTJ.JK",
    "TLKM.JK","ISAT.JK","EXCL.JK","AKRA.JK","SMGR.JK","ASII.JK","UNTR.JK","JSMR.JK",
    "GOTO.JK","ARTO.JK","BUKA.JK","EMTK.JK","DCII.JK","MTDL.JK","BELI.JK",
    "BSDE.JK","CTRA.JK","LPKR.JK","PWON.JK",
    "BREN.JK","CUAN.JK","TPIA.JK","BRPT.JK","PGEO.JK","DOID.JK",
    "ERAA.JK","INKP.JK","PTMP.JK","ENRG.JK",
]

_IDX_URLS = [
    "https://www.idx.co.id/primary/TradingSummary/GetStockSummary?start=0&length=200&sortBy=FrequencyTotal&sortType=desc",
    "https://idx.co.id/primary/TradingSummary/GetStockSummary?start=0&length=200",
    "https://www.idx.co.id/umbraco/Surface/StockData/GetStockSummary?start=0&length=200&sortBy=FrequencyTotal&sortType=desc",
    "https://idx.co.id/umbraco/Surface/StockData/GetStockSummary?start=0&length=200",
]

def _fetch_idx(top_n=50):
    key = f"idx_{top_n}"
    if _is_cache_valid(key):
        print("📦 [UNIVERSE] IDX from cache.")
        return _get_cache(key)

    print("🔄 [UNIVERSE] Fetching IDX universe...")
    tickers = []

    # Try IDX API
    for url in _IDX_URLS:
        try:
            r = _SESSION.get(url, timeout=15)
            if r.status_code != 200: continue
            data   = r.json()
            stocks = data.get("data") or data.get("Data") or []
            if not stocks: continue
            scored = []
            for s in stocks:
                code = str(s.get("StockCode") or s.get("Code") or "").strip()
                if not code or len(code) > 5: continue
                freq = float(s.get("FrequencyTotal") or s.get("Frequency") or 0)
                vol  = float(s.get("VolumeTotal") or s.get("Volume") or 0)
                scored.append({"t": f"{code}.JK", "sc": freq * 0.6 + vol * 0.4})
            scored.sort(key=lambda x: x["sc"], reverse=True)
            tickers = [s["t"] for s in scored[:top_n]]
            if tickers:
                print(f"   ✅ IDX API: {len(tickers)} tickers")
                break
        except Exception:
            continue

    # yfinance seed fallback
    if len(tickers) < 10:
        print("   ⚠️  IDX API unavailable → validating seed list via yfinance...")
        tickers = _screen_idx_yf(_IDX_SEED, top_n)

    if not tickers:
        tickers = _IDX_SEED[:top_n]
        print(f"   ⚠️  Using full seed list: {len(tickers)} tickers")

    # Classify
    _BANKING = {"BBCA","BBRI","BMRI","BBNI","BRIS","BTPS","BNGA","BNLI","NISP","MEGA","BBTN","BJBR","BJTM"}
    _ENERGY  = {"ADRO","PTBA","ITMG","HRUM","BRMS","DEWA","BUMI","ESSA","MEDC","PGAS","MDKA","ANTM","TINS","INCO"}
    _CONSUMER= {"UNVR","ICBP","INDF","MYOR","JPFA","CPIN","AMRT","MAPI","ACES","KLBF","SIDO","ULTJ"}
    _INFRA   = {"TLKM","ISAT","EXCL","AKRA","SMGR","ASII","UNTR","JSMR"}
    _TECH    = {"GOTO","ARTO","BUKA","EMTK","DCII","MTDL","BELI","WIRG"}
    _HIGHVOL = {"BREN","CUAN","TPIA","BRPT","PGEO","DOID","PTMP","ENRG"}

    cats = {"IDX_BLUECHIP":[],"IDX_BANKING":[],"IDX_ENERGY":[],"IDX_CONSUMER":[],
            "IDX_INFRA_TELCO":[],"IDX_TECH_DIGITAL":[],"IDX_HIGH_VOL":[],"IDX_OTHER":[]}
    for i, t in enumerate(tickers):
        c = t.replace(".JK","")
        if c in _BANKING:   cats["IDX_BANKING"].append(t)
        elif c in _ENERGY:  cats["IDX_ENERGY"].append(t)
        elif c in _CONSUMER:cats["IDX_CONSUMER"].append(t)
        elif c in _INFRA:   cats["IDX_INFRA_TELCO"].append(t)
        elif c in _TECH:    cats["IDX_TECH_DIGITAL"].append(t)
        elif c in _HIGHVOL: cats["IDX_HIGH_VOL"].append(t)
        else:               cats["IDX_OTHER"].append(t)
        if i < 20: cats["IDX_BLUECHIP"].append(t)
    cats["IDX"] = tickers
    print(f"   ✅ IDX ready: {len(tickers)} tickers")
    _set_cache(key, cats)
    return cats


def _screen_idx_yf(seed, top_n):
    """Validasi IDX seed list via yfinance dengan batch kecil."""
    scored = []
    batch_size = 30  # IDX: batch lebih kecil, koneksi lebih lambat
    for i in range(0, len(seed), batch_size):
        batch = seed[i:i + batch_size]
        try:
            raw = yf.download(
                batch if len(batch) > 1 else batch[0],
                period="5d", interval="1d",
                progress=False, auto_adjust=True,
            )
            if raw.empty:
                continue
            for t in batch:
                try:
                    vol = _yf_extract(raw, t, "Volume")
                    cls = _yf_extract(raw, t, "Close")
                    if vol.empty:
                        continue
                    av = float(vol.mean())
                    if av > 50_000:
                        price = float(cls.iloc[-1]) if not cls.empty else 1.0
                        scored.append({"t": t, "to": av * price})
                except Exception:
                    continue
        except Exception as e:
            print(f"   ⚠️ IDX batch {i//batch_size+1} error: {e}")
            continue
        time.sleep(0.3)

    scored.sort(key=lambda x: x["to"], reverse=True)
    result = [s["t"] for s in scored[:top_n]]
    print(f"   ✅ IDX yfinance screened: {len(result)} tickers")
    return result


# ══════════════════════════════════════════════════════════════════
#  HARDCODED FALLBACKS
# ══════════════════════════════════════════════════════════════════

def _hardcoded_crypto():
    major = ["BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD"]
    alts  = ["ADA-USD","AVAX-USD","DOT-USD","LINK-USD","NEAR-USD","APT-USD","SUI-USD","INJ-USD","TAO-USD","TRX-USD"]
    l2    = ["MATIC-USD","ARB-USD","OP-USD","STX-USD","IMX-USD"]
    ai    = ["RNDR-USD","FET-USD","WLD-USD","GRT-USD","FIL-USD"]
    meme  = ["DOGE-USD","SHIB-USD","PEPE-USD","WIF-USD","FLOKI-USD","BONK-USD"]
    all_c = list(dict.fromkeys(major+alts+l2+ai+meme))
    return {"CRYPTO_MAJOR":major,"CRYPTO_L1_ALT":alts,"CRYPTO_L2_SCALING":l2,
            "CRYPTO_AI_DEPIN":ai,"CRYPTO_MEME":meme,"CRYPTO_TOP_VOLUME":all_c,"CRYPTO":all_c}


def _sp500_hardcoded():
    return ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AVGO","LLY","JPM",
            "V","UNH","XOM","MA","COST","JNJ","HD","PG","ABBV","AMD","MRK","BAC",
            "CRM","ORCL","CVX","WMT","KO","PEP","NFLX","TMO","ADBE","ACN","MCD",
            "TXN","CSCO","QCOM","AMAT","LRCX","MU","PANW","CRWD","PLTR","NET",
            "DDOG","SNOW","ZS","OKTA","SHOP","PYPL","COIN","HOOD","MSTR","MARA",
            "RIOT","CLSK","ARM","SMCI","GS","MS","BLK","C","V","MA","AXP","SPGI"]


def _ndx100_hardcoded():
    return ["AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AVGO","COST","NFLX",
            "AMD","ADBE","QCOM","CSCO","INTU","AMGN","AMAT","TXN","LRCX","ISRG",
            "PANW","CRWD","PLTR","NET","DDOG","SNOW","ZS","COIN","MSTR","PYPL",
            "SHOP","MELI","OKTA","WDAY","VEEV","ZM","DOCU","TEAM","HUBS","MDB",
            "ABNB","UBER","LYFT","DASH","RBLX","U","SPOT","ROKU"]


def _us_hardcoded():
    mag7  = ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA"]
    semi  = ["AMD","AVGO","TSM","QCOM","INTC","MU","ARM","SMCI","LRCX","AMAT"]
    saas  = ["CRM","PLTR","CRWD","PANW","ADBE","NFLX","NET","DDOG","SNOW","ZS"]
    cprxy = ["MSTR","COIN","MARA","RIOT","CLSK","HOOD"]
    all_u = list(dict.fromkeys(mag7+semi+saas+cprxy))
    return {"US_MAG7_TECH":mag7,"US_SEMICONDUCTOR":semi,"US_GROWTH_SAAS":saas,
            "US_CRYPTO_PROXY":cprxy,"US_TOP_VOLUME":all_u,"US":all_u}


# ══════════════════════════════════════════════════════════════════
#  MASTER BUILDER
# ══════════════════════════════════════════════════════════════════

def build_dynamic_watchlists(
    include_crypto=True, include_us=True, include_idx=True,
    crypto_top_n=25, us_top_n=60, idx_top_n=50,
    min_crypto_vol=5_000_000, verbose=True,
) -> Dict[str, List[str]]:
    if verbose:
        print(f"\n{'='*60}\n  DYNAMIC UNIVERSE ENGINE v1.1\n  Building live watchlists...\n{'='*60}")

    wl: Dict[str, List[str]] = {}

    if include_crypto:
        wl.update(_get_crypto_universe(crypto_top_n, min_crypto_vol))
    if include_us:
        wl.update(_get_us_universe(us_top_n))
    if include_idx:
        wl.update(_fetch_idx(idx_top_n))

    universal = []
    for src, n in [("CRYPTO_TOP_VOLUME", 10), ("US_TOP_VOLUME", 15), ("IDX_BLUECHIP", 10)]:
        if src in wl:
            universal += wl[src][:n]
    wl["UNIVERSAL"] = list(dict.fromkeys(universal))

    if verbose:
        total = sum(len(v) for v in wl.values())
        print(f"\n{'='*60}\n  DYNAMIC UNIVERSE READY  (total ticker-slots: {total})")
        for k, v in sorted(wl.items()):
            if v: print(f"  {k:<26}: {len(v):3d} tickers")
        print(f"{'='*60}\n")

    return wl


class UniverseRefreshScheduler:
    def __init__(self, refresh_hours=6):
        self._wl = {}
        self._h  = refresh_hours
        self._last = None

    def _stale(self):
        return self._last is None or datetime.now() - self._last > timedelta(hours=self._h)

    def refresh(self, **kw):
        self._wl   = build_dynamic_watchlists(**kw)
        self._last = datetime.now()

    def get_universe(self, key="UNIVERSAL"):
        if self._stale(): self.refresh()
        return self._wl.get(key, [])

    def get_all(self):
        if self._stale(): self.refresh()
        return self._wl


if __name__ == "__main__":
    wl = build_dynamic_watchlists(crypto_top_n=20, us_top_n=30, idx_top_n=30)
    for cat, tickers in sorted(wl.items()):
        if tickers:
            print(f"  {cat}: {tickers[:4]}{'...' if len(tickers)>4 else ''}")