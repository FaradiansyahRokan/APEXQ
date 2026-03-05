import feedparser
from datetime import datetime
import time
import urllib.parse # WAJIB ditambahkan untuk keamanan URL

def get_smart_news(ticker, full_name):
    is_idx = ticker.endswith('.JK')
    
    # 1. Tentukan Parameter Regional & Bahasa
    # hl = host language, gl = geographic location
    hl = "id" if is_idx else "en-US"
    gl = "ID" if is_idx else "US"
    ceid = "ID:id" if is_idx else "US:en"

    try:
        # 2. SUSUN QUERY CERDAS
        if ticker.startswith('^') or "Index" in full_name or "Composite" in full_name:
            # Jika Index (IHSG, S&P 500)
            if is_idx:
                query = f"berita+IHSG+hari+ini+market"
            else:
                query = f"{urllib.parse.quote(full_name)}+market+news"
        else:
            # Jika Saham Biasa (BBCA, NVDA, dll)
            if is_idx:
                clean_ticker = ticker.replace('.JK', '')
                # Ambil kata pertama nama perusahaan (e.g., "Bank Central Asia" -> "BCA")
                short_name = full_name.split(' ')[0]
                query = f"saham+{clean_ticker}+{urllib.parse.quote(short_name)}+investasi"
            else:
                clean_name = full_name.split(' ')[0]
                query = f"{urllib.parse.quote(clean_name)}+stock+market+news"

        # 3. TEMBAK RSS GOOGLE NEWS DENGAN PARAMETER DINAMIS
        # Perhatikan hl, gl, dan ceid yang sekarang fleksibel!
        rss_url = f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"
        
        feed = feedparser.parse(rss_url)
        
        formatted_news = []
        for entry in feed.entries[:10]:
            # Parsing waktu publikasi
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_time = int(time.mktime(entry.published_parsed))
            else:
                pub_time = int(time.time())

            formatted_news.append({
                "title": entry.title,
                "publisher": entry.source.get('title', 'Market News') if hasattr(entry, 'source') else 'Market News',
                "link": entry.link,
                "time": pub_time
            })
            
        return formatted_news
    
    except Exception as e:
        print(f" [NEWS ENGINE] Error fetching news for {ticker}: {str(e)}")
        return []

def get_global_market_news():
    try:
        query = urllib.parse.quote("IHSG Indonesia Stock Market Global Finance")
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
        news_list = []
        for entry in feed.entries[:5]:
            news_list.append({
                # Hapus .upper() di sini, biar Frontend (CSS) yang atur styling-nya
                "title": entry.title, 
                "source": entry.source.get('title', 'MARKET NEWS') if hasattr(entry, 'source') else 'MARKET NEWS',
                "link": entry.link,
                "time": entry.published 
            })
        return news_list
        
    except Exception as e:
        print(f" [NEWS ENGINE] Global News Error: {str(e)}")
        return []