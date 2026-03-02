import React, { useState, useEffect } from "react";
import axios from "axios";

import { FontInjector, GlobalStyles, Divider, formatPrice } from "./components/common/GlobalStyles";
import { Label }           from "./components/common/Label";
import { MetricCell }      from "./components/common/MetricCell";
import { NewsItem }        from "./components/common/NewsItem";
import { IndicatorButton } from "./components/common/IndicatorButton";
import { GlobalBar }       from "./components/dashboard/GlobalBar";
import { WatchlistCard }   from "./components/dashboard/WatchlistCard";
import { MacroIntelligence } from "./components/dashboard/MacroIntelligence";

import PriceChart     from "./components/PriceChart";
import MarketOverview from "./components/MarketOverview";
import KeyStats       from "./components/fundamentals/KeyStats";
import OwnershipBar   from "./components/fundamentals/OwnershipBars";
import Orderbook      from "./components/dashboard/OrderBook";
import AIAnalyst      from "./components/dashboard/AIAnalyst";
import Screener from "./components/dashboard/Screener"
import QuantumPortfolioSimulator from "./components/dashboard/QuantumPortfolioSimulator"

const API    = "http://localhost:8001";
const TICKERS = ["BBCA.JK", "BBRI.JK", "NVDA", "BTC-USD"];

// ─────────────────────────────────────────────────────────────────
//  Mini Loader
// ─────────────────────────────────────────────────────────────────
const Spinner = ({ size = 22, color = 'var(--gold)' }) => (
  <div style={{
    width: size, height: size,
    border: `1.5px solid var(--border2)`,
    borderTopColor: color,
    borderRadius: '50%',
  }} className="spin-icon" />
);

// ─────────────────────────────────────────────────────────────────
//  Apex Score Ring
// ─────────────────────────────────────────────────────────────────
const ApexRing = ({ score = 0, verdict = 'NEUTRAL' }) => {
  const r = 28;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color = score >= 70 ? 'var(--green)' : score <= 30 ? 'var(--red)' : 'var(--gold)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <svg width={72} height={72} style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
        <circle cx={36} cy={36} r={r} fill="none" stroke="var(--surface3)" strokeWidth={5} />
        <circle cx={36} cy={36} r={r} fill="none" stroke={color} strokeWidth={5}
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1s cubic-bezier(.22,1,.36,1)' }}
        />
      </svg>
      <div>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 5 }}>APEX Score</p>
        <p style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1, color, fontVariantNumeric: 'tabular-nums' }}>{score}</p>
        <span className={`badge ${score >= 70 ? 'badge-green' : score <= 30 ? 'badge-red' : 'badge-gold'}`} style={{ marginTop: 6, display: 'inline-flex' }}>{verdict}</span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
//  ICT / SMC Bias Indicator
// ─────────────────────────────────────────────────────────────────
const BiasGauge = ({ bull = 0, bear = 0, bias = 'NEUTRAL' }) => {
  const total  = bull + bear || 1;
  const bullPct = (bull / total) * 100;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--green)' }}>B {bull}</span>
        <span className={`badge ${bias === 'BULLISH' ? 'badge-green' : bias === 'BEARISH' ? 'badge-red' : 'badge-muted'}`}>{bias}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--red)' }}>R {bear}</span>
      </div>
      <div style={{ height: 4, background: 'var(--red-dim)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${bullPct}%`, background: 'var(--green)', borderRadius: 4, transition: 'width 1s ease' }} />
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
//  Section Header
// ─────────────────────────────────────────────────────────────────
const SectionHead = ({ label, badge, badgeType = 'badge-muted' }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 2, height: 14, background: 'var(--gold)', borderRadius: 2 }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ink2)' }}>{label}</span>
    </div>
    {badge && <span className={`badge ${badgeType}`}>{badge}</span>}
  </div>
);

// ─────────────────────────────────────────────────────────────────
//  Main App
// ─────────────────────────────────────────────────────────────────
export default function App() {
  const [ticker, setTicker]         = useState("");
  const [data, setData]             = useState({ news: [], history: [], metrics: {}, profile: {} });
  const [marketIndices, setMarketIndices] = useState({ global: [], news: [], ihsg: { history: [] } });
  const [loading, setLoading]       = useState(false);
  const [aiLoading, setAiLoading]   = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [hasSearched, setHasSearched]   = useState(false);
  const [settings, setSettings]     = useState({ showEma1: true, ema1: 20, showEma2: true, ema2: 50, showVol: true });
  const [marketTf, setMarketTf]     = useState("1D");
  const [chartTf, setChartTf]       = useState("1D");
  const [livePrice, setLivePrice]   = useState(null);
  const [liveCandle, setLiveCandle] = useState(null);
  const [apexData, setApexData]     = useState(null);
  const [satinStatus, setSatinStatus] = useState(null);
  const [activeView, setActiveView] = useState('home'); // 'home' | 'screener' | 'analysis'

// Handler: dipanggil ketika user klik "Analyze →" di dalam Screener
const handleScreenerAnalyze = (selectedTicker) => {
  setTicker(selectedTicker);
  setActiveView('analysis');
  fetchData(selectedTicker);  // langsung trigger fetch
};

  // ── Market home data ─────────────────────────────────────────
  useEffect(() => {
    if (hasSearched) return;
    axios.get(`${API}/api/market-overview/${marketTf}`)
      .then(r => setMarketIndices(r.data))
      .catch(() => {});
  }, [hasSearched, marketTf]);

  // ── WebSocket live price ──────────────────────────────────────
  useEffect(() => {
    let ws = null;
    setLivePrice(null); setLiveCandle(null);
    if (!data?.ticker) return;

    const src   = data?.profile?.data_source;
    const is1D  = chartTf === "1D";

    if (src === "HYPERLIQUID") {
      const coin = data.ticker.split("-")[0].toUpperCase();
      const ival  = { "1m":"1m","15m":"15m","1H":"1h","1D":"1d" }[chartTf] || "1d";
      ws = new WebSocket("wss://api.hyperliquid.xyz/ws");
      ws.onopen = () => ws.send(JSON.stringify({ method:"subscribe", subscription:{ type:"candle", coin, interval:ival } }));
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.channel === "candle" && msg.data) {
          const k = msg.data;
          const close = parseFloat(k.c);
          setLivePrice(close);
          setLiveCandle({ time: is1D ? new Date(k.t).toISOString().split('T')[0] : Math.floor(k.t/1000), open:parseFloat(k.o), high:parseFloat(k.h), low:parseFloat(k.l), close, volume:parseFloat(k.v) });
        }
      };
    } else if (src === "BINANCE") {
      const sym  = data.ticker.replace("-USD","usdt").toLowerCase();
      const ival = { "1m":"1m","15m":"15m","1H":"1h","1D":"1d" }[chartTf] || "1d";
      ws = new WebSocket(`wss://stream.binance.com:9443/ws/${sym}@kline_${ival}`);
      ws.onmessage = (e) => {
        const k = JSON.parse(e.data).k;
        const close = parseFloat(k.c);
        setLivePrice(close);
        const d = new Date(k.t);
        const time = is1D
          ? `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
          : Math.floor(k.t/1000);
        setLiveCandle({ time, open:parseFloat(k.o), high:parseFloat(k.h), low:parseFloat(k.l), close, volume:parseFloat(k.v) });
      };
    }
    return () => ws?.close();
  }, [data.ticker, data.profile?.data_source, chartTf]);

  // ── Fetch asset data ─────────────────────────────────────────
  const fetchData = async (overrideTicker, overrideTf) => {
    const t  = overrideTicker || ticker;
    const tf = overrideTf    || chartTf;
    if (!t) return;

    const isNew = t !== ticker || !hasSearched;
    if (isNew) {
      setLoading(true);
      setData({ news:[], history:[], metrics:{}, profile:{}, fundamentals:null });
      setApexData(null);
    } else {
      setChartLoading(true);
    }

    try {
      const [resAnalyze, resApex, resSatin] = await Promise.all([
        axios.get(`${API}/api/analyze/${t}?tf=${tf}`),
        axios.get(`${API}/api/apex-institutional/${t}?tf=${tf}`),
        axios.get(`${API}/api/satin/status`),
      ]);

      const asset = resAnalyze.data;
      const apex  = resApex.data;
      const satin = resSatin.data;

      // FIX: Handle error but do not return early before finally block!
      if (asset.error) { 
        alert(`Error from Server: ${asset.error}`); 
        // Reset view back to home if it fails on a new search
        if (isNew) {
           setActiveView('home'); 
           setHasSearched(false);
        }
        return; // Now it will jump to the finally block
      }

      if (!isNew) {
        asset.ai_analysis  = data.ai_analysis;
        asset.ai_reasoning = data.ai_reasoning;
        asset.news         = data.news;
        asset.fundamentals = data.fundamentals;
      } else {
        // Fallback checks in case apex data is missing
        asset.ai_analysis  = apex?.apex_score?.verdict || "NEUTRAL";
        asset.ai_reasoning = apex?.apex_score?.action || "No action data";
      }

      setData(asset);
      setApexData(apex);
      setSatinStatus(satin);
      setTicker(t);
      setHasSearched(true);
      setActiveView('analysis'); // Ensure we switch to analysis view on success
      
    } catch (e) {
      console.error("Fetch Error:", e);
      alert("Network or Server Error. Check console.");
      if (isNew) {
          setActiveView('home');
          setHasSearched(false);
      }
    } finally {
      // THIS WILL NOW ALWAYS EXECUTE
      setLoading(false);
      setChartLoading(false);
    }
  };

  const isBull    = data?.ai_analysis === "BULLISH";
  const isBear    = data?.ai_analysis === "BEARISH";
  const isCrypto  = data?.profile?.data_source === 'BINANCE' || data?.profile?.data_source === 'HYPERLIQUID';
  const apexScore = apexData?.apex_score?.score ?? 0;
  const apexVerd  = apexData?.apex_score?.verdict ?? 'NEUTRAL';
  const ictBias   = apexData?.ict_analysis?.composite_bias ?? 'NEUTRAL';
  const bullF     = apexData?.ict_analysis?.bullish_factors ?? 0;
  const bearF     = apexData?.ict_analysis?.bearish_factors ?? 0;

  // ─────────────────────────────────────────────────────────────
  //  HOME VIEW
  // ─────────────────────────────────────────────────────────────
  const renderHomeView = () => (
    <div style={{ paddingTop: 56, paddingBottom: 96 }}>
      {/* Ticker tape */}
      {marketIndices?.global?.length > 0 && (
        <div style={{ marginBottom: 72 }}>
          <GlobalBar indices={marketIndices.global} />
        </div>
      )}

      {/* Hero Search */}
      <div className="anim" style={{ marginBottom: 72 }}>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 20 }}>
          Asset Intelligence · IDX / NYSE / NASDAQ / Crypto
        </p>

        <div style={{ display: 'flex', alignItems: 'center', gap: 20, paddingBottom: 22, borderBottom: '1px solid var(--border2)', marginBottom: 24 }}>
          <input
            autoFocus
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && fetchData()}
            placeholder="TICKER"
            style={{
              flex: 1, background: 'none', border: 'none',
              fontFamily: 'var(--font)', fontSize: 68, fontWeight: 800,
              color: 'var(--ink)', letterSpacing: '-0.04em',
            }}
          />
          <button onClick={() => fetchData()} style={{
            background: 'var(--gold)', border: 'none', color: '#000',
            padding: '14px 36px', borderRadius: 10, fontSize: 13, fontWeight: 700,
            letterSpacing: '0.02em', flexShrink: 0,
            transition: 'opacity .15s ease',
          }}
          onMouseEnter={e => e.currentTarget.style.opacity = '.85'}
          onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
            Analyze
          </button>
        </div>

        {/* Quick tickers */}
        <div style={{ display: 'flex', gap: 8 }}>
          {TICKERS.map(t => (
            <button key={t} onClick={() => fetchData(t)} style={{
              background: 'none', border: '1px solid var(--border2)', borderRadius: 5,
              padding: '5px 14px', fontFamily: 'var(--mono)', fontSize: 9,
              letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)',
              transition: 'all .15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--gold)'; e.currentTarget.style.color = 'var(--gold)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border2)'; e.currentTarget.style.color = 'var(--ink3)'; }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Global Watchlist */}
      <div className="anim d1" style={{ marginBottom: 72 }}>
        <SectionHead label="Global Watchlist & Indices" badge="REAL-TIME" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 20 }}>
          {marketIndices?.global?.map(item => {
            const isIdx = ["GSPC","NDX","DJI","JKSE"].includes(item.symbol);
            return <WatchlistCard key={item.symbol} item={item} onClick={() => fetchData(isIdx ? `^${item.symbol}` : item.symbol)} />;
          })}
        </div>
      </div>

      <div className="gold-rule" style={{ marginBottom: 56 }} />

      {/* IHSG + News */}
      <div className="anim d2" style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 48 }}>
        {/* IHSG panel */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
            <div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 8 }}>IDX Composite · IHSG</p>
              <h2 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ink)', marginBottom: 16 }}>Jakarta Composite</h2>
              <div style={{ display: 'flex', gap: 4 }}>
                {["1D","1W","1M","1Y"].map(tf => (
                  <button key={tf} onClick={() => setMarketTf(tf)} style={{
                    background: marketTf === tf ? 'var(--gold)' : 'transparent',
                    color: marketTf === tf ? '#000' : 'var(--ink3)',
                    border: `1px solid ${marketTf === tf ? 'transparent' : 'var(--border2)'}`,
                    borderRadius: 5, padding: '4px 12px',
                    fontFamily: 'var(--mono)', fontSize: 9, fontWeight: marketTf === tf ? 600 : 400,
                    letterSpacing: '0.1em', transition: 'all .15s',
                  }}>{tf}</button>
                ))}
              </div>
            </div>
            {marketIndices?.ihsg && (
              <div style={{ textAlign: 'right' }}>
                <p style={{
                  fontSize: 42, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1,
                  color: marketIndices.ihsg.current > marketIndices.ihsg.open ? 'var(--green)' : 'var(--red)',
                  fontVariantNumeric: 'tabular-nums',
                }}>{marketIndices.ihsg.current?.toLocaleString()}</p>
                <div style={{ display: 'flex', gap: 16, justifyContent: 'flex-end', marginTop: 8 }}>
                  {[['H', marketIndices.ihsg.high], ['O', marketIndices.ihsg.open]].map(([l, v]) => (
                    <span key={l} style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', letterSpacing: '0.08em' }}>{l} {v?.toLocaleString()}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={{
            height: 400, background: 'var(--surface)', borderRadius: 12,
            border: '1px solid var(--border)', padding: 16, overflow: 'hidden', position: 'relative',
          }}>
            {marketIndices?.ihsg?.history?.length > 0 && (
              <MarketOverview data={marketIndices.ihsg.history} openPrice={marketIndices.ihsg.open} tf={marketTf} />
            )}
          </div>
        </div>

        {/* News sidebar */}
        <div>
          <SectionHead label="Intelligence Wire" />
          <div style={{ maxHeight: 420, overflowY: 'auto' }} className="scrollbar-hide">
            {(marketIndices?.news || []).slice(0, 8).map((n, i) => (
              <NewsItem key={i} title={n.title} publisher={n.source} time={n.time} link={n.link} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────────────────────
  //  LOADING SCREEN
  // ─────────────────────────────────────────────────────────────
  const renderLoadingScreen = () => (
    <div style={{ height: '85vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
      {/* Animated logo */}
      <div style={{ position: 'relative', width: 64, height: 64 }}>
        <svg width={64} height={64} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={32} cy={32} r={27} fill="none" stroke="var(--surface3)" strokeWidth={3} />
          <circle cx={32} cy={32} r={27} fill="none" stroke="var(--gold)" strokeWidth={3}
            strokeDasharray="42 128" strokeLinecap="round"
            style={{ animation: 'spin 1.2s linear infinite', transformOrigin: 'center' }}
          />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600, color: 'var(--gold)', letterSpacing: '0.04em' }}>AQ</span>
        </div>
      </div>
      <p style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--ink3)' }}>
        Gathering data for {ticker}…
      </p>
    </div>
  );

  // ─────────────────────────────────────────────────────────────
  //  ANALYSIS VIEW
  // ─────────────────────────────────────────────────────────────
  const renderAnalysisView = () => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 292px', gap: 40, paddingTop: 40, paddingBottom: 80 }}>

      {/* ════════════════════════════ LEFT COLUMN ════════════════════ */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>

        {/* 1 — ASSET HEADER */}
        <div className="anim">
          {/* Breadcrumb badges */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 22, flexWrap: 'wrap' }}>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, letterSpacing: '0.14em',
              textTransform: 'uppercase', background: 'var(--gold)', color: '#000',
              padding: '4px 14px', borderRadius: 5,
            }}>{data.ticker}</span>

            {data.profile?.data_source && (
              <span className={`badge ${data.profile.data_source === 'BINANCE' ? 'badge-gold' : 'badge-blue'}`}>
                {data.profile.data_source}
              </span>
            )}
            {data.profile?.sector && <span className="badge badge-muted">{data.profile.sector}</span>}
            {data.profile?.exchange && <span className="badge badge-muted">{data.profile.exchange}</span>}
            {data.profile?.full_name && (
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink3)' }}>{data.profile.full_name}</span>
            )}
          </div>

          {/* Price + controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 24 }}>

            {/* Price block */}
            <div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 8 }}>
                Real-Time Quote
              </p>
              <p style={{
                fontSize: 58, fontWeight: 800, letterSpacing: '-0.045em', lineHeight: 0.9,
                color: 'var(--ink)', fontVariantNumeric: 'tabular-nums',
              }}>
                {formatPrice(livePrice !== null ? livePrice : data.price, data.profile?.currency)}
              </p>
            </div>

            {/* Right controls */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 14 }}>

              {/* Sentiment badge */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                border: `1px solid ${isBull ? 'var(--green-b)' : isBear ? 'var(--red-b)' : 'var(--border2)'}`,
                background: isBull ? 'var(--green-dim)' : isBear ? 'var(--red-dim)' : 'var(--glass)',
                borderRadius: 100, padding: '6px 16px',
              }}>
                {aiLoading ? (
                  <><Spinner size={10} color="var(--ink3)" />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', letterSpacing: '0.14em' }}>SYNTHESIZING</span></>
                ) : (
                  <><span style={{ width: 7, height: 7, borderRadius: '50%', background: isBull ? 'var(--green)' : isBear ? 'var(--red)' : 'var(--ink3)', boxShadow: isBull ? '0 0 8px var(--green)' : isBear ? '0 0 8px var(--red)' : 'none' }} className="pulse-dot" />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.14em', color: isBull ? 'var(--green)' : isBear ? 'var(--red)' : 'var(--ink2)' }}>
                    {data.ai_analysis || 'NEUTRAL'}
                  </span></>
                )}
              </div>

              {/* TF + Indicators */}
              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <div style={{ display: 'flex', background: 'var(--surface2)', padding: 3, borderRadius: 8, border: '1px solid var(--border)', gap: 2 }}>
                  {["1m","15m","1H","1D"].map(tf => (
                    <button key={tf}
                      onClick={() => { setChartTf(tf); fetchData(data.ticker, tf); }}
                      style={{
                        background: chartTf === tf ? 'var(--gold)' : 'transparent',
                        color: chartTf === tf ? '#000' : 'var(--ink3)',
                        border: 'none', borderRadius: 6, padding: '5px 13px',
                        fontFamily: 'var(--mono)', fontSize: 10, fontWeight: chartTf === tf ? 600 : 400,
                        letterSpacing: '0.06em', transition: 'all .18s ease',
                      }}>{tf}</button>
                  ))}
                </div>

                <div style={{ width: 1, height: 22, background: 'var(--border2)' }} />

                <div style={{ display: 'flex', gap: 6 }}>
                  <IndicatorButton label="EMA 20" active={settings.showEma1} color="blue"   onClick={() => setSettings(s => ({ ...s, showEma1: !s.showEma1 }))} />
                  <IndicatorButton label="EMA 50" active={settings.showEma2} color="orange" onClick={() => setSettings(s => ({ ...s, showEma2: !s.showEma2 }))} />
                  <IndicatorButton label="Vol"    active={settings.showVol}  color="gold"   onClick={() => setSettings(s => ({ ...s, showVol: !s.showVol }))} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 2 — CHART */}
        <div className="anim d1 card" style={{ padding: '20px 20px 36px', position: 'relative' }}>
          {chartLoading && (
            <div style={{ position: 'absolute', inset: 0, zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(8,8,15,.7)', borderRadius: 14, backdropFilter: 'blur(4px)' }}>
              <Spinner size={32} />
            </div>
          )}
          <div style={{ height: 460, opacity: chartLoading ? 0.3 : 1, transition: 'opacity .2s' }}>
            {data.history?.length > 0 && (
              <PriceChart data={data.history} settings={settings} liveCandle={liveCandle} tf={chartTf} />
            )}
          </div>
        </div>

        {/* 3 — APEX SCORE + ICT BIAS ROW */}
        <div className="anim d2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Apex Score */}
          <div className="card card-gold" style={{ padding: 24, display: 'flex', alignItems: 'center', gap: 24 }}>
            <ApexRing score={apexScore} verdict={apexVerd} />
            <div style={{ flex: 1 }}>
              <div style={{ height: 1, background: 'var(--border2)', marginBottom: 12 }} />
              <div style={{ display: 'flex', justify: 'space-between', flexDirection: 'column', gap: 6 }}>
                {[
                  ['EV per Trade', `${(apexData?.kelly?.expected_value_pct ?? 0) > 0 ? '+' : ''}${(apexData?.kelly?.expected_value_pct ?? 0).toFixed(4)}%`, (apexData?.kelly?.expected_value_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'],
                  ['Kelly Edge',    apexData?.kelly?.edge_quality ?? '—',       'var(--gold)'],
                  ['Regime',        (apexData?.statistics?.regime?.market_regime ?? 'UNKNOWN').replace(/_/g,' '), 'var(--blue)'],
                ].map(([l, v, c]) => (
                  <div key={l} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>{l}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: c }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* SMC Bias */}
          <div className="card" style={{ padding: 24 }}>
            <SectionHead label="Smart Money Bias (ICT)" badge="LIVE" badgeType="badge-gold" />
            <BiasGauge bull={bullF} bear={bearF} bias={ictBias} />
            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                ['POC',    (apexData?.ict_analysis?.volume_profile?.poc_price ?? 0).toFixed(4)],
                ['Struct', (apexData?.ict_analysis?.market_structure?.market_structure ?? '—').replace(/_/g,' ')],
                ['FVG Count', apexData?.ict_analysis?.fvg_analysis?.total_fvgs ?? '—'],
                ['Liq Hunt', apexData?.ict_analysis?.liquidity_zones?.liquidity_bias ?? '—'],
              ].map(([l, v]) => (
                <div key={l} style={{ background: 'var(--surface2)', borderRadius: 6, padding: '8px 10px' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', marginBottom: 4, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{l}</p>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: 'var(--ink)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 4 — 8-METRIC QUANT GRID */}
        <div className="anim d2 card" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', overflow: 'hidden' }}>
          <MetricCell label="APEX Score"      value={apexScore}
            color={apexScore >= 70 ? 'green' : apexScore <= 30 ? 'red' : undefined}
            accent={apexScore >= 70 ? '#24D26D' : apexScore <= 30 ? '#F03D5F' : '#C9A96E'} />
          <MetricCell label="Sortino Ratio"   value={(data.metrics?.sortino ?? apexData?.quant?.sortino ?? 0).toFixed(2)}
            color={(data.metrics?.sortino ?? 0) > 0.5 ? 'green' : 'red'} />
          <MetricCell label="VaR 95%"         value={`${(apexData?.statistics?.var_cvar?.var_pct ?? 0).toFixed(3)}%`} color="red" />
          <MetricCell label="Win Prob (MC)"   value={`${apexData?.statistics?.monte_carlo?.probability_analysis?.prob_profit_pct ?? 0}%`}
            color={(apexData?.statistics?.monte_carlo?.probability_analysis?.prob_profit_pct ?? 50) > 50 ? 'green' : 'red'} />
          <MetricCell label="Z-Score"
            value={`${(apexData?.statistics?.zscore?.current_zscore ?? 0) > 0 ? '+' : ''}${(apexData?.statistics?.zscore?.current_zscore ?? 0).toFixed(2)}σ`}
            color={Math.abs(apexData?.statistics?.zscore?.current_zscore ?? 0) >= 2 ? 'red' : undefined} />
          <MetricCell label="Market Regime"
            value={(apexData?.statistics?.regime?.market_regime ?? 'UNKNOWN').replace(/_/g,' ')}
            color="blue" />
          <MetricCell label="Kelly Edge"      value={apexData?.kelly?.edge_quality ?? '—'} color="gold" />
          <MetricCell label="Ruin Probability" value={`${(apexData?.kelly?.ruin_probability_pct ?? 0).toFixed(2)}%`}
            color={(apexData?.kelly?.ruin_probability_pct ?? 100) < 5 ? 'green' : 'red'}
            sub="Based on Quarter Kelly sizing" />
        </div>

        {/* 5 — MACRO INTELLIGENCE ENGINE */}
        {apexData && <MacroIntelligence apexData={apexData} />}

        {/* 6 — FUNDAMENTALS */}
        {data.fundamentals && (
          <div className="anim d3" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div className="card" style={{ padding: 26 }}>
              <SectionHead label="Fundamental Statistics" />
              <KeyStats stats={data.fundamentals.stats} currency={data.profile?.currency} />
            </div>
            <div className="card" style={{ padding: 26 }}>
              <SectionHead label="Ownership Structure" badge="Bandarmologi" badgeType="badge-blue" />
              <OwnershipBar ownership={data.fundamentals.ownership} />
            </div>
          </div>
        )}

        {/* 7 — SATIN AI DEEP ANALYSIS */}
        <div className="anim d4">
          <AIAnalyst ticker={data.ticker} apexData={apexData} tf={chartTf} />
        </div>

        {/* 8 — AI SYNTHESIS (Crypto only, legacy text) */}
        {isCrypto && data.ai_reasoning && (
          <div className="anim d4 card" style={{ padding: 24 }}>
            <SectionHead label="Neural Synthesis" badge="APEX AI" badgeType="badge-gold" />
            {aiLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
                {[100, 90, 70].map((w, i) => <div key={i} className="shimmer" style={{ height: 10, width: `${w}%`, borderRadius: 2 }} />)}
              </div>
            ) : (
              <p style={{ fontSize: 13, fontWeight: 400, lineHeight: 1.8, color: 'var(--ink2)', borderLeft: '2px solid var(--gold3)', paddingLeft: 16, fontStyle: 'italic' }}>
                "{data.ai_reasoning}"
              </p>
            )}
          </div>
        )}
      </div>

      {/* ════════════════════════════ RIGHT SIDEBAR ═════════════════ */}
      <div style={{ position: 'sticky', top: 64, height: 'calc(100vh - 84px)', display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* Satin Risk Status */}
        {satinStatus && (
          <div className="anim card" style={{ padding: 18, flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Satin Risk Manager</p>
              <span className={`badge ${satinStatus.account_locked ? 'badge-red' : 'badge-green'}`}>
                {satinStatus.account_locked ? 'LOCKED' : 'ACTIVE'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[
                ['Daily P&L', `${(satinStatus.daily_pnl_usd ?? 0) >= 0 ? '+' : ''}$${(satinStatus.daily_pnl_usd ?? 0).toFixed(2)}`, (satinStatus.daily_pnl_usd ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'],
                ['Trades',    satinStatus.session_trades ?? 0,   'var(--ink)'],
                ['Balance',   `$${(satinStatus.account_balance ?? 30000).toLocaleString()}`, 'var(--gold)'],
                ['Max Loss',  `${(satinStatus.risk_rules?.max_daily_loss_pct ?? 2)}%`, 'var(--red)'],
              ].map(([l, v, c]) => (
                <div key={l} style={{ background: 'var(--surface2)', borderRadius: 6, padding: '8px 10px' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginBottom: 3, letterSpacing: '0.1em', textTransform: 'uppercase' }}>{l}</p>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: c }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Non-crypto: AI reasoning card */}
        {!isCrypto && (
          <div className="anim d1 card" style={{ padding: 20, flexShrink: 0 }}>
            <SectionHead label="Neural Synthesis" />
            {aiLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[100, 85, 65].map((w, i) => <div key={i} className="shimmer" style={{ height: 9, width: `${w}%`, borderRadius: 2 }} />)}
              </div>
            ) : (
              <p style={{ fontSize: 12, lineHeight: 1.75, color: 'var(--ink2)', borderLeft: '2px solid var(--gold3)', paddingLeft: 12, fontStyle: 'italic' }}>
                "{data.ai_reasoning || 'No significant signals detected.'}"
              </p>
            )}
          </div>
        )}

        {/* Crypto: Orderbook */}
        {isCrypto && (
          <div className="anim d1" style={{ flex: 1.4, minHeight: 0 }}>
            <Orderbook ticker={data.ticker} />
          </div>
        )}

        {/* News feed */}
        <div className="anim d2 card" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: 20 }}>
          <SectionHead label="Intelligence Wire" />
          <div style={{ flex: 1, overflowY: 'auto' }} className="scrollbar-hide">
            {(data?.news || []).slice(0, 12).map((n, i) => (
              <NewsItem key={i} title={n.title} publisher={n.publisher} link={n.link} time={n.time} />
            ))}
            {(!data?.news || !data.news.length) && (
              <p style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink3)' }}>No recent intel.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  // ─────────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────────
  return (
  <>
    <FontInjector />
    <GlobalStyles />

    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* ── NAV ── */}
      <nav style={{
        height: 52, background: 'rgba(8,8,15,0.95)', borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 100, backdropFilter: 'blur(12px)',
      }}>
        <div style={{
          maxWidth: 1440, margin: '0 auto', padding: '0 40px', height: '100%',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>

          {/* Logo → klik balik ke home */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <button
              onClick={() => { setActiveView('home'); setHasSearched(false); }}
              style={{ background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: 10 }}
            >
              <div style={{
                width: 24, height: 24, background: 'var(--gold)',
                borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 800, color: '#000', letterSpacing: '-0.02em' }}>AQ</span>
              </div>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, letterSpacing: '0.22em', textTransform: 'uppercase', color: 'var(--ink)' }}>APEXQ</span>
            </button>

            {/* ── NAV LINKS ── */}
            <div style={{ display: 'flex', gap: 4 }}>
              {[
                { id: 'home',     label: 'Dashboard' },
                { id: 'screener', label: '⬡ Screener' },
                { id: 'simulator', label: '⚡ Simulator' },
              ].map(({ id, label }) => {
                const isActive = activeView === id || (id === 'analysis' && activeView === 'analysis');
                return (
                  <button
                    key={id}
                    onClick={() => {
                      if (id === 'home') { setActiveView('home'); setHasSearched(false); }
                      else setActiveView(id);
                    }}
                    style={{
                      background: isActive ? 'var(--surface3)' : 'none',
                      border: `1px solid ${isActive ? 'var(--border2)' : 'transparent'}`,
                      borderRadius: 6, padding: '5px 14px',
                      fontFamily: 'var(--mono)', fontSize: 9, fontWeight: isActive ? 600 : 400,
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                      color: isActive ? 'var(--ink)' : 'var(--ink3)',
                      transition: 'all .15s', cursor: 'pointer',
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'var(--ink2)'; }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'var(--ink3)'; }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Search bar — hanya tampil di analysis view */}
          {activeView === 'analysis' && (
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'var(--surface2)', border: '1px solid var(--border2)',
              borderRadius: 8, overflow: 'hidden',
            }}>
              <input
                value={ticker}
                onChange={e => setTicker(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === "Enter" && fetchData()}
                placeholder="TICKER..."
                style={{
                  background: 'none', border: 'none', fontFamily: 'var(--mono)',
                  fontSize: 11, letterSpacing: '0.1em', color: 'var(--ink)',
                  padding: '8px 14px', width: 180,
                }}
              />
              <button onClick={() => fetchData()} style={{
                background: 'var(--gold)', border: 'none', padding: '8px 18px',
                fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
                letterSpacing: '0.12em', textTransform: 'uppercase', color: '#000',
                transition: 'opacity .15s',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '.85'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}>Run</button>
            </div>
          )}

          {/* Status dot */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 6px var(--green)' }} className="pulse-dot" />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Market Active</span>
          </div>
        </div>
      </nav>

      <main style={{ maxWidth: 1440, margin: '0 auto', padding: '0 40px' }}>

        {/* HOME VIEW */}
        {activeView === 'home' && !loading && renderHomeView()}

        {/* SCREENER VIEW */}
        {activeView === 'screener' && (
          <Screener onAnalyze={handleScreenerAnalyze} />
        )}

        {/* SIMULATOR VIEW */}
        {activeView === 'simulator' && (
          <QuantumPortfolioSimulator />
        )}

        {/* LOADING */}
        {loading && renderLoadingScreen()}

        {/* ANALYSIS VIEW */}
        {!loading && activeView === 'analysis' && data && renderAnalysisView()}

      </main>
    </div>
  </>
);
}