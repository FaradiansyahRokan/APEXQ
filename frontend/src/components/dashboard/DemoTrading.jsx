/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║              APEX DEMO TRADING v2.0 — LIVE SIMULATION            ║
 * ║   Quant Signals · Chart · Orderbook · Limit Orders · Live P&L   ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * NEW in v2.0:
 *  • Full Quant Engine panel (VaR, CVaR, Calmar, Omega, Fat Tail…)
 *  • Trade Setup Recommendation (entry, SL, TP from volatility + ICT)
 *  • Market Order  → fills immediately at current price
 *  • Limit Order   → pending, auto-executes when price is hit
 *  • Stop-Loss / Take-Profit auto-monitor via live price polling
 *  • PriceChart embedded in signal panel
 *  • Hyperliquid Orderbook for crypto tickers
 *  • Unrealized P&L on open positions (live)
 *  • Apex Equity Armor active for all risk-sizing
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import PriceChart    from '../PriceChart';
import MarketOverview from '../MarketOverview';
import Orderbook      from './OrderBook';
import HFTBot         from './HftBot';

import { API as _API } from '../../config';
const API      = _API;
const DEMO_KEY = 'apexq_demo_v2';

// ─── Formatters ───────────────────────────────────────────────────
const fmt    = (n, d = 2) => Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (n)        => `${n >= 0 ? '+' : ''}${fmt(n, 2)}%`;
const fmtUSD = (n)        => `${n >= 0 ? '' : '-'}$${fmt(Math.abs(n || 0))}`;
const today  = ()         => new Date().toISOString().split('T')[0];
const isCrypto = (t)      => t?.endsWith('-USD') || t?.endsWith('USDT') || t?.endsWith('-USDT');

// ─── Verdict color ────────────────────────────────────────────────
const verdictColor = (v) => v === 'BULLISH' ? 'var(--pos)' : v === 'BEARISH' ? 'var(--neg)' : 'var(--ink2)';

// ─── Mini equity curve SVG ────────────────────────────────────────
const EquityCurve = ({ data = [], w = 284, h = 72 }) => {
  if (!data || data.length < 2) return (
    <div style={{ width: w, height: h, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)' }}>Trade to build curve</span>
    </div>
  );
  const vals  = data.map(d => d.balance);
  const min   = Math.min(...vals); const max = Math.max(...vals);
  const range = max - min || 1; const pad = 4;
  const pts   = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const isPos = vals[vals.length - 1] >= vals[0];
  const color = isPos ? '#22c55e' : '#ef4444';
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="ecg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill="url(#ecg)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

// ─── Scale bar ────────────────────────────────────────────────────
const ScaleBar = ({ value = 1, color = 'var(--pos)' }) => (
  <div style={{ height: 5, background: 'var(--surface3)', borderRadius: 3, overflow: 'hidden' }}>
    <div style={{ height: '100%', width: `${Math.min(1, Math.max(0, value)) * 100}%`, background: color, borderRadius: 3, transition: 'width 1s cubic-bezier(.22,1,.36,1)' }} />
  </div>
);

// ─── Quant metric row ─────────────────────────────────────────────
const QRow = ({ label, value, color, badge }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</span>
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {badge && <span className={`badge ${badge}`} style={{ fontSize: 9, padding: '1px 5px' }}>{value}</span>}
      {!badge && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: color || 'var(--ink2)' }}>{value}</span>}
    </div>
  </div>
);

// ─── Account factory ──────────────────────────────────────────────
const makeAccount = (balance = 10000) => ({
  version:        2,
  sessionId:      `demo_${Date.now()}`,
  initialBalance: balance,
  currentBalance: balance,
  armorReady:     false,
  openPositions:  [],
  closedTrades:   [],
  equityCurve:    [{ date: today(), balance }],
});

const MODE_COLOR = { FULL: 'var(--pos)', REDUCED: 'var(--amber)', DEFENSIVE: 'var(--neg)', HALTED: 'var(--neg)' };

// ─────────────────────────────────────────────────────────────────
//  MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────
export default function DemoTrading() {

  // ── Account ──────────────────────────────────────────────────
  const [account,   setAccount]   = useState(null);
  const [setupMode, setSetupMode] = useState(false);
  const [deposit,   setDeposit]   = useState(10000);

  // ── Armor ─────────────────────────────────────────────────────
  const [armor,      setArmor]      = useState(null);
  const [milestones, setMilestones] = useState(null);
  const [armorBusy,  setArmorBusy]  = useState(false);

  // ── Signal / Analysis ─────────────────────────────────────────
  const [sigTicker,  setSigTicker]  = useState('');
  const [sigLoading, setSigLoading] = useState(false);
  const [sigData,    setSigData]    = useState(null);   // apex-institutional response
  const [riskRec,    setRiskRec]    = useState(null);   // armor risk-size
  const [chartData,  setChartData]  = useState(null);   // OHLCV for PriceChart
  const [chartLoading, setChartLoading] = useState(false);
  const [tradeSetup, setTradeSetup] = useState(null);   // recommended SL/TP

  // ── Live prices (ticker → price) ──────────────────────────────
  const [livePrices, setLivePrices] = useState({});
  const pollRef = useRef(null);

  // ── Form ──────────────────────────────────────────────────────
  const [form, setForm] = useState({
    ticker: '', direction: 'LONG', orderType: 'MARKET',
    entryPrice: '', limitPrice: '', stopLoss: '', takeProfit: '', notes: '',
  });

  // ── UI ────────────────────────────────────────────────────────
  const [closeMeta,  setCloseMeta]  = useState(null);
  const [tab,        setTab]        = useState('positions');
  const [mainTab,    setMainTab]    = useState('demo');   // 'demo' | 'hft'
  const [showChart,  setShowChart]  = useState(true);
  const [notification, setNotification] = useState(null);

  // ── Watchlist ─────────────────────────────────────────────
  const DEFAULT_WATCHLIST = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'BNB-USD', 'NVDA', 'AAPL'];
  const [watchlist,     setWatchlist]     = useState(() => {
    try { return JSON.parse(localStorage.getItem('apexq_watchlist') || 'null') || DEFAULT_WATCHLIST; }
    catch { return DEFAULT_WATCHLIST; }
  });
  const [watchPrices,   setWatchPrices]   = useState({});  // ticker → { price, open, chgPct, sparkline[] }
  const [watchInput,    setWatchInput]    = useState('');
  const watchWsRefs = useRef({});  // ticker → WebSocket (crypto only)

  // ── Standalone chart (independen dari signal) ─────────────
  const [chartTicker,   setChartTicker]   = useState('');
  const [standaloneChart, setStandaloneChart] = useState(null);   // { data, tf, ticker }
  const [chartPanelTf,  setChartPanelTf]  = useState('1D');
  const [chartPanelLoading, setChartPanelLoading] = useState(false);
  const [liveCandle,    setLiveCandle]    = useState(null);  // realtime candle update
  const chartWsRef = useRef(null);

  // FIX 3: Throttle WS price updates — update state max 1x/detik per coin.
  // Hyperliquid candle WS bisa kirim update setiap < 1 detik untuk semua coin sekaligus.
  // Tanpa throttle: setiap candle message → setWatchPrices → re-render seluruh DemoTrading
  // termasuk HFTBot di dalamnya → UI flickering terus.
  const watchPriceThrottleRef = useRef({});   // ticker → last update timestamp (ms)
  const livePriceThrottleRef  = useRef({});   // ticker → last update timestamp (ms)
  const PRICE_THROTTLE_MS     = 1000;         // update state max sekali per detik per coin

  // FIX 4: Simpan account terbaru di ref untuk diakses oleh WS callbacks (no stale closure)
  const accountRef = useRef(null);
  useEffect(() => { accountRef.current = account; }, [account]);

  // ═══════════════════════════════════════════════════════════════
  //  PERSISTENCE
  // ═══════════════════════════════════════════════════════════════
  const saveAccount = useCallback((acc) => {
    localStorage.setItem(DEMO_KEY, JSON.stringify(acc));
    setAccount(acc);
  }, []);

  useEffect(() => {
    const raw = localStorage.getItem(DEMO_KEY);
    if (raw) {
      try { setAccount(JSON.parse(raw)); }
      catch { setSetupMode(true); }
    } else {
      setSetupMode(true);
    }
  }, []);

  // ═══════════════════════════════════════════════════════════════
  //  NOTIFICATION HELPER
  // ═══════════════════════════════════════════════════════════════
  const notify = useCallback((msg, type = 'info') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  }, []);

  // ═══════════════════════════════════════════════════════════════
  //  ARMOR
  // ═══════════════════════════════════════════════════════════════
  const initArmor = useCallback(async (acc) => {
    try {
      await axios.post(`${API}/api/armor/init`, {
        session_id:          acc.sessionId,
        initial_balance:     acc.initialBalance,
        trailing_stop_pct:   0.15,
        target_vol_ann:      0.12,
        base_kelly_fraction: 0.25,
        reserve_rate:        0.15,
        min_win_rate:        0.45,
        max_consec_losses:   7,
      });
      return { ...acc, armorReady: true };
    } catch (e) {
      console.warn('Armor init failed:', e.message);
      return { ...acc, armorReady: false };
    }
  }, []);

  const refreshArmor = useCallback(async (acc) => {
    if (!acc?.armorReady) return;
    setArmorBusy(true);
    try {
      await axios.post(`${API}/api/armor/update`, {
        session_id:      acc.sessionId,
        current_balance: acc.currentBalance,
        date:            today(),
      });
      const [sRes, mRes] = await Promise.all([
        axios.get(`${API}/api/armor/status?session_id=${acc.sessionId}`),
        axios.get(`${API}/api/armor/milestones?session_id=${acc.sessionId}`),
      ]);
      setArmor(sRes.data);
      setMilestones(mRes.data);
    } catch (e) {
      console.warn('Armor refresh failed:', e.message);
    } finally {
      setArmorBusy(false);
    }
  }, []);

  useEffect(() => {
    if (account && !setupMode) refreshArmor(account);
  }, [account?.sessionId]); // eslint-disable-line

  // ═══════════════════════════════════════════════════════════════
  //  LIVE PRICE POLLING — 25s interval
  // ═══════════════════════════════════════════════════════════════
  const fetchLivePrices = useCallback(async (positions) => {
    const tickers = [...new Set(
      positions
        .filter(p => p.status !== 'CLOSED')
        .map(p => p.ticker)
    )];
    if (!tickers.length) return null;

    const results = {};
    await Promise.allSettled(
      tickers.map(async (tk) => {
        try {
          const res = await axios.get(`${API}/api/apex-institutional/${tk}`, { timeout: 15000 });
          results[tk] = res.data?.price ?? null;
        } catch { /* ignore */ }
      })
    );
    return results;
  }, []);

  // Auto-execute: limit hit, SL/TP triggers
  const checkAutoExecutions = useCallback((acc, prices) => {
    if (!acc || !prices) return acc;
    let updated = { ...acc };
    let changed  = false;
    let notifs   = [];

    updated.openPositions = updated.openPositions.map(pos => {
      const liveP = prices[pos.ticker];
      if (!liveP) return pos;

      // ── Activate limit order ──
      if (pos.status === 'PENDING' && pos.orderType === 'LIMIT') {
        const hit = pos.direction === 'LONG'
          ? liveP <= pos.limitPrice
          : liveP >= pos.limitPrice;
        if (hit) {
          changed = true;
          notifs.push({ msg: ` Limit order FILLED: ${pos.ticker} @ ${fmt(pos.limitPrice, 4)}`, type: 'success' });
          return { ...pos, status: 'OPEN', entryPrice: pos.limitPrice };
        }
      }

      // ── Stop Loss ──
      if (pos.status === 'OPEN' && pos.stopLoss) {
        const slHit = pos.direction === 'LONG'
          ? liveP <= pos.stopLoss
          : liveP >= pos.stopLoss;
        if (slHit) {
          changed = true;
          const pnl = pos.direction === 'LONG'
            ? (pos.stopLoss - pos.entryPrice) * pos.shares
            : (pos.entryPrice - pos.stopLoss) * pos.shares;
          updated.closedTrades = [
            { ...pos, exitPrice: pos.stopLoss, pnl: Number(pnl.toFixed(2)),
              pnlPct: Number(((pnl / pos.positionValue) * 100).toFixed(3)),
              isWin: pnl > 0, closedAt: new Date().toISOString(), closeReason: 'STOP_LOSS' },
            ...updated.closedTrades,
          ];
          updated.currentBalance = Number((updated.currentBalance + pnl).toFixed(2));
          updated.equityCurve    = [...updated.equityCurve, { date: today(), balance: updated.currentBalance }];
          notifs.push({ msg: ` Stop Loss hit: ${pos.ticker} P&L ${fmtUSD(pnl)}`, type: pnl >= 0 ? 'success' : 'error' });
          return null; // remove from open
        }
      }

      // ── Take Profit ──
      if (pos.status === 'OPEN' && pos.takeProfit) {
        const tpHit = pos.direction === 'LONG'
          ? liveP >= pos.takeProfit
          : liveP <= pos.takeProfit;
        if (tpHit) {
          changed = true;
          const pnl = pos.direction === 'LONG'
            ? (pos.takeProfit - pos.entryPrice) * pos.shares
            : (pos.entryPrice - pos.takeProfit) * pos.shares;
          updated.closedTrades = [
            { ...pos, exitPrice: pos.takeProfit, pnl: Number(pnl.toFixed(2)),
              pnlPct: Number(((pnl / pos.positionValue) * 100).toFixed(3)),
              isWin: pnl > 0, closedAt: new Date().toISOString(), closeReason: 'TAKE_PROFIT' },
            ...updated.closedTrades,
          ];
          updated.currentBalance = Number((updated.currentBalance + pnl).toFixed(2));
          updated.equityCurve    = [...updated.equityCurve, { date: today(), balance: updated.currentBalance }];
          notifs.push({ msg: ` Take Profit hit: ${pos.ticker} +${fmtUSD(pnl)}`, type: 'success' });
          return null; // remove from open
        }
      }
      return pos;
    }).filter(Boolean);

    if (changed) {
      notifs.forEach((n, i) => setTimeout(() => notify(n.msg, n.type), i * 1200));
    }
    return changed ? updated : acc;
  }, [notify]);

  // ─── WebSocket refs for live crypto prices ───────────────────
  const wsRefs = useRef({});  // ticker → WebSocket

  // Subscribe to Hyperliquid/Binance WS for open crypto positions
  useEffect(() => {
    if (!account) return;
    const cryptoTickers = [...new Set(
      account.openPositions
        .filter(p => p.status === 'OPEN' && isCrypto(p.ticker))
        .map(p => p.ticker)
    )];

    // Close WS for tickers no longer needed
    Object.keys(wsRefs.current).forEach(tk => {
      if (!cryptoTickers.includes(tk)) {
        wsRefs.current[tk]?.close();
        delete wsRefs.current[tk];
      }
    });

    // Open WS for new crypto tickers
    cryptoTickers.forEach(tk => {
      if (wsRefs.current[tk]) return; // already connected
      const coin = tk.split('-')[0].toUpperCase();
      try {
        const ws = new WebSocket('wss://api.hyperliquid.xyz/ws');
        ws.onopen = () => {
          ws.send(JSON.stringify({ method: 'subscribe', subscription: { type: 'candle', coin, interval: '1m' } }));
        };
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.channel === 'candle' && msg.data?.c) {
              const price = parseFloat(msg.data.c);
              // FIX 3: throttle live price updates per coin
              const now = Date.now();
              if (now - (livePriceThrottleRef.current[tk] || 0) < PRICE_THROTTLE_MS) return;
              livePriceThrottleRef.current[tk] = now;
              setLivePrices(prev => ({ ...prev, [tk]: price }));
            }
          } catch {}
        };
        ws.onerror = () => {};
        wsRefs.current[tk] = ws;
      } catch {}
    });

    return () => {
      // Cleanup handled per-effect, but keep WS alive across re-renders
    };
  }, [account?.openPositions?.length]); // eslint-disable-line

  // Cleanup all WS on unmount
  useEffect(() => {
    return () => {
      Object.values(wsRefs.current).forEach(ws => ws?.close());
    };
  }, []);

  // ═══════════════════════════════════════════════════════════════
  //  WATCHLIST — fetch prices + sparkline via polling
  // ═══════════════════════════════════════════════════════════════
  const saveWatchlist = useCallback((list) => {
    setWatchlist(list);
    localStorage.setItem('apexq_watchlist', JSON.stringify(list));
  }, []);

  const addToWatchlist = useCallback(() => {
    const tk = watchInput.trim().toUpperCase();
    if (!tk || watchlist.includes(tk)) { setWatchInput(''); return; }
    saveWatchlist([...watchlist, tk]);
    setWatchInput('');
  }, [watchInput, watchlist, saveWatchlist]);

  const removeFromWatchlist = useCallback((tk) => {
    saveWatchlist(watchlist.filter(t => t !== tk));
    // Close WS if crypto
    if (watchWsRefs.current[tk]) {
      watchWsRefs.current[tk]?.close();
      delete watchWsRefs.current[tk];
    }
  }, [watchlist, saveWatchlist]);

  // Poll non-crypto watch prices every 15s, subscribe WS for crypto
  useEffect(() => {
    const cryptoTickers  = watchlist.filter(isCrypto);
    const stockTickers   = watchlist.filter(t => !isCrypto(t));

    // ── WebSocket for crypto watchlist ──
    // Close WS for removed tickers
    Object.keys(watchWsRefs.current).forEach(tk => {
      if (!cryptoTickers.includes(tk)) {
        watchWsRefs.current[tk]?.close();
        delete watchWsRefs.current[tk];
      }
    });

    cryptoTickers.forEach(tk => {
      if (watchWsRefs.current[tk]) return;
      const coin = tk.split('-')[0].toUpperCase();
      try {
        const ws = new WebSocket('wss://api.hyperliquid.xyz/ws');
        ws.onopen = () => {
          ws.send(JSON.stringify({ method: 'subscribe', subscription: { type: 'candle', coin, interval: '1m' } }));
        };
        ws.onmessage = (e) => {
          try {
            const msg = JSON.parse(e.data);
            if (msg.channel === 'candle' && msg.data?.c) {
              const price = parseFloat(msg.data.c);
              const open  = parseFloat(msg.data.o);
              // FIX 3: throttle — skip jika coin ini sudah diupdate dalam 1 detik terakhir
              const now = Date.now();
              if (now - (watchPriceThrottleRef.current[tk] || 0) < PRICE_THROTTLE_MS) return;
              watchPriceThrottleRef.current[tk] = now;

              setWatchPrices(prev => {
                const existing = prev[tk] || {};
                const chgPct = open > 0 ? ((price - open) / open) * 100 : 0;
                // Append to sparkline (max 60 points)
                const spark = [...(existing.sparkline || []), price].slice(-60);
                return { ...prev, [tk]: { price, open, chgPct, sparkline: spark } };
              });
            }
          } catch {}
        };
        ws.onerror = () => {};
        watchWsRefs.current[tk] = ws;
      } catch {}
    });

    // ── Poll stock watchlist ──
    const fetchStockWatch = async () => {
      for (const tk of stockTickers) {
        try {
          const res = await axios.get(`${API}/api/apex-institutional/${tk}`, { timeout: 10000 });
          const price = res.data?.price;
          const open  = res.data?.open_price ?? price;
          if (!price) continue;
          const chgPct = open > 0 ? ((price - open) / open) * 100 : 0;
          setWatchPrices(prev => {
            const existing = prev[tk] || {};
            const spark = [...(existing.sparkline || []), price].slice(-60);
            return { ...prev, [tk]: { price, open, chgPct, sparkline: spark } };
          });
        } catch {}
      }
    };

    if (stockTickers.length) {
      fetchStockWatch();
      const id = setInterval(fetchStockWatch, 15000);
      return () => {
        clearInterval(id);
        Object.values(watchWsRefs.current).forEach(ws => ws?.close());
        watchWsRefs.current = {};
      };
    }
    return () => {
      Object.values(watchWsRefs.current).forEach(ws => ws?.close());
      watchWsRefs.current = {};
    };
  }, [watchlist]); // eslint-disable-line

  // ═══════════════════════════════════════════════════════════════
  //  STANDALONE CHART — bisa dibuka kapan saja, live WebSocket candle
  // ═══════════════════════════════════════════════════════════════
  const loadStandaloneChart = useCallback(async (ticker, tf = '1D') => {
    if (!ticker) return;
    setChartPanelLoading(true);
    setLiveCandle(null);
    // Close previous WS
    if (chartWsRef.current) { chartWsRef.current.close(); chartWsRef.current = null; }

    try {
      const res = await axios.get(`${API}/api/analyze/${ticker.trim().toUpperCase()}?tf=${tf}`, { timeout: 20000 });
      const data = res.data?.history ?? [];
      setStandaloneChart({ data, tf, ticker: ticker.trim().toUpperCase() });

      // ── Live WebSocket candle untuk crypto ──
      if (isCrypto(ticker)) {
        const coin = ticker.split('-')[0].toUpperCase();
        try {
          const ws = new WebSocket('wss://api.hyperliquid.xyz/ws');
          ws.onopen = () => {
            ws.send(JSON.stringify({ method: 'subscribe', subscription: { type: 'candle', coin, interval: tf === '1D' ? '1m' : '1m' } }));
          };
          ws.onmessage = (e) => {
            try {
              const msg = JSON.parse(e.data);
              if (msg.channel === 'candle' && msg.data) {
                const d = msg.data;
                setLiveCandle({
                  time:   Math.floor(parseInt(d.t) / 1000),
                  open:   parseFloat(d.o),
                  high:   parseFloat(d.h),
                  low:    parseFloat(d.l),
                  close:  parseFloat(d.c),
                  volume: parseFloat(d.v),
                });
              }
            } catch {}
          };
          ws.onerror = () => {};
          chartWsRef.current = ws;
        } catch {}
      }
    } catch {
      // silently fail
    } finally {
      setChartPanelLoading(false);
    }
  }, []); // eslint-disable-line

  // Re-load chart when TF changes
  useEffect(() => {
    if (standaloneChart?.ticker) {
      loadStandaloneChart(standaloneChart.ticker, chartPanelTf);
    }
  }, [chartPanelTf]); // eslint-disable-line

  // Cleanup chart WS on unmount
  useEffect(() => {
    return () => { chartWsRef.current?.close(); };
  }, []);

  // Polling for non-crypto open positions (10s interval)
  useEffect(() => {
    if (!account) return;
    const hasNonCrypto = account.openPositions.some(p => p.status === 'OPEN' && !isCrypto(p.ticker));
    const hasAnyOpen   = account.openPositions.some(p => p.status !== 'CLOSED');
    if (!hasAnyOpen) return;

    const run = async () => {
      // FIX 4: pakai accountRef.current agar selalu dapat versi terbaru, bukan stale closure
      const currentAcc = accountRef.current;
      if (!currentAcc) return;

      // For non-crypto: polling via apex endpoint
      const nonCryptoTickers = [...new Set(
        currentAcc.openPositions
          .filter(p => !isCrypto(p.ticker))
          .map(p => p.ticker)
      )];
      if (nonCryptoTickers.length) {
        const prices = await fetchLivePrices(currentAcc.openPositions.filter(p => !isCrypto(p.ticker)));
        if (prices) {
          setLivePrices(prev => {
            const merged = { ...prev, ...prices };
            // Check SL/TP/Limit triggers
            const updatedAcc = checkAutoExecutions(currentAcc, merged);
            if (updatedAcc !== currentAcc) saveAccount(updatedAcc);
            return merged;
          });
        }
      }
    };
    run();
    pollRef.current = setInterval(run, 10000); // 10s for stocks/equities
    return () => clearInterval(pollRef.current);
  }, [account?.openPositions?.length, account?.sessionId]); // eslint-disable-line

  // Auto-execute check when live prices update (crypto via WS)
  const prevLivePricesRef = useRef({});
  useEffect(() => {
    // FIX 4: gunakan accountRef.current bukan account dari closure
    // Tanpa ini: saat account diupdate (saveAccount), effect ini masih pakai versi lama account
    const acc = accountRef.current;
    if (!acc) return;
    const changed = Object.keys(livePrices).some(
      tk => livePrices[tk] !== prevLivePricesRef.current[tk]
    );
    if (!changed) return;
    prevLivePricesRef.current = livePrices;

    const updatedAcc = checkAutoExecutions(acc, livePrices);
    if (updatedAcc !== acc) saveAccount(updatedAcc);
  }, [livePrices]); // eslint-disable-line


  const handleSetup = async () => {
    const amount = Math.max(1000, Number(deposit) || 10000);
    let acc = makeAccount(amount);
    acc = await initArmor(acc);
    saveAccount(acc);
    setSetupMode(false);
    await refreshArmor(acc);
  };

  // ═══════════════════════════════════════════════════════════════
  //  GENERATE SIGNAL + CHART
  // ═══════════════════════════════════════════════════════════════
  const generateSignal = async () => {
    if (!sigTicker.trim()) return;
    setSigLoading(true);
    setChartLoading(true);
    setSigData(null);
    setRiskRec(null);
    setChartData(null);
    setTradeSetup(null);

    try {
      const [apexRes, riskRes, analyzeRes] = await Promise.all([
        axios.get(`${API}/api/apex-institutional/${sigTicker.trim()}`),
        account?.armorReady
          ? axios.post(`${API}/api/armor/risk-size`, {
              session_id:    account.sessionId,
              base_risk_pct: 2.0,
              win_rate:      0.55,
              rr_ratio:      2.0,
            })
          : Promise.resolve({ data: null }),
        axios.get(`${API}/api/analyze/${sigTicker.trim()}`),
      ]);

      const apex   = apexRes.data;
      const analyze = analyzeRes.data;

      setSigData(apex);
      setRiskRec(riskRes.data);

      // ── Build chart data ──────────────────────────────────────
      if (analyze?.history?.length) {
        setChartData(analyze.history);  // [{time, open, high, low, close, volume}] or [{time, value}]
      }

      // ── Compute trade setup recommendation ───────────────────
      const price     = apex?.price ?? apex?.current_price;
      const vol       = apex?.quant?.volatility;             // annualized vol %
      const verdict   = apex?.apex_score?.verdict ?? 'NEUTRAL';
      const ict       = apex?.ict_analysis;
      const score     = apex?.apex_score?.score ?? 50;
      const tradeGate = apex?.signals?.trade_gate ?? 'OPEN';

      if (price && vol) {
        const dailyMoveAmt = price * (vol / 100) / Math.sqrt(252);
        const direction    = verdict === 'BEARISH' ? 'SHORT' : 'LONG';

        // SL: 1.5× daily move, TP: 3× daily move (2:1 R:R)
        const slDist = dailyMoveAmt * 1.5;
        const tpDist = dailyMoveAmt * 3.0;

        // Try to use ICT swing levels if available
        const slPrice = direction === 'LONG'
          ? Math.max(ict?.swing_lows?.[0]?.price ?? (price - slDist), price - slDist * 2)
          : Math.min(ict?.swing_highs?.[0]?.price ?? (price + slDist), price + slDist * 2);
        const tpPrice = direction === 'LONG'
          ? price + tpDist
          : price - tpDist;

        const rrRatio = tpDist / slDist;
        const confidence = score >= 70 ? 'HIGH' : score >= 50 ? 'MEDIUM' : 'LOW';

        setTradeSetup({
          direction,
          entryPrice:  price,
          stopLoss:    Number(slPrice.toFixed(6)),
          takeProfit:  Number(tpPrice.toFixed(6)),
          rrRatio:     Number(rrRatio.toFixed(2)),
          confidence,
          tradeGate,
          dailyMove:   Number(dailyMoveAmt.toFixed(6)),
        });

        setForm(f => ({
          ...f,
          ticker:     sigTicker.trim().toUpperCase(),
          entryPrice: String(Number(price).toFixed(6)),
          limitPrice: String(Number(price).toFixed(6)),
          direction,
          stopLoss:   String(Number(slPrice.toFixed(6))),
          takeProfit: String(Number(tpPrice.toFixed(6))),
        }));
      } else {
        setForm(f => ({
          ...f,
          ticker:    sigTicker.trim().toUpperCase(),
          entryPrice: price ? String(Number(price).toFixed(6)) : f.entryPrice,
          direction: verdict === 'BEARISH' ? 'SHORT' : 'LONG',
        }));
      }
    } catch (e) {
      console.error('Signal error:', e);
      notify(' Analysis failed — check ticker or backend', 'error');
    } finally {
      setSigLoading(false);
      setChartLoading(false);
    }
  };

  // ── Execution busy state ─────────────────────────────────────
  const [execBusy, setExecBusy] = useState(false);

  // ═══════════════════════════════════════════════════════════════
  //  OPEN POSITION — broker-accurate sizing & fill
  // ═══════════════════════════════════════════════════════════════
  const openPosition = async () => {
    const { ticker, direction, orderType, entryPrice, limitPrice, stopLoss, takeProfit, notes } = form;
    if (!ticker || execBusy) return;

    const isLimit = orderType === 'LIMIT';
    const slVal   = stopLoss   ? Number(stopLoss)   : null;
    const tpVal   = takeProfit ? Number(takeProfit)  : null;

    // ── MARKET ORDER: fetch live price at moment of click ───────
    let fillPrice;
    if (isLimit) {
      fillPrice = Number(limitPrice);
      if (!fillPrice || fillPrice <= 0) { notify(' Limit price harus diisi', 'error'); return; }
    } else {
      // Fetch live price NOW (same as clicking "buy" at broker)
      setExecBusy(true);
      try {
        const res = await axios.get(`${API}/api/apex-institutional/${ticker}`, { timeout: 12000 });
        fillPrice = res.data?.price ?? Number(entryPrice);
        if (!fillPrice || fillPrice <= 0) throw new Error('No price');
        // Update live price cache
        setLivePrices(prev => ({ ...prev, [ticker]: fillPrice }));
      } catch {
        // Fallback to form value if backend unreachable
        fillPrice = Number(entryPrice);
        if (!fillPrice || fillPrice <= 0) {
          notify(' Tidak bisa fetch harga live — isi entry price manual', 'error');
          setExecBusy(false);
          return;
        }
        notify(' Pakai harga form (backend timeout)', 'error');
      } finally {
        setExecBusy(false);
      }
    }

    // ── POSITION SIZING — broker-accurate ────────────────────────
    // Rule 1: jika SL tersedia → shares = dollarRisk ÷ |entry - SL|
    //         (ini cara prop firm & trader profesional sizing)
    // Rule 2: jika tanpa SL → positionValue = dollarRisk × 10
    //         (fixed dollar exposure, pakai 5× risk sebagai position value)
    const dollarRisk = riskRec?.dollar_risk ?? (account.currentBalance * 0.02);
    const riskPct    = riskRec?.risk_pct ?? 2.0;

    let shares, positionValue;

    if (slVal && Math.abs(fillPrice - slVal) > 0) {
      //  CORRECT: risk-based sizing
      // shares = berapa unit yang bisa kita beli supaya jika harga hit SL,
      // kerugian kita tepat = dollarRisk
      const slDistance = Math.abs(fillPrice - slVal);
      shares           = dollarRisk / slDistance;
      positionValue    = shares * fillPrice;
    } else {
      // Fallback: gunakan 5× risk sebagai position value (leverage 1×)
      positionValue = Math.min(dollarRisk * 10, account.currentBalance * 0.5);
      shares        = positionValue / fillPrice;
    }

    const pos = {
      id:            Date.now(),
      ticker:        ticker.toUpperCase(),
      direction,
      orderType,
      status:        isLimit ? 'PENDING' : 'OPEN',
      entryPrice:    isLimit ? 0 : Number(fillPrice),   // 0 sampai limit terisi
      limitPrice:    isLimit ? Number(fillPrice) : null,
      stopLoss:      slVal ? Number(slVal.toFixed(8)) : null,
      takeProfit:    tpVal ? Number(tpVal.toFixed(8)) : null,
      shares:        Number(shares.toFixed(8)),
      positionValue: Number(positionValue.toFixed(2)),
      dollarRisk:    Number(dollarRisk.toFixed(2)),
      riskPct:       Number(riskPct.toFixed(3)),
      // Derived for display
      slDistance:    slVal ? Number(Math.abs(fillPrice - slVal).toFixed(8)) : null,
      openedAt:      new Date().toISOString(),
      notes,
      signal:        sigData?.apex_score?.verdict ?? '—',
      apexScore:     sigData?.apex_score?.score ?? 0,
      tradeGate:     sigData?.signals?.trade_gate ?? '—',
    };

    const updated = { ...account, openPositions: [...account.openPositions, pos] };
    saveAccount(updated);
    setForm({ ticker: '', direction: 'LONG', orderType: 'MARKET', entryPrice: '', limitPrice: '', stopLoss: '', takeProfit: '', notes: '' });
    setSigData(null); setRiskRec(null); setSigTicker(''); setChartData(null); setTradeSetup(null);

    const sizeStr = shares >= 1
      ? `${fmt(shares, 2)} unit`
      : `${fmt(shares, 6)} unit`;
    notify(isLimit
      ? ` Limit order placed: ${pos.ticker} ${direction} @ ${fmt(fillPrice, fillPrice < 10 ? 4 : 2)} · ${sizeStr}`
      : ` Filled: ${pos.ticker} ${direction} @ ${fmt(fillPrice, fillPrice < 10 ? 4 : 2)} · ${sizeStr} · Pos $${fmt(positionValue)}`,
      'success');
  };

  // ═══════════════════════════════════════════════════════════════
  //  CLOSE POSITION (manual)
  // ═══════════════════════════════════════════════════════════════
  const closePosition = async () => {
    if (!closeMeta?.posId || !closeMeta?.exitPrice) return;
    const pos = account.openPositions.find(p => p.id === closeMeta.posId);
    if (!pos) return;

    const exitPrice = Number(closeMeta.exitPrice);
    if (exitPrice <= 0) return;

    const useEntry = pos.status === 'OPEN' ? pos.entryPrice : pos.limitPrice;
    const rawPnl   = pos.direction === 'LONG'
      ? (exitPrice - useEntry) * pos.shares
      : (useEntry - exitPrice) * pos.shares;
    const pnl      = Number(rawPnl.toFixed(2));
    const pnlPct   = Number(((pnl / pos.positionValue) * 100).toFixed(3));

    const newBal = Number((account.currentBalance + (pos.status === 'OPEN' ? pnl : 0)).toFixed(2));

    const updated = {
      ...account,
      currentBalance: pos.status === 'OPEN' ? newBal : account.currentBalance,
      openPositions:  account.openPositions.filter(p => p.id !== closeMeta.posId),
      closedTrades:   [
        { ...pos, exitPrice, pnl, pnlPct, isWin: pnl > 0,
          closedAt: new Date().toISOString(), closeReason: 'MANUAL' },
        ...account.closedTrades,
      ],
      equityCurve: pos.status === 'OPEN'
        ? [...account.equityCurve, { date: today(), balance: newBal }]
        : account.equityCurve,
    };
    saveAccount(updated);
    setCloseMeta(null);

    if (account.armorReady && pos.status === 'OPEN') {
      try {
        await axios.post(`${API}/api/armor/record-trade`, {
          session_id: account.sessionId, pnl_usd: pnl, is_win: pnl > 0, date: today(),
        });
        await refreshArmor(updated);
      } catch {}
    }
  };

  // ═══════════════════════════════════════════════════════════════
  //  RESET
  // ═══════════════════════════════════════════════════════════════
  const resetAccount = () => {
    if (!confirm('Reset demo account? All trades will be erased.')) return;
    localStorage.removeItem(DEMO_KEY);
    setAccount(null); setArmor(null); setMilestones(null);
    setSigData(null); setRiskRec(null); setSetupMode(true);
    setChartData(null); setTradeSetup(null);
  };

  // ═══════════════════════════════════════════════════════════════
  //  DERIVED VALUES
  // ═══════════════════════════════════════════════════════════════
  const totalPnl    = account ? account.currentBalance - account.initialBalance : 0;
  const totalPnlPct = account ? (totalPnl / account.initialBalance) * 100 : 0;
  const wins        = account?.closedTrades.filter(t => t.isWin).length ?? 0;
  const winRate     = account?.closedTrades.length ? (wins / account.closedTrades.length) * 100 : 0;
  const armorMode   = armor?.operational_mode ?? (account?.armorReady ? 'ACTIVE' : 'OFFLINE');
  const riskScale   = armor?.final_risk_scale ?? 1.0;
  const modeColor   = MODE_COLOR[armorMode] ?? 'var(--ink3)';

  // Unrealized P&L for open positions
  const getUnrealizedPnl = (pos) => {
    if (pos.status !== 'OPEN') return 0;
    const lp = livePrices[pos.ticker] ?? pos.entryPrice;
    return pos.direction === 'LONG'
      ? (lp - pos.entryPrice) * pos.shares
      : (pos.entryPrice - lp) * pos.shares;
  };

  const totalUnrealized = account?.openPositions?.reduce((sum, p) => sum + getUnrealizedPnl(p), 0) ?? 0;

  // Close modal preview
  const previewPos  = closeMeta?.posId ? account?.openPositions.find(p => p.id === closeMeta.posId) : null;
  const previewExit = Number(closeMeta?.exitPrice) || (previewPos?.entryPrice ?? 0);
  const previewPnl  = previewPos
    ? (previewPos.direction === 'LONG'
        ? (previewExit - (previewPos.status === 'OPEN' ? previewPos.entryPrice : previewPos.limitPrice)) * previewPos.shares
        : ((previewPos.status === 'OPEN' ? previewPos.entryPrice : previewPos.limitPrice) - previewExit) * previewPos.shares)
    : 0;

  // ─── Chart data formatting ────────────────────────────────────
  const isOHLCV = chartData?.[0]?.open !== undefined;
  const chartSettings = { showEma1: true, ema1: 20, showEma2: true, ema2: 50, showVol: true };

  // ─────────────────────────────────────────────────────────────
  //  SETUP SCREEN
  // ─────────────────────────────────────────────────────────────
  if (setupMode || !account) {
    return (
      <div style={{ minHeight: '80vh', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 60 }}>
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 18, padding: '44px 52px', width: 500, textAlign: 'center' }}>
          <div style={{ width: 56, height: 56, background: 'var(--accent)', borderRadius: 14, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 22px', boxShadow: '0 0 32px var(--accent-glow)' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 800, color: '#fff' }}>DT</span>
          </div>
          <h2 style={{ fontSize: 24, fontWeight: 800, letterSpacing: '-0.025em', color: 'var(--ink)', marginBottom: 7 }}>Demo Trading</h2>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.14em', color: 'var(--ink3)', marginBottom: 34, textTransform: 'uppercase' }}>Paper Account · Risk-Free Simulation</p>

          <div style={{ marginBottom: 24, textAlign: 'left' }}>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ink4)', marginBottom: 10 }}>Virtual Deposit</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 10 }}>
              {[10000, 25000, 50000, 100000].map(amt => (
                <button key={amt} onClick={() => setDeposit(amt)} style={{ padding: '11px 0', background: deposit === amt ? 'var(--accent)' : 'var(--surface2)', border: `1px solid ${deposit === amt ? 'transparent' : 'var(--border)'}`, borderRadius: 9, cursor: 'pointer', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: deposit === amt ? '#fff' : 'var(--ink2)' }}>
                  ${(amt / 1000).toFixed(0)}K
                </button>
              ))}
            </div>
            <input type="number" value={deposit} onChange={e => setDeposit(Number(e.target.value))} placeholder="Custom amount..." style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 9, padding: '11px 14px', fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 700, color: 'var(--ink)' }} />
          </div>

          <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 18px', marginBottom: 26, textAlign: 'left' }}>
            {[
              ['', 'Apex Quant Engine: VaR, CVaR, Calmar, Omega, Fat Tail detection'],
              ['', 'Candlestick chart + EMA overlays for every analysis'],
              ['', 'Market & Limit orders — auto-executes when price hits'],
              ['', 'Auto Stop-Loss & Take-Profit from volatility-based setup'],
              ['', 'Equity Armor: milestone floors & Kelly-adjusted risk scaling'],
              ['', 'Crypto Orderbook (Hyperliquid) for BTC-USD / ETH-USD'],
            ].map(([icon, text], i) => (
              <div key={i} style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', letterSpacing: '0.04em', marginBottom: i < 5 ? 7 : 0, display: 'flex', gap: 9, alignItems: 'flex-start' }}>
                <span>{icon}</span><span>{text}</span>
              </div>
            ))}
          </div>

          <button onClick={handleSetup} style={{ width: '100%', background: 'var(--accent)', border: 'none', borderRadius: 11, padding: '15px 0', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#fff', cursor: 'pointer', boxShadow: '0 0 28px var(--accent-glow)' }}>
            Start with ${Number(deposit).toLocaleString()}
          </button>
        </div>
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────
  //  MAIN INTERFACE
  // ─────────────────────────────────────────────────────────────
  return (
    <div style={{ paddingTop: 24, paddingBottom: 80, position: 'relative' }}>

      {/* ── NOTIFICATION TOAST ──────────────────────────────── */}
      {notification && (
        <div style={{
          position: 'fixed', top: 24, right: 24, zIndex: 2000,
          background: notification.type === 'success' ? '#16a34a' : notification.type === 'error' ? '#dc2626' : 'var(--surface)',
          border: `1px solid ${notification.type === 'success' ? '#16a34a' : notification.type === 'error' ? '#dc2626' : 'var(--border)'}`,
          borderRadius: 10, padding: '12px 20px', maxWidth: 380,
          fontFamily: 'var(--mono)', fontSize: 10, color: '#fff',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          animation: 'slideIn 0.3s ease',
        }}>
          {notification.msg}
        </div>
      )}

      {/* ── TOP STRIP ─────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--pos)', boxShadow: '0 0 6px var(--pos)' }} className="pulse-dot" />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--ink3)' }}>
            Demo Mode · {account.sessionId.slice(5, 13)} · Polling {account.openPositions.length > 0 ? '🟢' : ''}
          </span>
        </div>
        <button onClick={resetAccount} style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 13px', fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', cursor: 'pointer' }}>
          ↺ Reset
        </button>
      </div>

      {/* ── ACCOUNT STATS STRIP ───────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 1, background: 'var(--border)', borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 20 }}>
        {[
          { label: 'Balance',       value: `$${fmt(account.currentBalance)}`,          color: 'var(--ink)' },
          { label: 'Total P&L',     value: fmtUSD(totalPnl),                           color: totalPnl >= 0 ? 'var(--pos)' : 'var(--neg)' },
          { label: 'Return',        value: fmtPct(totalPnlPct),                         color: totalPnl >= 0 ? 'var(--pos)' : 'var(--neg)' },
          { label: 'Unrealized',    value: totalUnrealized !== 0 ? fmtUSD(totalUnrealized) : '—', color: totalUnrealized >= 0 ? 'var(--pos)' : 'var(--neg)' },
          { label: 'Win Rate',      value: account.closedTrades.length ? `${fmt(winRate, 1)}%` : '—', color: winRate >= 50 ? 'var(--pos)' : 'var(--ink3)' },
          { label: 'Trades',        value: `${account.closedTrades.length}C · ${account.openPositions.length}O`, color: 'var(--ink2)' },
          { label: 'Armor Mode',    value: armorMode,                                   color: modeColor },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ background: 'var(--surface)', padding: '14px 16px' }}>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 5 }}>{label}</p>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color, letterSpacing: '-0.01em' }}>{value}</p>
          </div>
        ))}
      </div>

      {/* ── PAGE TAB SWITCHER ───────────────────────────────── */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 18, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', background: 'var(--surface)' }}>
        {[
          { id: 'demo', label: '  Demo Trading' },
          { id: 'hft',  label: '  HFT Bot (Spider)' },
        ].map(({ id, label }) => (
          <button key={id} onClick={() => setMainTab(id)} style={{
            flex: 1, padding: '11px 0', border: 'none', cursor: 'pointer',
            background: mainTab === id ? 'var(--surface2)' : 'transparent',
            borderBottom: mainTab === id ? '2px solid var(--accent)' : '2px solid transparent',
            fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.10em',
            textTransform: 'uppercase',
            color: mainTab === id ? 'var(--ink)' : 'var(--ink4)',
            fontWeight: mainTab === id ? 700 : 400,
            transition: 'all 0.15s',
          }}>{label}</button>
        ))}
      </div>

      {/* ── HFT BOT PANEL ─────────────────────────────────────── */}
      {mainTab === 'hft' && (
        <HFTBot initialBalance={account?.currentBalance || 1000} />
      )}

      {/* ── MAIN GRID ─────────────────────────────────────────── */}
      {mainTab === 'demo' && <div style={{ display: 'grid', gridTemplateColumns: '1fr 316px', gap: 16 }}>

        {/* ═══ LEFT ═══════════════════════════════════════════ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* ── WATCHLIST ─────────────────────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--pos)', boxShadow: '0 0 5px var(--pos)' }} className="pulse-dot" />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Watchlist</span>
              </div>
              {/* Add ticker input */}
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  value={watchInput}
                  onChange={e => setWatchInput(e.target.value.toUpperCase())}
                  onKeyDown={e => e.key === 'Enter' && addToWatchlist()}
                  placeholder="Add ticker…"
                  style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink)', width: 110 }}
                />
                <button onClick={addToWatchlist} style={{ background: 'var(--accent)', border: 'none', borderRadius: 6, padding: '4px 10px', fontFamily: 'var(--mono)', fontSize: 8, color: '#fff', cursor: 'pointer', letterSpacing: '0.08em' }}>+</button>
              </div>
            </div>

            {/* Watchlist grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
              {watchlist.map(tk => {
                const wp = watchPrices[tk];
                const chg = wp?.chgPct ?? 0;
                const isPos = chg >= 0;
                const spark = wp?.sparkline ?? [];
                // Mini SVG sparkline
                const sparkSvg = (() => {
                  if (spark.length < 2) return null;
                  const min = Math.min(...spark), max = Math.max(...spark);
                  const range = max - min || 1;
                  const w = 72, h = 26, pad = 2;
                  const pts = spark.map((v, i) => {
                    const x = (i / (spark.length - 1)) * (w - pad * 2) + pad;
                    const y = h - pad - ((v - min) / range) * (h - pad * 2);
                    return `${x.toFixed(1)},${y.toFixed(1)}`;
                  }).join(' ');
                  const color = isPos ? '#22c55e' : '#ef4444';
                  return (
                    <svg width={w} height={h} style={{ display: 'block' }}>
                      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" opacity={0.85} />
                    </svg>
                  );
                })();

                return (
                  <div
                    key={tk}
                    onClick={() => { setChartTicker(tk); loadStandaloneChart(tk, chartPanelTf); }}
                    style={{ background: 'var(--surface2)', border: `1px solid ${standaloneChart?.ticker === tk ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 9, padding: '10px 11px', cursor: 'pointer', position: 'relative', transition: 'border-color .15s' }}
                  >
                    {/* Remove btn */}
                    <button
                      onClick={e => { e.stopPropagation(); removeFromWatchlist(tk); }}
                      style={{ position: 'absolute', top: 4, right: 6, background: 'none', border: 'none', color: 'var(--ink4)', fontSize: 9, cursor: 'pointer', lineHeight: 1, padding: 0 }}
                    >×</button>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
                        {tk.replace('-USD', '')}
                      </span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 600, color: isPos ? 'var(--pos)' : 'var(--neg)' }}>
                        {wp ? `${isPos ? '+' : ''}${chg.toFixed(2)}%` : '—'}
                      </span>
                    </div>

                    <div style={{ marginBottom: 4 }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
                        {wp?.price
                          ? wp.price < 10 ? wp.price.toFixed(4) : wp.price < 1000 ? wp.price.toFixed(2) : wp.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                          : <span style={{ color: 'var(--ink4)', fontSize: 8 }}>Loading…</span>
                        }
                      </span>
                    </div>

                    {sparkSvg || <div style={{ height: 26 }} />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── STANDALONE CHART PANEL ───────────────────────── */}
          {(standaloneChart || chartPanelLoading) && (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 18 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    {isCrypto(standaloneChart?.ticker || '') && (
                      <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--pos)', boxShadow: '0 0 5px var(--pos)' }} className="pulse-dot" />
                    )}
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.01em' }}>
                      {standaloneChart?.ticker || chartTicker}
                    </span>
                  </div>
                  {/* TF buttons */}
                  <div style={{ display: 'flex', gap: 3 }}>
                    {['1D','1W','1M','1Y'].map(tf => (
                      <button key={tf} onClick={() => setChartPanelTf(tf)} style={{ background: chartPanelTf === tf ? 'var(--accent)' : 'transparent', color: chartPanelTf === tf ? '#fff' : 'var(--ink3)', border: `1px solid ${chartPanelTf === tf ? 'transparent' : 'var(--border)'}`, borderRadius: 5, padding: '3px 9px', fontFamily: 'var(--mono)', fontSize: 8, fontWeight: chartPanelTf === tf ? 600 : 400, letterSpacing: '0.10em', cursor: 'pointer' }}>{tf}</button>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {isCrypto(standaloneChart?.ticker || '') && liveCandle && (
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--pos)', letterSpacing: '0.08em' }}>● LIVE</span>
                  )}
                  <button onClick={() => { setStandaloneChart(null); setLiveCandle(null); chartWsRef.current?.close(); }} style={{ background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', cursor: 'pointer' }}> close</button>
                </div>
              </div>

              <div style={{ height: 360, borderRadius: 10, overflow: 'hidden', background: 'var(--surface2)', border: '1px solid var(--border)' }}>
                {chartPanelLoading ? (
                  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>Loading chart…</span>
                  </div>
                ) : standaloneChart?.data?.length ? (
                  standaloneChart.data[0]?.open !== undefined ? (
                    <PriceChart
                      data={standaloneChart.data}
                      settings={{ showEma1: true, ema1: 20, showEma2: true, ema2: 50, showVol: true }}
                      liveCandle={isCrypto(standaloneChart.ticker) ? liveCandle : null}
                      tf={standaloneChart.tf}
                    />
                  ) : (
                    <MarketOverview data={standaloneChart.data} openPrice={standaloneChart.data[0]?.value} tf={standaloneChart.tf} />
                  )
                ) : (
                  <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>No chart data</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── SIGNAL GENERATOR ─────────────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 22 }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 5px var(--accent-glow)' }} />
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Signal Generator</span>
              </div>
              <span className="badge badge-accent">Apex Engine v6</span>
            </div>

            {/* Ticker search */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
              <input
                value={sigTicker}
                onChange={e => setSigTicker(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && generateSignal()}
                placeholder="BBCA.JK, NVDA, BTC-USD, ETH-USD…"
                style={{ flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)' }}
              />
              <button onClick={generateSignal} disabled={sigLoading || !sigTicker.trim()} style={{ background: 'var(--accent)', border: 'none', borderRadius: 8, padding: '10px 22px', fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#fff', cursor: 'pointer', opacity: sigLoading || !sigTicker.trim() ? 0.5 : 1 }}>
                {sigLoading ? 'Scanning…' : 'Analyze →'}
              </button>
            </div>

            {/* ── SIGNAL RESULT ──────────────────────────────── */}
            {sigData && (() => {
              const q   = sigData.quant ?? {};
              const sig = sigData.signals ?? {};
              const ict = sigData.ict_analysis ?? {};
              const hmm = sigData.hmm_regime ?? {};
              const score = sigData.apex_score?.score ?? 0;
              const verdict = sigData.apex_score?.verdict ?? 'NEUTRAL';
              const price = sigData.price;

              return (
                <div style={{ marginBottom: 16 }}>

                  {/* Chart ─────────────────────────────────── */}
                  {(chartData || chartLoading) && (
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>
                          {sigTicker || form.ticker} · Price Chart
                        </span>
                        <button onClick={() => setShowChart(v => !v)} style={{ background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', cursor: 'pointer', letterSpacing: '0.08em' }}>
                          {showChart ? '▲ collapse' : '▼ expand'}
                        </button>
                      </div>
                      {showChart && (
                        <div style={{ height: 340, borderRadius: 10, overflow: 'hidden', background: 'var(--surface2)', border: '1px solid var(--border)' }}>
                          {chartLoading ? (
                            <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>Loading chart…</span>
                            </div>
                          ) : isOHLCV ? (
                            <PriceChart data={chartData} settings={chartSettings} liveCandle={isCrypto(sigTicker) ? liveCandle : null} tf="1D" />
                          ) : (
                            <MarketOverview data={chartData} openPrice={chartData?.[0]?.value} tf="1D" />
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── TOP METRICS ROW ──────────────────── */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 0, background: 'var(--surface2)', borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 12 }}>
                    {[
                      { label: 'Signal',     value: verdict,              color: verdictColor(verdict) },
                      { label: 'Apex Score', value: `${score}/100`,       color: score >= 70 ? 'var(--pos)' : score <= 30 ? 'var(--neg)' : 'var(--ink)' },
                      { label: 'Price',      value: price ? fmt(price, price < 10 ? 4 : 2) : '—', color: 'var(--ink)' },
                      { label: 'Trade Gate', value: sig.trade_gate ?? '—', color: sig.trade_gate === 'OPEN' ? 'var(--pos)' : 'var(--neg)' },
                      { label: 'Regime',     value: (hmm.current_regime ?? '—').replace(/_/g,' '), color: 'var(--blue)' },
                    ].map(({ label, value, color }) => (
                      <div key={label} style={{ textAlign: 'center', padding: '12px 6px', borderRight: '1px solid var(--border)' }}>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', marginBottom: 5, letterSpacing: '0.10em', textTransform: 'uppercase' }}>{label}</p>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color }}>{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* ── 2-COL: QUANT METRICS + TRADE SETUP ── */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>

                    {/* Quant Metrics ──────────────────────── */}
                    <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px' }}>
                      <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>Quant Metrics</p>
                      <QRow label="Volatility (Ann.)" value={q.volatility != null ? `${fmt(q.volatility, 2)}%` : '—'} />
                      <QRow label="Sortino Ratio"     value={q.sortino != null ? fmt(q.sortino, 3) : '—'} color={q.sortino > 1 ? 'var(--pos)' : q.sortino < 0 ? 'var(--neg)' : 'var(--ink2)'} />
                      <QRow label="Calmar Ratio"      value={q.calmar_ratio != null ? fmt(q.calmar_ratio, 3) : '—'} color={q.calmar_ratio > 0.5 ? 'var(--pos)' : 'var(--ink2)'} />
                      <QRow label="Omega Ratio"       value={q.omega_ratio != null ? fmt(q.omega_ratio, 3) : '—'} color={q.omega_ratio > 1 ? 'var(--pos)' : 'var(--neg)'} />
                      <QRow label="Max Drawdown"      value={q.max_drawdown != null ? `${fmt(q.max_drawdown, 2)}%` : '—'} color="var(--neg)" />
                      <QRow label="Ann. Return"       value={q.ann_return_pct != null ? `${fmt(q.ann_return_pct, 2)}%` : '—'} color={q.ann_return_pct > 0 ? 'var(--pos)' : 'var(--neg)'} />
                    </div>

                    {/* Risk Metrics + Trade Setup ─────────── */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', flex: 1 }}>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8 }}>Risk Metrics</p>
                        <QRow label="VaR 95% (Hist.)" value={q.var_95_hist_pct != null ? `${fmt(q.var_95_hist_pct, 3)}%` : '—'} color="var(--neg)" />
                        <QRow label="CVaR 95% (Hist.)" value={q.cvar_95_hist_pct != null ? `${fmt(q.cvar_95_hist_pct, 3)}%` : '—'} color="var(--neg)" />
                        <QRow label="VaR 95% (CF)"    value={q.var_95_cf_pct != null ? `${fmt(q.var_95_cf_pct, 3)}%` : '—'} color="var(--neg)" />
                        <QRow label="Skewness"        value={q.skewness != null ? fmt(q.skewness, 3) : '—'} color={q.skewness < -0.5 ? 'var(--neg)' : 'var(--ink2)'} />
                        <QRow label="Excess Kurtosis" value={q.excess_kurtosis != null ? fmt(q.excess_kurtosis, 2) : '—'} color={q.excess_kurtosis > 3 ? 'var(--neg)' : 'var(--ink2)'} />
                        <QRow label="Fat Tail Risk"   value={q.fat_tail ? 'YES ' : 'NORMAL'} badge={q.fat_tail ? 'badge-red' : 'badge-green'} />
                      </div>
                    </div>
                  </div>

                  {/* ── ICT + Signals row ────────────────── */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8, marginBottom: 12 }}>
                    {[
                      { label: 'ICT Bias',   value: sig.ict_bias ?? '—', color: verdictColor(sig.ict_bias) },
                      { label: 'Momentum',   value: sig.momentum_signal ?? '—', color: verdictColor(sig.momentum_signal) },
                      { label: 'Kelly Edge', value: sig.kelly_edge ?? '—', color: sig.kelly_edge === 'STRONG' ? 'var(--pos)' : sig.kelly_edge === 'WEAK' ? 'var(--neg)' : 'var(--ink2)' },
                      { label: 'Z-Score',    value: sig.zscore_signal ?? '—', color: verdictColor(sig.zscore_signal) },
                    ].map(({ label, value, color }) => (
                      <div key={label} style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px' }}>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</p>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color }}>{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* ── TRADE SETUP RECOMMENDATION ───────── */}
                  {tradeSetup && (
                    <div style={{ background: tradeSetup.tradeGate === 'OPEN' ? '#16a34a0c' : '#dc262608', border: `1px solid ${tradeSetup.tradeGate === 'OPEN' ? 'var(--pos-b)' : 'var(--neg-b)'}`, borderRadius: 10, padding: '12px 14px', marginBottom: 10 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Apex Setup Recommendation</span>
                          <span className={`badge ${tradeSetup.confidence === 'HIGH' ? 'badge-green' : tradeSetup.confidence === 'MEDIUM' ? 'badge-amber' : 'badge-red'}`} style={{ fontSize: 9 }}>
                            {tradeSetup.confidence} CONF
                          </span>
                        </div>
                        {tradeSetup.tradeGate === 'OPEN'
                          ? <span className="badge badge-green" style={{ fontSize: 9 }}>GATE OPEN </span>
                          : <span className="badge badge-red"   style={{ fontSize: 9 }}>GATE CLOSED </span>
                        }
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 8 }}>
                        {[
                          { label: 'Direction',    value: tradeSetup.direction, color: tradeSetup.direction === 'LONG' ? 'var(--pos)' : 'var(--neg)' },
                          { label: 'Entry (Mkt)',  value: fmt(tradeSetup.entryPrice, tradeSetup.entryPrice < 10 ? 4 : 2), color: 'var(--ink)' },
                          { label: 'Stop Loss',    value: fmt(tradeSetup.stopLoss, tradeSetup.stopLoss < 10 ? 4 : 2),    color: 'var(--neg)' },
                          { label: 'Take Profit',  value: fmt(tradeSetup.takeProfit, tradeSetup.takeProfit < 10 ? 4 : 2), color: 'var(--pos)' },
                        ].map(({ label, value, color }) => (
                          <div key={label} style={{ textAlign: 'center' }}>
                            <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 3 }}>{label}</p>
                            <p style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color }}>{value}</p>
                          </div>
                        ))}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)' }}>
                          R:R = 1 : {tradeSetup.rrRatio} · Daily σ = {fmt(tradeSetup.dailyMove, tradeSetup.dailyMove < 1 ? 4 : 2)}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)' }}>
                          SL/TP auto-filled ↓
                        </span>
                      </div>
                    </div>
                  )}

                  {/* ── ARMOR RISK SIZE ────────────────────── */}
                  {riskRec ? (
                    <div style={{ background: 'var(--surface)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase', marginBottom: 4 }}>Armor Risk Recommendation</p>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>Kelly-adjusted · Risk scale {fmt(riskScale * 100, 0)}%</p>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 800, color: 'var(--amber)', letterSpacing: '-0.02em' }}>{fmtUSD(riskRec.dollar_risk ?? 0)}</p>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>{fmt(riskRec.risk_pct ?? 0, 3)}% of equity</p>
                      </div>
                    </div>
                  ) : (
                    <div style={{ background: 'var(--surface3)', borderRadius: 8, padding: '10px 14px', border: '1px solid var(--border)' }}>
                      <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)' }}>Armor offline — default 2% risk applied.</p>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* ── TRADE ENTRY FORM ─────────────────────────────── */}
            <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', marginTop: 4 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 12 }}>New Order</p>

              {/* Row 1: Ticker / Direction / Order Type */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 10 }}>
                <div>
                  <p style={LBL}>Ticker</p>
                  <input value={form.ticker} onChange={e => setForm(f => ({ ...f, ticker: e.target.value.toUpperCase() }))} placeholder="TICKER" style={INPUT} />
                </div>
                <div>
                  <p style={LBL}>Direction</p>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {['LONG','SHORT'].map(d => (
                      <button key={d} onClick={() => setForm(f => ({ ...f, direction: d }))} style={{ flex: 1, padding: '9px 0', cursor: 'pointer', background: form.direction === d ? (d === 'LONG' ? '#16a34a22' : '#dc262622') : 'var(--surface)', border: `1px solid ${form.direction === d ? (d === 'LONG' ? 'var(--pos-b)' : 'var(--neg-b)') : 'var(--border)'}`, borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600, color: form.direction === d ? (d === 'LONG' ? 'var(--pos)' : 'var(--neg)') : 'var(--ink3)' }}>{d}</button>
                    ))}
                  </div>
                </div>
                <div>
                  <p style={LBL}>Order Type</p>
                  <div style={{ display: 'flex', gap: 5 }}>
                    {['MARKET','LIMIT'].map(t => (
                      <button key={t} onClick={() => setForm(f => ({ ...f, orderType: t }))} style={{ flex: 1, padding: '9px 0', cursor: 'pointer', background: form.orderType === t ? 'var(--accent)' : 'var(--surface)', border: `1px solid ${form.orderType === t ? 'transparent' : 'var(--border)'}`, borderRadius: 7, fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 600, color: form.orderType === t ? '#fff' : 'var(--ink3)' }}>{t}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Row 2: Entry/Limit Price / SL / TP */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
                {/* Price input — changes label & behavior based on order type */}
                <div>
                  {form.orderType === 'MARKET' ? (
                    <>
                      <p style={LBL}>Entry Price (Live on fill)</p>
                      <div style={{ ...INPUT, display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--surface3)', color: 'var(--ink3)', cursor: 'default' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                          {form.entryPrice ? `≈ ${fmt(Number(form.entryPrice), Number(form.entryPrice) < 10 ? 4 : 2)}` : 'Fetched at submit'}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>LIVE ●</span>
                      </div>
                      <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', marginTop: 3 }}>Harga final = live price saat submit</p>
                    </>
                  ) : (
                    <>
                      <p style={LBL}>Limit Price</p>
                      <input type="number" value={form.limitPrice} onChange={e => setForm(f => ({ ...f, limitPrice: e.target.value }))} placeholder="0.00" style={{ ...INPUT, borderColor: 'var(--amber)' }} />
                      <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--amber)', marginTop: 3 }}>Eksekusi otomatis saat harga menyentuh limit</p>
                    </>
                  )}
                </div>
                <div>
                  <p style={{ ...LBL, color: 'var(--neg)' }}>Stop Loss</p>
                  <input type="number" value={form.stopLoss} onChange={e => setForm(f => ({ ...f, stopLoss: e.target.value }))} placeholder="0.00" style={{ ...INPUT, borderColor: form.stopLoss ? 'var(--neg-b)' : 'var(--border)' }} />
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', marginTop: 3 }}>Auto-closes on hit</p>
                </div>
                <div>
                  <p style={{ ...LBL, color: 'var(--pos)' }}>Take Profit</p>
                  <input type="number" value={form.takeProfit} onChange={e => setForm(f => ({ ...f, takeProfit: e.target.value }))} placeholder="0.00" style={{ ...INPUT, borderColor: form.takeProfit ? 'var(--pos-b)' : 'var(--border)' }} />
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)', marginTop: 3 }}>Auto-closes on hit</p>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <input value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} placeholder="Notes (optional)…" style={{ flex: 1, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '9px 12px', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink)' }} />
                <button
                  onClick={openPosition}
                  disabled={execBusy || !form.ticker || (form.orderType === 'LIMIT' && !form.limitPrice)}
                  style={{ background: form.direction === 'LONG' ? 'var(--pos)' : 'var(--neg)', border: 'none', borderRadius: 8, padding: '9px 24px', fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, letterSpacing: '0.10em', textTransform: 'uppercase', color: '#fff', cursor: execBusy ? 'wait' : 'pointer', whiteSpace: 'nowrap', opacity: (execBusy || !form.ticker || (form.orderType === 'LIMIT' && !form.limitPrice)) ? 0.5 : 1, transition: 'all .15s', minWidth: 140 }}
                >
                  {execBusy
                    ? '⏳ Fetching price…'
                    : form.orderType === 'LIMIT'
                      ? ' Place Limit'
                      : `↑ Open ${form.direction}`}
                </button>
              </div>
            </div>
          </div>

          {/* ── POSITIONS / HISTORY TABS ─────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, overflow: 'hidden' }}>
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
              {[
                { id: 'positions', label: `Open (${account.openPositions.length})` },
                { id: 'pending',   label: `Pending (${account.openPositions.filter(p => p.status === 'PENDING').length})` },
                { id: 'history',   label: `History (${account.closedTrades.length})` },
              ].map(({ id, label }) => (
                <button key={id} onClick={() => setTab(id)} style={{ flex: 1, padding: '13px 16px', border: 'none', cursor: 'pointer', background: tab === id ? 'var(--surface2)' : 'transparent', borderBottom: tab === id ? '2px solid var(--accent)' : '2px solid transparent', fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.10em', textTransform: 'uppercase', color: tab === id ? 'var(--ink)' : 'var(--ink3)' }}>{label}</button>
              ))}
            </div>

            {/* ── Open Positions ── */}
{tab === 'positions' && (() => {
  const openPos = account.openPositions.filter(p => p.status === 'OPEN');
  return openPos.length === 0 ? (
    <div style={{ padding: '36px 0', textAlign: 'center' }}>
      <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>No open positions.</p>
    </div>
  ) : (
    <div>
      {/* HEADER */}
      <div style={{ 
        display: 'grid', 
        // 1. Ukuran grid kolom disamakan
        gridTemplateColumns: '80px 60px 100px 100px 110px 160px 100px 1fr', 
        padding: '8px 16px', 
        borderBottom: '1px solid var(--border)', 
        gap: 8 // Gap 8
      }}>
        {['Ticker','Dir','Entry','Live Price','Unr. P&L','Size / Pos Value','SL · TP',''].map(h => (
          <span key={h} style={{ 
            fontFamily: 'var(--mono)', 
            fontSize: 10, 
            color: 'var(--ink4)', 
            letterSpacing: '0.10em', 
            textTransform: 'uppercase',
            whiteSpace: 'nowrap'
          }}>
            {h}
          </span>
        ))}
      </div>

      {/* DATA ROWS */}
      {openPos.map(pos => {
        const liveP  = livePrices[pos.ticker];
        const unrPnl = getUnrealizedPnl(pos);
        const unrPct = pos.positionValue ? (unrPnl / pos.positionValue) * 100 : 0;
        return (
          <div key={pos.id} style={{ 
            display: 'grid', 
            // 2. PAstikan gridTemplateColumns persis dengan header
            gridTemplateColumns: '80px 60px 100px 100px 110px 160px 100px 1fr', 
            padding: '12px 16px', 
            borderBottom: '1px solid var(--border)', 
            alignItems: 'center', 
            gap: 8, // 3. Samakan gap dengan header (dari 4 jadi 8) agar tidak geser
            background: unrPnl > 0 ? '#16a34a04' : unrPnl < 0 ? '#dc262604' : 'transparent' 
          }}>
            <div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', marginBottom: 2 }}>{pos.ticker}</p>
              {pos.signal !== '—' && <span className={`badge ${pos.signal === 'BULLISH' ? 'badge-green' : 'badge-red'}`} style={{ fontSize: 9 }}>{pos.signal}</span>}
            </div>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: pos.direction === 'LONG' ? 'var(--pos)' : 'var(--neg)' }}>{pos.direction}</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>{fmt(pos.entryPrice, pos.entryPrice < 10 ? 4 : 2)}</span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', fontWeight: liveP ? 600 : 400 }}>
              {liveP ? fmt(liveP, liveP < 10 ? 4 : 2) : '—'}
            </span>
            <div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: unrPnl >= 0 ? 'var(--pos)' : 'var(--neg)' }}>
                {liveP ? fmtUSD(unrPnl) : '—'}
              </p>
              {liveP && <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: unrPnl >= 0 ? 'var(--pos)' : 'var(--neg)' }}>{fmtPct(unrPct)}</p>}
            </div>
            <div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', fontWeight: 600 }}>
                {pos.shares >= 1 ? fmt(pos.shares, 2) : fmt(pos.shares, 5)} {pos.ticker.split('.')[0].split('-')[0]}
              </p>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)' }}>${fmt(pos.positionValue)} pos</p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--neg)' }}>
                {pos.stopLoss ? `SL ${fmt(pos.stopLoss, pos.stopLoss < 10 ? 4 : 2)}` : ' No SL'}
              </span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--pos)' }}>
                {pos.takeProfit ? `TP ${fmt(pos.takeProfit, pos.takeProfit < 10 ? 4 : 2)}` : ' No TP'}
              </span>
            </div>
            <button
              onClick={() => setCloseMeta({ posId: pos.id, exitPrice: String(liveP ?? pos.entryPrice) })}
              style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 10px', fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.10em', color: 'var(--ink3)', cursor: 'pointer' }}>
              Close
            </button>
          </div>
        );
      })}
    </div>
  );
})()}

            {/* ── Pending Limit Orders ── */}
            {tab === 'pending' && (() => {
              const pending = account.openPositions.filter(p => p.status === 'PENDING');
              return pending.length === 0 ? (
                <div style={{ padding: '36px 0', textAlign: 'center' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>No pending limit orders.</p>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '80px 54px 100px 90px 90px 1fr', padding: '8px 16px', borderBottom: '1px solid var(--border)', gap: 4 }}>
                    {['Ticker','Dir','Limit Price','Current Price','Status',''].map(h => (
                      <span key={h} style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>{h}</span>
                    ))}
                  </div>
                  {pending.map(pos => {
                    const liveP = livePrices[pos.ticker];
                    const dist  = liveP ? Math.abs(liveP - pos.limitPrice) / pos.limitPrice * 100 : null;
                    return (
                      <div key={pos.id} style={{ display: 'grid', gridTemplateColumns: '80px 54px 100px 90px 90px 1fr', padding: '12px 16px', borderBottom: '1px solid var(--border)', alignItems: 'center', gap: 4 }}>
                        <p style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>{pos.ticker}</p>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: pos.direction === 'LONG' ? 'var(--pos)' : 'var(--neg)' }}>{pos.direction}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--amber)', fontWeight: 700 }}>{fmt(pos.limitPrice, pos.limitPrice < 10 ? 4 : 2)}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>{liveP ? fmt(liveP, liveP < 10 ? 4 : 2) : '—'}</span>
                        <div>
                          <span className="badge badge-amber" style={{ fontSize: 9 }}>PENDING</span>
                          {dist != null && <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', marginTop: 2 }}>{fmt(dist, 2)}% away</p>}
                        </div>
                        <button
                          onClick={() => { const updated = { ...account, openPositions: account.openPositions.filter(p => p.id !== pos.id) }; saveAccount(updated); }}
                          style={{ background: 'var(--surface2)', border: '1px solid var(--neg-b)', borderRadius: 5, padding: '4px 10px', fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--neg)', cursor: 'pointer' }}>
                          Cancel
                        </button>
                      </div>
                    );
                  })}
                </div>
              );
            })()}

            {/* ── Trade History ── */}
            {tab === 'history' && (
              account.closedTrades.length === 0 ? (
                <div style={{ padding: '36px 0', textAlign: 'center' }}>
                  <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>No completed trades yet.</p>
                </div>
              ) : (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '78px 54px 88px 88px 100px 76px 72px 72px', padding: '8px 16px', borderBottom: '1px solid var(--border)', gap: 4 }}>
                    {['Ticker','Dir','Entry','Exit','P&L $','P&L %','Result','Reason'].map(h => (
                      <span key={h} style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>{h}</span>
                    ))}
                  </div>
                  {account.closedTrades.map(t => (
                    <div key={t.id} style={{ display: 'grid', gridTemplateColumns: '78px 54px 88px 88px 100px 76px 72px 72px', padding: '11px 16px', borderBottom: '1px solid var(--border)', alignItems: 'center', gap: 4, background: t.isWin ? '#16a34a08' : '#dc262608' }}>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>{t.ticker}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600, color: t.direction === 'LONG' ? 'var(--pos)' : 'var(--neg)' }}>{t.direction}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>{fmt(t.entryPrice ?? t.limitPrice, 4)}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)' }}>{fmt(t.exitPrice, 4)}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: t.pnl >= 0 ? 'var(--pos)' : 'var(--neg)' }}>{fmtUSD(t.pnl)}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: t.pnl >= 0 ? 'var(--pos)' : 'var(--neg)' }}>{fmtPct(t.pnlPct)}</span>
                      <span className={`badge ${t.isWin ? 'badge-green' : 'badge-red'}`} style={{ fontSize: 11 }}>{t.isWin ? 'WIN' : 'LOSS'}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>{t.closeReason ?? 'MANUAL'}</span>
                    </div>
                  ))}
                </div>
              )
            )}
          </div>
        </div>

        {/* ═══ RIGHT SIDEBAR ═══════════════════════════════════ */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Equity Curve ──────────────────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Equity Curve</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: totalPnl >= 0 ? 'var(--pos)' : 'var(--neg)' }}>{fmtPct(totalPnlPct)}</span>
            </div>
            <EquityCurve data={account.equityCurve} w={280} h={68} />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>Init: ${fmt(account.initialBalance)}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>Now: ${fmt(account.currentBalance)}</span>
            </div>
          </div>

          {/* Equity Armor ──────────────────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}> Equity Armor</span>
              {armorBusy
                ? <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>updating…</span>
                : <span className={`badge ${armorMode === 'FULL' || armorMode === 'ACTIVE' ? 'badge-green' : armorMode === 'REDUCED' ? 'badge-amber' : 'badge-red'}`}>{armorMode}</span>
              }
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>Risk Scale</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: modeColor }}>{fmt(riskScale * 100, 0)}%</span>
              </div>
              <ScaleBar value={riskScale} color={modeColor} />
            </div>
            {[
              ['HWM Balance',  armor?.trailing_stop?.hwm != null ? `$${fmt(armor.trailing_stop.hwm)}` : `$${fmt(account.currentBalance)}`],
              ['Stop Level',   armor?.trailing_stop?.stop_level != null ? `$${fmt(armor.trailing_stop.stop_level)}` : '—'],
              ['Active Floor', armor?.milestone?.locked_floor_pct != null ? `+${armor.milestone.locked_floor_pct}%` : 'BASE (0%)'],
              ['Sharpe',       armor?.performance?.sharpe_ratio != null ? fmt(armor.performance.sharpe_ratio, 2) : '—'],
              ['Max DD',       armor?.performance?.max_drawdown_pct != null ? `${fmt(armor.performance.max_drawdown_pct, 2)}%` : '—'],
              ['Edge',         armor?.edge_monitor?.status ?? (account.armorReady ? 'NORMAL' : 'OFFLINE')],
            ].map(([label, value]) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{label}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color: 'var(--ink2)' }}>{value}</span>
              </div>
            ))}
            <button onClick={() => refreshArmor(account)} disabled={armorBusy} style={{ width: '100%', marginTop: 12, background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 7, padding: '8px 0', fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', cursor: armorBusy ? 'default' : 'pointer', opacity: armorBusy ? 0.5 : 1 }}>
              {armorBusy ? 'Refreshing…' : '↺ Refresh Armor'}
            </button>
            {!account.armorReady && (
              <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--neg)', marginTop: 8, textAlign: 'center' }}> Backend offline — armor inactive</p>
            )}
          </div>

          {/* Orderbook (crypto only) ────────────────────────── */}
          {sigData && isCrypto(sigData.ticker) && (
            <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, overflow: 'hidden' }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Orderbook</span>
                  <span className="badge badge-accent" style={{ fontSize: 9 }}>Hyperliquid</span>
                </div>
              </div>
              <Orderbook ticker={sigData.ticker} />
            </div>
          )}

          {/* Milestone Ladder ──────────────────────────────── */}
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 13, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>Milestone Ladder</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>floor locks at prev</span>
            </div>
            {(() => {
              const ladder = milestones?.full_ladder ?? [
                { level_pct: 5,   floor_pct: 0,   reached: account.currentBalance >= account.initialBalance * 1.05 },
                { level_pct: 10,  floor_pct: 5,   reached: account.currentBalance >= account.initialBalance * 1.10 },
                { level_pct: 20,  floor_pct: 10,  reached: account.currentBalance >= account.initialBalance * 1.20 },
                { level_pct: 30,  floor_pct: 20,  reached: account.currentBalance >= account.initialBalance * 1.30 },
                { level_pct: 50,  floor_pct: 30,  reached: account.currentBalance >= account.initialBalance * 1.50 },
                { level_pct: 75,  floor_pct: 50,  reached: account.currentBalance >= account.initialBalance * 1.75 },
                { level_pct: 100, floor_pct: 75,  reached: account.currentBalance >= account.initialBalance * 2.00 },
              ];
              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {ladder.map((m, i) => {
                    const isNext    = !m.reached && (i === 0 || ladder[i-1]?.reached);
                    const targetBal = account.initialBalance * (1 + m.level_pct / 100);
                    return (
                      <div key={i} style={{ borderRadius: 6, overflow: 'hidden', border: `1px solid ${m.reached ? 'var(--pos-b)' : isNext ? 'var(--border2)' : 'var(--border)'}`, opacity: m.reached ? 1 : isNext ? 0.9 : 0.45 }}>
                        <div style={{ padding: '6px 10px', background: m.reached ? '#16a34a0c' : isNext ? 'var(--surface2)' : 'transparent', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 9 }}>{m.reached ? '' : isNext ? '→' : '○'}</span>
                            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600, color: m.reached ? 'var(--pos)' : isNext ? 'var(--ink)' : 'var(--ink3)' }}>+{m.level_pct}%</span>
                            {isNext && <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>${fmt(targetBal, 0)}</span>}
                          </div>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)' }}>floor +{m.floor_pct}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>
        </div>
      </div>

      }  {/* end mainTab==='demo' grid */}

      {/* ═══ CLOSE MODAL ═══════════════════════════════════════ */}
      {closeMeta && previewPos && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(10px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 18, padding: '36px 40px', width: 420 }}>
            <h3 style={{ fontSize: 18, fontWeight: 800, color: 'var(--ink)', marginBottom: 5 }}>Close Position</h3>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', marginBottom: 8 }}>
              {previewPos.direction} {previewPos.ticker} · entry @ {fmt(previewPos.entryPrice || previewPos.limitPrice, 4)}
            </p>
            {livePrices[previewPos.ticker] && (
              <div style={{ background: 'var(--surface2)', borderRadius: 8, padding: '8px 12px', marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)' }}>LIVE PRICE</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700, color: 'var(--ink)' }}>{fmt(livePrices[previewPos.ticker], livePrices[previewPos.ticker] < 10 ? 4 : 2)}</span>
              </div>
            )}
            <div style={{ marginBottom: 18 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', marginBottom: 7, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Exit Price</p>
              <input autoFocus type="number" value={closeMeta.exitPrice} onChange={e => setCloseMeta(m => ({ ...m, exitPrice: e.target.value }))} onKeyDown={e => e.key === 'Enter' && closePosition()} style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 9, padding: '13px 16px', fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color: 'var(--ink)' }} />
            </div>
            <div style={{ background: previewPnl >= 0 ? '#16a34a12' : '#dc262612', border: `1px solid ${previewPnl >= 0 ? 'var(--pos-b)' : 'var(--neg-b)'}`, borderRadius: 11, padding: '16px 18px', marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>Estimated P&L</p>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>{fmt(previewPos.shares, 4)} shares × Δ{fmt(previewExit - (previewPos.entryPrice || previewPos.limitPrice), 4)}</p>
              </div>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 26, fontWeight: 800, color: previewPnl >= 0 ? 'var(--pos)' : 'var(--neg)', letterSpacing: '-0.03em' }}>{fmtUSD(previewPnl)}</p>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setCloseMeta(null)} style={{ flex: 1, background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 9, padding: '12px 0', fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', cursor: 'pointer' }}>Cancel</button>
              <button onClick={closePosition} style={{ flex: 2, background: previewPnl >= 0 ? 'var(--pos)' : 'var(--neg)', border: 'none', borderRadius: 9, padding: '12px 0', fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: '#fff', cursor: 'pointer' }}>
                Confirm · {fmtUSD(previewPnl)}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Shared styles ────────────────────────────────────────────────
const LBL = {
  fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink4)',
  marginBottom: 5, letterSpacing: '0.10em', textTransform: 'uppercase',
};
const INPUT = {
  width: '100%', boxSizing: 'border-box',
  background: 'var(--surface)', border: '1px solid var(--border)',
  borderRadius: 8, padding: '9px 12px',
  fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)',
};