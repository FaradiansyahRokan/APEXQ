from ollama import Client

client = Client(host='http://localhost:11434')
MODEL = 'deepseek-r1:8b' 

def get_ai_analysis(news_list, ticker, profile):
    """Satu fungsi untuk mendapatkan Sentiment dan Reasoning sekaligus."""
    if not news_list:
        return "NEUTRAL", "No significant news signals detected for analysis."
    
    headlines = "\n- ".join([n['title'] for n in news_list[:5]])
    
    prompt = f"""
    CONTEXT:
    Entity: {profile['full_name']} (Ticker: {ticker})
    Sector: {profile['sector']}
    Market: {profile['exchange']}

    HEADLINES:
    {headlines}

    TASK:
    Analyze market impact for {profile['full_name']}. 
    Provide:
    1. Sentiment: BULLISH, BEARISH, or NEUTRAL.
    2. Executive summary in 2 sentences.
    
    Format:
    SENTIMENT: [Label]
    REASONING: [Summary]
    """
    
    try:
        response = client.generate(model=MODEL, prompt=prompt)
        text = response['response']
        
        # Ekstraksi Label
        sentiment = "NEUTRAL"
        if "BULLISH" in text.upper(): sentiment = "BULLISH"
        elif "BEARISH" in text.upper(): sentiment = "BEARISH"
        
        # Ekstraksi Reasoning
        reasoning = text.split("REASONING:")[-1].strip() if "REASONING:" in text else text
        return sentiment, reasoning
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        return "NEUTRAL", "Neural engine connection timeout."