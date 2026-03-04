import React, { useState, useEffect } from "react";
import axios from "axios";

import { FontInjector, GlobalStyles, ThemeProvider, ThemeToggle, Divider, formatPrice } from "./components/common/GlobalStyles";
import { Label }             from "./components/common/Label";
import { MetricCell }        from "./components/common/MetricCell";
import { NewsItem }          from "./components/common/NewsItem";
import { IndicatorButton }   from "./components/common/IndicatorButton";
import { GlobalBar }         from "./components/dashboard/GlobalBar";
import { WatchlistCard }     from "./components/dashboard/WatchlistCard";
import { MacroIntelligence } from "./components/dashboard/MacroIntelligence";

import PriceChart     from "./components/PriceChart";
import MarketOverview from "./components/MarketOverview";
import KeyStats       from "./components/fundamentals/KeyStats";
import OwnershipBar   from "./components/fundamentals/OwnershipBars";
import Orderbook      from "./components/dashboard/OrderBook";
import AIAnalyst      from "./components/dashboard/AIAnalyst";
import Screener       from "./components/dashboard/Screener";
import QuantumPortfolioSimulator from "./components/dashboard/QuantumPortfolioSimulator";
import InstitutionalAuditPanel   from "./components/dashboard/InstitutionalAuditPanel";

const API     = "http://localhost:8001";
const TICKERS = ["BBCA.JK", "BBRI.JK", "NVDA", "BTC-USD"];

// ─────────────────────────────────────────────────────────────────
//  Spinner
// ─────────────────────────────────────────────────────────────────
const Spinner = ({ size = 20, color = 'var(--accent)' }) => (
  <div style={{
    width: size, height: size,
    border: `1.5px solid var(--border2)`,
    borderTopColor: color,
    borderRadius: '50%',
    flexShrink: 0,
  }} className="spin-icon" />
);

// ─────────────────────────────────────────────────────────────────
//  Apex Score Ring
// ─────────────────────────────────────────────────────────────────
const ApexRing = ({ score = 0, verdict = 'NEUTRAL' }) => {
  const r     = 26;
  const circ  = 2 * Math.PI * r;
  const fill  = (score / 100) * circ;
  const color = score >= 70 ? 'var(--pos)' : score <= 30 ? 'var(--neg)' : 'var(--accent-soft)';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <svg width={68} height={68} style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
        <circle cx={34} cy={34} r={r} fill="none" stroke="var(--surface3)" strokeWidth={4} />
        <circle cx={34} cy={34} r={r} fill="none" stroke={color} strokeWidth={4}
          strokeDasharray={`${fill} ${circ - fill}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1s cubic-bezier(.22,1,.36,1)' }}
        />
      </svg>
      <div>
        <Label size="xs" style={{ marginBottom: 4 }}>APEX Score</Label>
        <p style={{
          fontSize: 26, fontWeight: 800,
          letterSpacing: '-0.04em', lineHeight: 1,
          color, fontVariantNumeric: 'tabular-nums',
        }}>{score}</p>
        <span className={`badge ${score >= 70 ? 'badge-green' : score <= 30 ? 'badge-red' : 'badge-accent'}`}
          style={{ marginTop: 6, display: 'inline-flex' }}>
          {verdict}
        </span>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
//  Bias Gauge
// ─────────────────────────────────────────────────────────────────
const BiasGauge = ({ bull = 0, bear = 0, bias = 'NEUTRAL' }) => {
  const total   = bull + bear || 1;
  const bullPct = (bull / total) * 100;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--pos)' }}>B {bull}</span>
        <span className={`badge ${bias === 'BULLISH' ? 'badge-green' : bias === 'BEARISH' ? 'badge-red' : 'badge-muted'}`}>
          {bias}
        </span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--neg)' }}>R {bear}</span>
      </div>
      <div style={{ height: 3, background: 'var(--neg-dim)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${bullPct}%`,
          background: 'var(--pos)', borderRadius: 3,
          transition: 'width 1s ease',
        }} />
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────
//  Section Header
// ─────────────────────────────────────────────────────────────────
const SectionHead = ({ label, badge, badgeType = 'badge-muted' }) => (
  <div style={{
    display: 'flex', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: 16,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 4, height: 4, borderRadius: '50%',
        background: 'var(--accent)',
        boxShadow: '0 0 6px var(--accent-glow)',
      }} />
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
        letterSpacing: '0.12em', textTransform: 'uppercase',
        color: 'var(--ink3)',
      }}>
        {label}
      </span>
    </div>
    {badge && <span className={`badge ${badgeType}`}>{badge}</span>}
  </div>
);

// ─────────────────────────────────────────────────────────────────
//  Shared nav styles
// ─────────────────────────────────────────────────────────────────
const NAV_VIEWS = [
  { id: 'home',                label: 'Dashboard' },
  { id: 'screener',            label: 'Screener' },
  { id: 'simulator',           label: 'Simulator' },
  { id: 'institutional-audit', label: 'Audit' },
];

// ─────────────────────────────────────────────────────────────────
//  Main App (inner — needs ThemeProvider wrapper)
// ─────────────────────────────────────────────────────────────────
function AppInner() {
  const [ticker, setTicker]             = useState("");
  const [data, setData]                 = useState({ news: [], history: [], metrics: {}, profile: {} });
  const [marketIndices, setMarketIndices] = useState({ global: [], news: [], ihsg: { history: [] } });
  const [loading, setLoading]           = useState(false);
  const [aiLoading, setAiLoading]       = useState(false);
  const [chartLoading, setChartLoading] = useState(false);
  const [hasSearched, setHasSearched]   = useState(false);
  const [settings, setSettings]         = useState({ showEma1: true, ema1: 20, showEma2: true, ema2: 50, showVol: true });
  const [marketTf, setMarketTf]         = useState("1D");
  const [chartTf, setChartTf]           = useState("1D");
  const [livePrice, setLivePrice]       = useState(null);
  const [liveCandle, setLiveCandle]     = useState(null);
  const [apexData, setApexData]         = useState(null);
  const [satinStatus, setSatinStatus]   = useState(null);
  const [activeView, setActiveView]     = useState('home');

  const handleScreenerAnalyze = (selectedTicker) => {
    setTicker(selectedTicker);
    setActiveView('analysis');
    fetchData(selectedTicker);
  };

  // Market overview data
  useEffect(() => {
    if (hasSearched) return;
    axios.get(`${API}/api/market-overview/${marketTf}`)
      .then(r => setMarketIndices(r.data))
      .catch(() => {});
  }, [hasSearched, marketTf]);

  // WebSocket live price
  useEffect(() => {
    let ws = null;
    setLivePrice(null); setLiveCandle(null);
    if (!data?.ticker) return;

    const src  = data?.profile?.data_source;
    const is1D = chartTf === "1D";

    if (src === "HYPERLIQUID") {
      const coin  = data.ticker.split("-")[0].toUpperCase();
      const ival  = { "1m":"1m","15m":"15m","1H":"1h","1D":"1d" }[chartTf] || "1d";
      ws = new WebSocket("wss://api.hyperliquid.xyz/ws");
      ws.onopen = () => ws.send(JSON.stringify({ method:"subscribe", subscription:{ type:"candle", coin, interval:ival } }));
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.channel === "candle" && msg.data) {
          const k     = msg.data;
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
        const k     = JSON.parse(e.data).k;
        const close = parseFloat(k.c);
        setLivePrice(close);
        const d    = new Date(k.t);
        const time = is1D
          ? `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
          : Math.floor(k.t/1000);
        setLiveCandle({ time, open:parseFloat(k.o), high:parseFloat(k.h), low:parseFloat(k.l), close, volume:parseFloat(k.v) });
      };
    }
    return () => ws?.close();
  }, [data.ticker, data.profile?.data_source, chartTf]);

  // Fetch asset data
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

      if (asset.error) {
        alert(`Error: ${asset.error}`);
        if (isNew) { setActiveView('home'); setHasSearched(false); }
        return;
      }

      if (!isNew) {
        asset.ai_analysis  = data.ai_analysis;
        asset.ai_reasoning = data.ai_reasoning;
        asset.news         = data.news;
        asset.fundamentals = data.fundamentals;
      } else {
        asset.ai_analysis  = apex?.apex_score?.verdict || "NEUTRAL";
        asset.ai_reasoning = apex?.apex_score?.action  || "No action data";
      }

      setData(asset);
      setApexData(apex);
      setSatinStatus(satin);
      setTicker(t);
      setHasSearched(true);
      setActiveView('analysis');
    } catch (e) {
      console.error("Fetch Error:", e);
      alert("Network or Server Error. Check console.");
      if (isNew) { setActiveView('home'); setHasSearched(false); }
    } finally {
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

  // ── HOME VIEW ────────────────────────────────────────────────
  const renderHome = () => (
    <div style={{ paddingTop: 52, paddingBottom: 96 }}>
      {marketIndices?.global?.length > 0 && (
        <div style={{ marginBottom: 64 }}>
          <GlobalBar indices={marketIndices.global} />
        </div>
      )}

      {/* Hero Search */}
      <div className="anim" style={{ marginBottom: 64 }}>
        <p style={{
          fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 20,
        }}>
          Asset Intelligence · IDX / NYSE / NASDAQ / Crypto
        </p>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 16,
          paddingBottom: 20, borderBottom: '1px solid var(--border2)',
          marginBottom: 20,
        }}>
          <input
            autoFocus
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === "Enter" && fetchData()}
            placeholder="TICKER"
            style={{
              flex: 1, background: 'none', border: 'none',
              fontFamily: 'var(--font)', fontSize: 64, fontWeight: 800,
              color: 'var(--ink)', letterSpacing: '-0.045em',
            }}
          />
          <button onClick={() => fetchData()} style={{
            background: 'var(--accent)', border: 'none', color: '#fff',
            padding: '12px 32px', borderRadius: 10,
            fontSize: 13, fontWeight: 600, letterSpacing: '0.02em',
            flexShrink: 0, transition: 'all .2s ease',
            boxShadow: '0 0 20px var(--accent-glow)',
          }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '.85'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1';   e.currentTarget.style.transform = 'translateY(0)'; }}>
            Analyze
          </button>
        </div>

        {/* Quick tickers */}
        <div style={{ display: 'flex', gap: 6 }}>
          {TICKERS.map(t => (
            <button key={t} onClick={() => fetchData(t)} style={{
              background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '4px 13px',
              fontFamily: 'var(--mono)', fontSize: 9,
              letterSpacing: '0.12em', textTransform: 'uppercase',
              color: 'var(--ink3)', transition: 'all .15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'var(--accent-border)';
              e.currentTarget.style.color = 'var(--accent-soft)';
              e.currentTarget.style.background = 'var(--accent-dim)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'var(--border)';
              e.currentTarget.style.color = 'var(--ink3)';
              e.currentTarget.style.background = 'var(--surface2)';
            }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Watchlist */}
      <div className="anim d1" style={{ marginBottom: 64 }}>
        <SectionHead label="Global Watchlist & Indices" badge="Real-Time" />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(276px, 1fr))', gap: 16 }}>
          {marketIndices?.global?.map(item => {
            const isIdx = ["GSPC","NDX","DJI","JKSE"].includes(item.symbol);
            return <WatchlistCard key={item.symbol} item={item} onClick={() => fetchData(isIdx ? `^${item.symbol}` : item.symbol)} />;
          })}
        </div>
      </div>

      <div className="border-rule" style={{ marginBottom: 52 }} />

      {/* IHSG + News */}
      <div className="anim d2" style={{ display: 'grid', gridTemplateColumns: '1fr 288px', gap: 48 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
            <div>
              <Label style={{ marginBottom: 7 }}>IDX Composite · IHSG</Label>
              <h2 style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ink)', marginBottom: 14 }}>
                Jakarta Composite
              </h2>
              <div style={{ display: 'flex', gap: 3 }}>
                {["1D","1W","1M","1Y"].map(tf => (
                  <button key={tf} onClick={() => setMarketTf(tf)} style={{
                    background: marketTf === tf ? 'var(--accent)' : 'transparent',
                    color:      marketTf === tf ? '#fff' : 'var(--ink3)',
                    border: `1px solid ${marketTf === tf ? 'transparent' : 'var(--border)'}`,
                    borderRadius: 5, padding: '3px 11px',
                    fontFamily: 'var(--mono)', fontSize: 9,
                    fontWeight: marketTf === tf ? 500 : 400,
                    letterSpacing: '0.10em', transition: 'all .15s',
                  }}>{tf}</button>
                ))}
              </div>
            </div>

            {marketIndices?.ihsg && (
              <div style={{ textAlign: 'right' }}>
                <p style={{
                  fontSize: 40, fontWeight: 800, letterSpacing: '-0.04em', lineHeight: 1,
                  color: marketIndices.ihsg.current > marketIndices.ihsg.open ? 'var(--pos)' : 'var(--neg)',
                  fontVariantNumeric: 'tabular-nums',
                }}>
                  {marketIndices.ihsg.current?.toLocaleString()}
                </p>
                <div style={{ display: 'flex', gap: 14, justifyContent: 'flex-end', marginTop: 8 }}>
                  {[['H', marketIndices.ihsg.high], ['O', marketIndices.ihsg.open]].map(([l, v]) => (
                    <span key={l} style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', letterSpacing: '0.08em' }}>
                      {l} {v?.toLocaleString()}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div style={{
            height: 360, background: 'var(--surface)',
            borderRadius: 12, border: '1px solid var(--border)',
            padding: 14, overflow: 'hidden', position: 'relative',
          }}>
            {marketIndices?.ihsg?.history?.length > 0 && (
              <MarketOverview data={marketIndices.ihsg.history} openPrice={marketIndices.ihsg.open} tf={marketTf} />
            )}
          </div>
        </div>

        {/* News */}
        <div>
          <SectionHead label="Intelligence Wire" />
          <div style={{ maxHeight: 400, overflowY: 'auto' }} className="scrollbar-hide">
            {(marketIndices?.news || []).slice(0, 8).map((n, i) => (
              <NewsItem key={i} title={n.title} publisher={n.source} time={n.time} link={n.link} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  // ── LOADING SCREEN ────────────────────────────────────────────
  const renderLoading = () => (
    <div style={{
      height: '82vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 18,
    }}>
      <div style={{ position: 'relative', width: 56, height: 56 }}>
        <svg width={56} height={56} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={28} cy={28} r={23} fill="none" stroke="var(--surface3)" strokeWidth={2.5} />
          <circle cx={28} cy={28} r={23} fill="none" stroke="var(--accent)" strokeWidth={2.5}
            strokeDasharray="36 108" strokeLinecap="round"
            style={{ animation: 'spin 1.1s linear infinite', transformOrigin: 'center' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 600,
            color: 'var(--accent)', letterSpacing: '0.04em',
          }}>AQ</span>
        </div>
      </div>
      <p style={{
        fontFamily: 'var(--mono)', fontSize: 9,
        letterSpacing: '0.18em', textTransform: 'uppercase',
        color: 'var(--ink3)',
      }}>
        Gathering data for {ticker}…
      </p>
    </div>
  );

  // ── ANALYSIS VIEW ─────────────────────────────────────────────
  const renderAnalysis = () => (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 280px',
      gap: 36, paddingTop: 36, paddingBottom: 80,
    }}>

      {/* ═══════ LEFT ═══════ */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* 1 — Asset Header */}
        <div className="anim">
          <div style={{ display: 'flex', gap: 7, alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
              letterSpacing: '0.14em', textTransform: 'uppercase',
              background: 'var(--accent)', color: '#fff',
              padding: '4px 12px', borderRadius: 5,
            }}>{data.ticker}</span>

            {data.profile?.data_source && (
              <span className={`badge ${data.profile.data_source === 'BINANCE' ? 'badge-amber' : 'badge-blue'}`}>
                {data.profile.data_source}
              </span>
            )}
            {data.profile?.sector   && <span className="badge badge-muted">{data.profile.sector}</span>}
            {data.profile?.exchange && <span className="badge badge-muted">{data.profile.exchange}</span>}
            {data.profile?.full_name && (
              <span style={{ fontSize: 13, fontWeight: 400, color: 'var(--ink3)' }}>{data.profile.full_name}</span>
            )}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 20 }}>
            {/* Price */}
            <div>
              <Label size="xs" style={{ marginBottom: 8 }}>Real-Time Quote</Label>
              <p style={{
                fontSize: 54, fontWeight: 800,
                letterSpacing: '-0.045em', lineHeight: 0.9,
                color: 'var(--ink)', fontVariantNumeric: 'tabular-nums',
              }}>
                {formatPrice(livePrice !== null ? livePrice : data.price, data.profile?.currency)}
              </p>
            </div>

            {/* Controls */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12 }}>
              {/* Sentiment pill */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 7,
                border: `1px solid ${isBull ? 'var(--pos-b)' : isBear ? 'var(--neg-b)' : 'var(--border2)'}`,
                background: isBull ? 'var(--pos-dim)' : isBear ? 'var(--neg-dim)' : 'var(--surface2)',
                borderRadius: 100, padding: '5px 14px',
              }}>
                {aiLoading ? (
                  <><Spinner size={9} color="var(--ink3)" />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', letterSpacing: '0.14em' }}>SYNTHESIZING</span></>
                ) : (
                  <><span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: isBull ? 'var(--pos)' : isBear ? 'var(--neg)' : 'var(--ink3)',
                    boxShadow: isBull ? '0 0 7px var(--pos)' : isBear ? '0 0 7px var(--neg)' : 'none',
                  }} className="pulse-dot" />
                  <span style={{
                    fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
                    letterSpacing: '0.14em',
                    color: isBull ? 'var(--pos)' : isBear ? 'var(--neg)' : 'var(--ink2)',
                  }}>
                    {data.ai_analysis || 'NEUTRAL'}
                  </span></>
                )}
              </div>

              {/* TF + indicators */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <div style={{
                  display: 'flex', background: 'var(--surface2)',
                  padding: 3, borderRadius: 7,
                  border: '1px solid var(--border)', gap: 2,
                }}>
                  {["1m","15m","1H","1D"].map(tf => (
                    <button key={tf}
                      onClick={() => { setChartTf(tf); fetchData(data.ticker, tf); }}
                      style={{
                        background: chartTf === tf ? 'var(--accent)' : 'transparent',
                        color:      chartTf === tf ? '#fff' : 'var(--ink3)',
                        border: 'none', borderRadius: 5,
                        padding: '4px 12px',
                        fontFamily: 'var(--mono)', fontSize: 9,
                        fontWeight: chartTf === tf ? 500 : 400,
                        letterSpacing: '0.06em',
                        transition: 'all .15s ease',
                      }}>
                      {tf}
                    </button>
                  ))}
                </div>

                <div style={{ width: 1, height: 20, background: 'var(--border)' }} />

                <div style={{ display: 'flex', gap: 5 }}>
                  <IndicatorButton label="EMA 20" active={settings.showEma1} color="blue"   onClick={() => setSettings(s => ({ ...s, showEma1: !s.showEma1 }))} />
                  <IndicatorButton label="EMA 50" active={settings.showEma2} color="orange" onClick={() => setSettings(s => ({ ...s, showEma2: !s.showEma2 }))} />
                  <IndicatorButton label="Vol"    active={settings.showVol}  color="gold"   onClick={() => setSettings(s => ({ ...s, showVol:  !s.showVol  }))} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 2 — Chart */}
        <div className="anim d1 card" style={{ padding: '18px 18px 32px', position: 'relative' }}>
          {chartLoading && (
            <div style={{
              position: 'absolute', inset: 0, zIndex: 10,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(9,9,11,.7)', borderRadius: 14,
              backdropFilter: 'blur(4px)',
            }}>
              <Spinner size={28} />
            </div>
          )}
          <div style={{ height: 450, opacity: chartLoading ? 0.25 : 1, transition: 'opacity .2s' }}>
            {data.history?.length > 0 && (
              <PriceChart data={data.history} settings={settings} liveCandle={liveCandle} tf={chartTf} />
            )}
          </div>
        </div>

        {/* 3 — Apex + ICT row */}
        <div className="anim d2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div className="card card-accent" style={{ padding: 22, display: 'flex', alignItems: 'center', gap: 20 }}>
            <ApexRing score={apexScore} verdict={apexVerd} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <Divider style={{ marginBottom: 10 }} />
              {[
                ['EV per Trade', `${(apexData?.kelly?.expected_value_pct ?? 0) > 0 ? '+' : ''}${(apexData?.kelly?.expected_value_pct ?? 0).toFixed(4)}%`, (apexData?.kelly?.expected_value_pct ?? 0) >= 0 ? 'var(--pos)' : 'var(--neg)'],
                ['Kelly Edge',   apexData?.kelly?.edge_quality ?? '—',   'var(--amber)'],
                ['Regime',       (apexData?.statistics?.regime?.market_regime ?? 'UNKNOWN').replace(/_/g,' '), 'var(--blue)'],
              ].map(([l, v, c]) => (
                <div key={l} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)' }}>{l}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: c }}>{v}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ padding: 22 }}>
            <SectionHead label="Smart Money Bias" badge="ICT" badgeType="badge-amber" />
            <BiasGauge bull={bullF} bear={bearF} bias={ictBias} />
            <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
              {[
                ['Struct',  (apexData?.ict_analysis?.market_structure?.market_structure ?? '—').replace(/_/g,' ')],
                ['FVG',     apexData?.ict_analysis?.fvg_analysis ? (apexData.ict_analysis.fvg_analysis.unfilled_bullish?.length || 0) + (apexData.ict_analysis.fvg_analysis.unfilled_bearish?.length || 0) : '—'],
                ['Liq Bias',apexData?.ict_analysis?.liquidity_zones?.liquidity_bias ?? '—'],
                ['Price Pos',apexData?.ict_analysis?.market_structure?.market_structure?.replace(/_/g, ' ') || '—'],
              ].map(([l, v]) => (
                <div key={l} style={{ background: 'var(--surface2)', borderRadius: 7, padding: '8px 10px' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginBottom: 3, letterSpacing: '0.10em', textTransform: 'uppercase' }}>{l}</p>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: 'var(--ink)' }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 4 — Quant Metrics Grid */}
        <div className="anim d2 card" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', overflow: 'hidden' }}>
          <MetricCell label="APEX Score"       value={apexScore} color={apexScore >= 70 ? 'green' : apexScore <= 30 ? 'red' : undefined} />
          <MetricCell label="Sortino Ratio"    value={(data.metrics?.sortino ?? apexData?.quant?.sortino ?? 0).toFixed(2)} color={(data.metrics?.sortino ?? 0) > 0.5 ? 'green' : 'red'} />
          <MetricCell label="VaR 95%"          value={`${(apexData?.statistics?.var_cvar?.var_pct ?? 0).toFixed(3)}%`} color="red" />
          <MetricCell label="Win Prob (MC)"    value={`${apexData?.statistics?.monte_carlo?.prob_profit_pct ?? 0}%`} color={(apexData?.statistics?.monte_carlo?.prob_profit_pct ?? 50) > 50 ? 'green' : 'red'} last />
          <MetricCell label="Z-Score"          value={`${(apexData?.statistics?.zscore?.current_zscore ?? 0) > 0 ? '+' : ''}${(apexData?.statistics?.zscore?.current_zscore ?? 0).toFixed(2)}σ`} color={Math.abs(apexData?.statistics?.zscore?.current_zscore ?? 0) >= 2 ? 'red' : undefined} />
          <MetricCell label="Market Regime"    value={(apexData?.statistics?.regime?.market_regime ?? 'UNKNOWN').replace(/_/g,' ')} color="blue" />
          <MetricCell label="Kelly Edge"       value={apexData?.kelly?.edge_quality ?? '—'} color="amber" />
          <MetricCell label="Ruin Probability" value={`${(apexData?.kelly?.ruin_probability_pct ?? 0).toFixed(2)}%`} color={(apexData?.kelly?.ruin_probability_pct ?? 100) < 5 ? 'green' : 'red'} sub="Quarter Kelly sizing" last />
        </div>

        {/* 5 — Macro Intelligence */}
        {apexData && <MacroIntelligence apexData={apexData} />}

        {/* 6 — Fundamentals */}
        {data.fundamentals && (
          <div className="anim d3" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div className="card" style={{ padding: 24 }}>
              <SectionHead label="Fundamental Statistics" />
              <KeyStats stats={data.fundamentals.stats} currency={data.profile?.currency} />
            </div>
            <div className="card" style={{ padding: 24 }}>
              <SectionHead label="Ownership Structure" badge="Bandarmologi" badgeType="badge-blue" />
              <OwnershipBar ownership={data.fundamentals.ownership} />
            </div>
          </div>
        )}

        {/* 7 — Satin AI */}
        <div className="anim d4">
          <AIAnalyst ticker={data.ticker} apexData={apexData} tf={chartTf} />
        </div>

        {/* 8 — Crypto AI Synthesis */}
        {isCrypto && data.ai_reasoning && (
          <div className="anim d4 card" style={{ padding: 22 }}>
            <SectionHead label="Neural Synthesis" badge="APEX AI" badgeType="badge-accent" />
            {aiLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 6 }}>
                {[100, 88, 68].map((w, i) => <div key={i} className="shimmer" style={{ height: 9, width: `${w}%`, borderRadius: 2 }} />)}
              </div>
            ) : (
              <p style={{
                fontSize: 13, fontWeight: 400, lineHeight: 1.85,
                color: 'var(--ink2)',
                borderLeft: '2px solid var(--accent)',
                paddingLeft: 14, fontStyle: 'italic',
              }}>
                "{data.ai_reasoning}"
              </p>
            )}
          </div>
        )}
      </div>

      {/* ═══════ RIGHT SIDEBAR ═══════ */}
      <div style={{
        position: 'sticky', top: 60,
        height: 'calc(100vh - 80px)',
        display: 'flex', flexDirection: 'column', gap: 14,
      }}>
        {/* Satin Risk Status */}
        {satinStatus && (
          <div className="anim card" style={{ padding: 16, flexShrink: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <Label size="xs">Satin Risk Manager</Label>
              <span className={`badge ${satinStatus.account_locked ? 'badge-red' : 'badge-green'}`}>
                {satinStatus.account_locked ? 'LOCKED' : 'ACTIVE'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 7 }}>
              {[
                ['P&L', `${(satinStatus.daily_pnl_usd ?? 0) >= 0 ? '+' : ''}$${(satinStatus.daily_pnl_usd ?? 0).toFixed(2)}`, (satinStatus.daily_pnl_usd ?? 0) >= 0 ? 'var(--pos)' : 'var(--neg)'],
                ['Trades',  satinStatus.session_trades ?? 0, 'var(--ink)'],
                ['Balance', `$${(satinStatus.account_balance ?? 30000).toLocaleString()}`, 'var(--amber)'],
                ['Max Loss',`${(satinStatus.risk_rules?.max_daily_loss_pct ?? 2)}%`, 'var(--neg)'],
              ].map(([l, v, c]) => (
                <div key={l} style={{ background: 'var(--surface2)', borderRadius: 6, padding: '8px 9px' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginBottom: 3, letterSpacing: '0.10em', textTransform: 'uppercase' }}>{l}</p>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: c }}>{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Neural Synthesis (non-crypto) */}
        {!isCrypto && (
          <div className="anim d1 card" style={{ padding: 18, flexShrink: 0 }}>
            <SectionHead label="Neural Synthesis" />
            {aiLoading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {[100, 82, 60].map((w, i) => <div key={i} className="shimmer" style={{ height: 8, width: `${w}%`, borderRadius: 2 }} />)}
              </div>
            ) : (
              <p style={{
                fontSize: 12, lineHeight: 1.75, color: 'var(--ink2)',
                borderLeft: '2px solid var(--accent)', paddingLeft: 11,
                fontStyle: 'italic',
              }}>
                "{data.ai_reasoning || 'No significant signals detected.'}"
              </p>
            )}
          </div>
        )}

        {/* Order Book (crypto) */}
        {isCrypto && (
          <div className="anim d1" style={{ flex: 1.4, minHeight: 0 }}>
            <Orderbook ticker={data.ticker} />
          </div>
        )}

        {/* News feed */}
        <div className="anim d2 card" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', padding: 18 }}>
          <SectionHead label="Intelligence Wire" />
          <div style={{ flex: 1, overflowY: 'auto' }} className="scrollbar-hide">
            {(data?.news || []).slice(0, 12).map((n, i) => (
              <NewsItem key={i} title={n.title} publisher={n.publisher} link={n.link} time={n.time} />
            ))}
            {(!data?.news || !data.news.length) && (
              <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>No recent intel.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  // ── RENDER ────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>

      {/* NAV */}
      <nav style={{
        height: 50,
        background: 'var(--nav-bg)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 100,
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        transition: 'background .25s ease',
      }}>
        <div style={{
          maxWidth: 1440, margin: '0 auto', padding: '0 36px',
          height: '100%', display: 'flex',
          justifyContent: 'space-between', alignItems: 'center', gap: 16,
        }}>

          {/* Logo + nav links */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button
              onClick={() => { setActiveView('home'); setHasSearched(false); }}
              style={{ background: 'none', border: 'none', display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <div style={{
                width: 22, height: 22, background: 'var(--accent)',
                borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 800, color: '#fff', letterSpacing: '-0.01em' }}>AQ</span>
              </div>
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
                letterSpacing: '0.22em', textTransform: 'uppercase', color: 'var(--ink)',
              }}>APEXQ</span>
            </button>

            {/* Divider */}
            <div style={{ width: 1, height: 18, background: 'var(--border)' }} />

            <div style={{ display: 'flex', gap: 2 }}>
              {NAV_VIEWS.map(({ id, label }) => {
                const isActive = activeView === id || (id === 'home' && activeView === 'analysis');
                return (
                  <button
                    key={id}
                    onClick={() => id === 'home' ? (setActiveView('home'), setHasSearched(false)) : setActiveView(id)}
                    style={{
                      background: isActive ? 'var(--surface2)' : 'none',
                      border: `1px solid ${isActive ? 'var(--border)' : 'transparent'}`,
                      borderRadius: 6, padding: '4px 12px',
                      fontFamily: 'var(--mono)', fontSize: 8, fontWeight: isActive ? 500 : 400,
                      letterSpacing: '0.12em', textTransform: 'uppercase',
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

          {/* Center — Search bar (analysis view only) */}
          {activeView === 'analysis' && (
            <div style={{
              display: 'flex', alignItems: 'center',
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderRadius: 8, overflow: 'hidden',
              flex: 1, maxWidth: 280,
            }}>
              <input
                value={ticker}
                onChange={e => setTicker(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === "Enter" && fetchData()}
                placeholder="TICKER..."
                style={{
                  background: 'none', border: 'none',
                  fontFamily: 'var(--mono)', fontSize: 10,
                  letterSpacing: '0.10em', color: 'var(--ink)',
                  padding: '7px 12px', flex: 1, minWidth: 0,
                }}
              />
              <button onClick={() => fetchData()} style={{
                background: 'var(--accent)', border: 'none',
                padding: '7px 16px', flexShrink: 0,
                fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 500,
                letterSpacing: '0.12em', textTransform: 'uppercase',
                color: '#fff', transition: 'opacity .15s',
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = '.8'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
                Run
              </button>
            </div>
          )}

          {/* Right — status + theme toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 5, height: 5, borderRadius: '50%',
                background: 'var(--pos)', boxShadow: '0 0 5px var(--pos)',
              }} className="pulse-dot" />
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 7,
                letterSpacing: '0.14em', textTransform: 'uppercase',
                color: 'var(--ink3)',
              }}>
                Market Active
              </span>
            </div>

            <ThemeToggle />
          </div>
        </div>
      </nav>

      <main style={{ maxWidth: 1440, margin: '0 auto', padding: '0 36px' }}>
        {activeView === 'home'                && !loading && renderHome()}
        {activeView === 'screener'            && <Screener onAnalyze={handleScreenerAnalyze} />}
        {activeView === 'simulator'           && <QuantumPortfolioSimulator />}
        {activeView === 'institutional-audit' && <InstitutionalAuditPanel />}
        {loading && renderLoading()}
        {!loading && activeView === 'analysis' && data && renderAnalysis()}
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
//  Root export — wraps everything in ThemeProvider
// ─────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <ThemeProvider>
      <FontInjector />
      <GlobalStyles />
      <AppInner />
    </ThemeProvider>
  );
}