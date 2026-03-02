import React, { useState, useEffect } from 'react';

const fmt = (n) => parseFloat(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 });
const fmtQty = (n) => {
  const v = parseFloat(n);
  return v > 1000 ? (v / 1000).toFixed(2) + 'k' : v.toFixed(3);
};

const Row = ({ price, qty, type, maxQty }) => {
  const pct = (parseFloat(qty) / maxQty) * 100;
  const isAsk = type === 'ask';
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 6px', position: 'relative', borderRadius: 3 }}>
      <div style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: `${pct}%`,
        background: isAsk ? 'rgba(240,61,95,0.09)' : 'rgba(36,210,109,0.09)',
        transition: 'width .1s ease',
      }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: isAsk ? 'var(--red)' : 'var(--green)', zIndex: 1 }}>{fmt(price)}</span>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)', zIndex: 1 }}>{fmtQty(qty)}</span>
    </div>
  );
};

export default function Orderbook({ ticker }) {
  const [bids, setBids] = useState([]);
  const [asks, setAsks] = useState([]);
  const [maxQty, setMaxQty] = useState(1);
  const [spread, setSpread] = useState(null);
  const [status, setStatus] = useState('CONNECTING');

  useEffect(() => {
    if (!ticker) return;
    
    let ws = null;
    setBids([]); setAsks([]); setSpread(null); setStatus('CONNECTING');

    // 1. Cek apakah ini koin Hyperliquid (HYPE) atau koin Binance umum
  const isHyperliquid = ticker.toUpperCase().endsWith('-USD'); 

    if (isHyperliquid) {
      // --- LOGIKA WEBSOCKET HYPERLIQUID (L2 Book) ---
      const coin = ticker.split('-')[0];
      ws = new WebSocket("wss://api.hyperliquid.xyz/ws");
      
      ws.onopen = () => {
        setStatus('LIVE (HYPERLIQUID)');
        ws.send(JSON.stringify({ method: "subscribe", subscription: { type: "l2Book", coin: coin } }));
      };
      
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.channel === 'l2Book' && msg.data) {
          const book = msg.data.levels;
          // Ambil 9 level teratas
          const b = (book[0] || []).slice(0, 9).map(level => [level.px, level.sz]);
          const a = (book[1] || []).slice(0, 9).reverse().map(level => [level.px, level.sz]);
          
          setBids(b); setAsks(a);
          const allQ = [...b, ...a].map(x => parseFloat(x[1]));
          setMaxQty(Math.max(...allQ));
          
          if (b.length && a.length) {
            const sp = Math.abs(parseFloat(a[a.length-1][0]) - parseFloat(b[0][0]));
            setSpread(sp.toFixed(4));
          }
        }
      };

    } else {
      // --- LOGIKA WEBSOCKET BINANCE ---
      const symbol = ticker.replace('-USD', 'usdt').toLowerCase();
      ws = new WebSocket(`wss://stream.binance.com:9443/ws/${symbol}@depth20@100ms`);
      
      ws.onopen = () => setStatus('LIVE (BINANCE)');
      
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.bids && msg.asks) {
          const b = msg.bids.slice(0, 9);
          const a = msg.asks.slice(0, 9).reverse();
          setBids(b); setAsks(a);
          const allQ = [...b, ...a].map(x => parseFloat(x[1]));
          setMaxQty(Math.max(...allQ));
          if (b.length && a.length) {
            const sp = Math.abs(parseFloat(a[a.length-1][0]) - parseFloat(b[0][0]));
            setSpread(sp.toFixed(4));
          }
        }
      };
      
      ws.onerror = () => setStatus('CONNECTION FAILED');
    }

    return () => {
      if (ws) ws.close();
    };
  }, [ticker]);

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14,
      display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{ padding: '18px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }}>
        <div>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 4 }}>Live Order Depth</p>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)' }}>Order Book</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ 
            width: 6, height: 6, borderRadius: '50%', 
            background: status.includes('LIVE') ? 'var(--green)' : 'var(--gold)', 
            boxShadow: `0 0 8px ${status.includes('LIVE') ? 'var(--green)' : 'var(--gold)'}` 
          }} className={status.includes('LIVE') ? "pulse-dot" : ""} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: status.includes('LIVE') ? 'var(--green)' : 'var(--gold)' }}>
            {status}
          </span>
        </div>
      </div>

      {/* Column labels */}
      <div style={{ padding: '8px 8px 4px', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Price</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Qty</span>
      </div>

      {/* Book */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '4px 2px' }}>
        {asks.map((a, i) => <Row key={`a${i}`} price={a[0]} qty={a[1]} type="ask" maxQty={maxQty} />)}

        {/* Spread */}
        <div style={{ margin: '6px 0', display: 'flex', alignItems: 'center', gap: 8, padding: '0 6px' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          {spread && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', letterSpacing: '0.1em', whiteSpace: 'nowrap' }}>
              SPREAD {spread}
            </span>
          )}
          <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        </div>

        {bids.map((b, i) => <Row key={`b${i}`} price={b[0]} qty={b[1]} type="bid" maxQty={maxQty} />)}
      </div>
    </div>
  );
}