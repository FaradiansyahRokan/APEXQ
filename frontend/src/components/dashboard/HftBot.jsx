/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  APEX HFT  ·  v4.0  —  Dual Engine                              ║
 * ║  🕷 Predator  →  mean-reversion VWAP microstructure             ║
 * ║  🐺 Jackal   →  micro-momentum burst scalper                    ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

import { API as _API, WS_URL } from '../../config';
const API = _API;

// ─── Engine definitions ───────────────────────────────────────────────────────
const ENGINES = {
  predator: {
    id       : 'predator',
    name     : 'Predator',
    emoji    : '🕷',
    subtitle : 'Mean-reversion · VWAP microstructure',
    strategy : 'mean_reversion',
    badge    : 'v2',
    color    : 'var(--ink)',           // neutral / system color
    apiBase  : '/api/hft',
    wsPath   : '/ws/hft',
    defaultCfg: {
      max_positions    : 3,
      capital_per_trade: 100,
      zscore_entry     : 1.8,
      atr_stop_mult    : 1.5,
      min_rr_ratio     : 2.5,
      max_hold_seconds : 60,
      scan_interval    : 0.5,
      long_bias        : false,
    },
  },
  jackal: {
    id       : 'jackal',
    name     : 'Jackal',
    emoji    : '🐺',
    subtitle : 'Micro-momentum burst · 3-tick streak entry',
    strategy : 'micro_momentum_burst',
    badge    : 'v1',
    color    : 'var(--amber)',
    apiBase  : '/api/hft-rapid',
    wsPath   : '/ws/hft-rapid',
    defaultCfg: {
      max_positions      : 5,
      capital_per_trade  : 50,
      min_streak         : 3,
      min_move_pct       : 0.020,
      ofi_floor          : 0.35,
      ofi_ceiling        : 0.65,
      tp_pct             : 0.10,
      sl_pct             : 0.07,
      max_hold_seconds   : 10,
      scan_interval      : 0.07,
      max_daily_dd_pct   : 3.0,
      lock_step_pct      : 0.50,
      lock_ratio         : 0.60,
      max_spread_pct     : 0.08,
    },
  },
};

// ─── Formatters ───────────────────────────────────────────────────────────────
const fmt    = (n, d = 2)  => Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmtPct = (n)         => `${n >= 0 ? '+' : ''}${fmt(n, 3)}%`;
const fmtUSD = (n)         => `${n >= 0 ? '+' : '−'}$${fmt(Math.abs(n || 0), 2)}`;
const fmtS   = (s)         => s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${Math.round(s)}s`;
const clr    = (n)         => n > 0 ? 'var(--pos)' : n < 0 ? 'var(--neg)' : 'var(--ink3)';
const clrDim = (n)         => n > 0 ? 'var(--pos-dim)' : n < 0 ? 'var(--neg-dim)' : 'transparent';
const clrB   = (n)         => n > 0 ? 'var(--pos-b)'   : n < 0 ? 'var(--neg-b)'   : 'var(--border)';

// ─── Equity Sparkline ─────────────────────────────────────────────────────────
const Spark = ({ data = [], w = 140, h = 44 }) => {
  const id = useRef(`sp-${Math.random().toString(36).slice(2,7)}`).current;
  if (!data || data.length < 2) return (
    <svg width={w} height={h}>
      <line x1={0} y1={h/2} x2={w} y2={h/2} stroke="var(--surface3)" strokeWidth={1} strokeDasharray="3 3"/>
    </svg>
  );
  const vals = data.map(d => d.balance);
  const mn = Math.min(...vals), mx = Math.max(...vals), rng = mx - mn || 1;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w;
    const y = h - 3 - ((v - mn) / rng) * (h - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = vals[vals.length - 1] >= vals[0];
  const rawC = up ? '#22c55e' : '#ef4444';
  return (
    <svg width={w} height={h} style={{ display:'block', overflow:'visible' }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={rawC} stopOpacity="0.2"/>
          <stop offset="100%" stopColor={rawC} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${id})`}/>
      <polyline points={pts} fill="none" stroke={up ? 'var(--pos)' : 'var(--neg)'}
        strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
};

// ─── Price Ladder ─────────────────────────────────────────────────────────────
const PriceLadder = ({ entry, stop, tp, current }) => {
  if (!entry || !current) return null;
  const isLong = tp > entry;
  const allPx  = [entry, stop, tp, current].filter(Boolean);
  const lo     = Math.min(...allPx) * 0.9995;
  const hi     = Math.max(...allPx) * 1.0005;
  const range  = hi - lo || 1;
  const pct    = v => ((v - lo) / range) * 100;
  const levels = [
    { label: 'TP',    price: tp,      color: 'var(--pos)',   pct: pct(tp) },
    { label: 'Entry', price: entry,   color: 'var(--ink2)',  pct: pct(entry) },
    { label: 'Stop',  price: stop,    color: 'var(--neg)',   pct: pct(stop) },
    { label: 'Now',   price: current, color: 'var(--amber)', pct: pct(current) },
  ].filter(l => l.price).sort((a, b) => b.pct - a.pct);
  const rr = tp && stop && entry
    ? Math.abs((tp - entry) / (entry - stop)).toFixed(2)
    : null;
  return (
    <div style={{ display:'flex', gap: 16, alignItems:'center' }}>
      <div style={{ position:'relative', width: 8, height: 90, flexShrink:0 }}>
        <div style={{ position:'absolute', left: 3, top: 0, bottom: 0, width: 2,
          background:'var(--surface3)', borderRadius: 2 }}/>
        {stop && tp && (
          <div style={{ position:'absolute', left: 3, width: 2, borderRadius: 2,
            background: isLong ? 'var(--pos-dim)' : 'var(--neg-dim)',
            top: `${100 - pct(isLong ? tp : stop)}%`,
            bottom: `${pct(isLong ? stop : tp)}%` }}/>
        )}
        {levels.map(l => (
          <div key={l.label} style={{ position:'absolute', left: 0, width: 8, height: 2,
            background: l.color, borderRadius: 1,
            top: `${100 - l.pct}%`, transform: 'translateY(-50%)',
            boxShadow: l.label === 'Now' ? `0 0 5px ${l.color}` : 'none' }}/>
        ))}
      </div>
      <div style={{ flex:1, position:'relative', height: 90 }}>
        {levels.map(l => (
          <div key={l.label} style={{ position:'absolute', width:'100%',
            top: `${100 - l.pct}%`, transform:'translateY(-50%)',
            display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontFamily:'var(--mono)', fontSize: 8,
              textTransform:'uppercase', letterSpacing:'0.09em',
              color: l.label === 'Now' ? l.color : 'var(--ink4)',
              fontWeight: l.label === 'Now' ? 700 : 400 }}>{l.label}</span>
            <span style={{ fontFamily:'var(--mono)', fontSize: 9, fontWeight: 600,
              color: l.color, letterSpacing:'-0.01em' }}>
              {l.price >= 1 ? `$${fmt(l.price, 2)}` : `$${l.price.toFixed(5)}`}
            </span>
          </div>
        ))}
      </div>
      {rr && (
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center',
          gap: 3, paddingLeft: 8, borderLeft:'1px solid var(--border)' }}>
          <span style={{ fontFamily:'var(--mono)', fontSize: 7, color:'var(--ink4)',
            textTransform:'uppercase', letterSpacing:'0.1em' }}>R:R</span>
          <span style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700,
            color: parseFloat(rr) >= 2 ? 'var(--pos)' : 'var(--amber)' }}>1:{rr}</span>
        </div>
      )}
    </div>
  );
};

// ─── Engine Mode Toggle ───────────────────────────────────────────────────────
const EnginePill = ({ engineMode, onChange, running }) => (
  <div style={{
    display:'flex', gap: 4,
    background:'var(--surface2)', border:'1px solid var(--border)',
    borderRadius:'var(--radius)', padding: 3,
    opacity: running ? 0.5 : 1,
    pointerEvents: running ? 'none' : 'auto',
    title: running ? 'Stop engine before switching' : '',
  }}>
    {Object.values(ENGINES).map(eng => {
      const active = engineMode === eng.id;
      return (
        <button key={eng.id} onClick={() => onChange(eng.id)} style={{
          background: active ? 'var(--surface4)' : 'transparent',
          border: active ? '1px solid var(--border2)' : '1px solid transparent',
          borderRadius: 'calc(var(--radius) - 3px)',
          padding:'5px 12px', cursor:'pointer',
          fontFamily:'var(--mono)', fontSize: 10, fontWeight: active ? 700 : 500,
          color: active ? 'var(--ink)' : 'var(--ink4)',
          letterSpacing:'0.05em', transition:'all .15s', whiteSpace:'nowrap',
        }}>
          {eng.emoji} {eng.name}
        </button>
      );
    })}
  </div>
);

// ─── Live dot ─────────────────────────────────────────────────────────────────
const LiveDot = ({ on }) => (
  <span style={{
    display:'inline-block', width: 6, height: 6, borderRadius:'50%', flexShrink: 0,
    background: on ? 'var(--pos)' : 'var(--surface4)',
    boxShadow: on ? '0 0 0 3px var(--pos-dim)' : 'none',
  }} className={on ? 'pulse' : ''}/>
);

const DirBadge = ({ d }) => (
  <span className={`badge ${d === 'LONG' ? 'badge-green' : 'badge-red'}`}>{d}</span>
);

const ExitBadge = ({ r }) => {
  const map = { TP:'badge-green', TAKE_PROFIT:'badge-green', SL:'badge-red', STOP:'badge-red',
    HARD_STOP:'badge-red', TIMEOUT:'badge-amber', MANUAL:'badge-muted',
    TRAIL:'badge-muted', TRAILING:'badge-muted',
    FLIP:'badge-amber', VAULT_HALT:'badge-red' };
  const labels = { TP:'TP', TAKE_PROFIT:'TP', SL:'SL', STOP:'Stop', HARD_STOP:'Hard Stop',
    TIMEOUT:'Timeout', MANUAL:'Manual', TRAIL:'Trail', TRAILING:'Trail',
    FLIP:'Flip', VAULT_HALT:'Vault' };
  return <span className={`badge ${map[r] || 'badge-muted'}`}>{labels[r] || r}</span>;
};

const Stat = ({ label, value, color }) => (
  <div>
    <div style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.1em',
      textTransform:'uppercase', color:'var(--ink4)', marginBottom: 5 }}>{label}</div>
    <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700,
      color: color || 'var(--ink)', fontVariantNumeric:'tabular-nums',
      letterSpacing:'-0.01em' }}>{value}</div>
  </div>
);

const CfgInput = ({ label, hint, value, step, min, max, onChange }) => (
  <div>
    <div style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.09em',
      textTransform:'uppercase', color:'var(--ink3)', marginBottom: 5 }}>{label}</div>
    <input type="number" value={value} step={step} min={min} max={max}
      onChange={e => onChange(Number(e.target.value))}
      style={{ width:'100%', background:'var(--surface2)',
        border:'1px solid var(--border)', borderRadius:'var(--radius-sm)',
        padding:'8px 10px', fontFamily:'var(--mono)', fontSize: 12,
        fontWeight: 500, color:'var(--ink)', outline:'none', transition:'border-color .15s' }}
      onFocus={e  => e.target.style.borderColor = 'var(--border3)'}
      onBlur={e   => e.target.style.borderColor = 'var(--border)'}
    />
    {hint && <div style={{ fontSize: 9, color:'var(--ink4)', marginTop: 3 }}>{hint}</div>}
  </div>
);

const Toggle = ({ on, onChange, label, hint }) => (
  <div style={{ display:'flex', alignItems:'flex-start', gap: 12 }}>
    <div onClick={onChange} style={{ width: 36, height: 20, borderRadius: 10, cursor:'pointer',
      position:'relative', flexShrink: 0, marginTop: 1,
      background: on ? 'var(--pos)' : 'var(--surface4)',
      border:`1px solid ${on ? 'var(--pos-b)' : 'var(--border2)'}`,
      transition:'background .2s, border-color .2s' }}>
      <div style={{ position:'absolute', top: 3, width: 12, height: 12,
        borderRadius: 6, background:'var(--ink)',
        left: on ? 19 : 3, transition:'left .2s', boxShadow:'0 1px 3px rgba(0,0,0,.25)' }}/>
    </div>
    <div>
      <div style={{ fontSize: 11, fontWeight: 500, color:'var(--ink2)', marginBottom: 2 }}>{label}</div>
      {hint && <div style={{ fontSize: 10, color:'var(--ink4)' }}>{hint}</div>}
    </div>
  </div>
);

const SecLabel = ({ children, right }) => (
  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 13 }}>
    <span style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.14em',
      textTransform:'uppercase', color:'var(--ink4)' }}>{children}</span>
    {right && <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--ink4)' }}>{right}</span>}
  </div>
);


// ═══════════════════════════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════
export default function HFTBot({ initialBalance = 1000 }) {
  const [engineMode, setEngineMode] = useState('predator');
  const [status,     setStatus]     = useState(null);
  const [running,    setRunning]    = useState(false);
  const [loading,    setLoading]    = useState(false);
  const [tab,        setTab]        = useState('positions');
  const [balance,    setBalance]    = useState(initialBalance);
  const [flash,      setFlash]      = useState(null);
  const [expandPos,  setExpandPos]  = useState(null);

  // Per-engine config state
  const [predCfg, setPredCfg] = useState(ENGINES.predator.defaultCfg);
  const [jackCfg, setJackCfg] = useState(ENGINES.jackal.defaultCfg);

  const eng  = ENGINES[engineMode];
  const cfg  = engineMode === 'predator' ? predCfg : jackCfg;
  const setCfg = engineMode === 'predator'
    ? fn => setPredCfg(c => typeof fn === 'function' ? fn(c) : fn)
    : fn => setJackCfg(c => typeof fn === 'function' ? fn(c) : fn);

  const wsRef     = useRef(null);
  const prevCount = useRef(0);
  const prevMode  = useRef(engineMode);

  // ─── Reset state when engine switches ─────────────────────────────────────
  useEffect(() => {
    if (prevMode.current !== engineMode) {
      prevMode.current = engineMode;
      setStatus(null);
      setRunning(false);
      setTab('positions');
      prevCount.current = 0;
      // Reconnect WS to new engine
      wsRef.current?.close();
    }
  }, [engineMode]);

  // ─── WebSocket ─────────────────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const ws = new WebSocket(`${WS_URL}${eng.wsPath}`);
    ws.onclose   = () => setTimeout(connectWS, 3000);
    ws.onerror   = () => ws.close();
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setStatus(data); setRunning(data.running);
        const count = data.trade_log?.length || 0;
        if (count > prevCount.current && prevCount.current > 0) {
          const last = data.trade_log[count - 1];
          if (last) {
            setFlash({ msg:`${last.coin} closed  ${fmtUSD(last.net_pnl)}`, pos: last.net_pnl >= 0 });
            setTimeout(() => setFlash(null), 3000);
          }
        }
        prevCount.current = count;
      } catch {}
    };
    wsRef.current = ws;
  }, [eng.wsPath]);

  useEffect(() => {
    wsRef.current?.close();
    connectWS();
    return () => wsRef.current?.close();
  }, [connectWS]);

  // Fallback polling
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}${eng.apiBase}/status`);
        setStatus(data); setRunning(data.running);
      } catch {}
    }, 2000);
    return () => clearInterval(id);
  }, [eng.apiBase]);

  // ─── Controls ─────────────────────────────────────────────────────────────
  const showFlash = (msg, pos = true) => {
    setFlash({ msg, pos });
    setTimeout(() => setFlash(null), 2500);
  };

  const startBot = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}${eng.apiBase}/config`, cfg);
      await axios.post(`${API}${eng.apiBase}/start`, { balance });
      setRunning(true);
    } catch (e) { alert('Start failed: ' + (e?.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const stopBot = async () => {
    setLoading(true);
    try { await axios.post(`${API}${eng.apiBase}/stop`); setRunning(false); } catch {}
    setLoading(false);
  };

  const resetBot = async () => {
    if (!confirm('Reset all trades and balance?')) return;
    await axios.post(`${API}${eng.apiBase}/reset`, { balance });
    setRunning(false); setStatus(null);
  };

  const closeAll  = async () => axios.post(`${API}${eng.apiBase}/close-all`);
  const closeOne  = async (id) => axios.post(`${API}${eng.apiBase}/close/${id}`);
  const resetCB   = async () => axios.post(`${API}${eng.apiBase}/${engineMode === 'jackal' ? 'vault-resume' : 'reset-cb'}`);

  // Jackal-only: vault resume
  const vaultResume = async () => {
    await axios.post(`${API}${eng.apiBase}/vault-resume`);
    showFlash('Vault resumed', true);
  };

  const applyConfig = async () => {
    await axios.post(`${API}${eng.apiBase}/config`, cfg);
    showFlash('Config applied ✓', true);
  };

  // ─── Data extraction ───────────────────────────────────────────────────────
  const st      = status?.stats || {};
  const equity  = status?.total_equity   ?? balance;
  const pnl     = status?.total_pnl      ?? 0;
  const pnlPct  = status?.total_pnl_pct  ?? 0;
  const cb      = status?.circuit_breaker;
  const openPos = status?.open_positions || [];
  const logs    = status?.trade_log      || [];
  const events  = status?.events         || [];

  // Predator-specific
  const ms      = status?.microstructure || [];
  // Jackal-specific
  const vault   = status?.vault          || null;
  const burst   = status?.burst_snapshot || [];
  const lossPause = status?.loss_pause_active;
  const jackalCB  = vault?.is_halted;

  const TABS = [
    { id:'positions', label:'Positions',                         count: openPos.length },
    { id:'finder',    label: engineMode === 'predator' ? 'Position Finder' : 'Burst Scanner', count: null },
    { id:'log',       label:'History',                           count: logs.length },
    { id:'stats',     label:'Stats',                             count: null },
    ...(engineMode === 'jackal' ? [{ id:'vault', label:'Vault', count: null }] : []),
    { id:'config',    label:'Config',                            count: null },
  ];

  return (
    <div style={{ display:'flex', flexDirection:'column', gap: 10 }}>

      {/* ── Flash toast ───────────────────────────────────────────────────── */}
      {flash && (
        <div className="fade-up" style={{
          position:'fixed', bottom: 28, left:'50%', transform:'translateX(-50%)',
          background:'var(--surface)', border:`1px solid ${flash.pos ? 'var(--pos-b)' : 'var(--neg-b)'}`,
          borderRadius:'var(--radius)', padding:'10px 24px', zIndex: 9999,
          fontFamily:'var(--mono)', fontSize: 11, fontWeight: 600,
          color: flash.pos ? 'var(--pos)' : 'var(--neg)',
          boxShadow:'var(--shadow-lg)', pointerEvents:'none', whiteSpace:'nowrap',
        }}>{flash.msg}</div>
      )}

      {/* ── Circuit breaker / Vault halt banner ───────────────────────────── */}
      {(cb?.tripped || jackalCB) && (
        <div className="card fade-up" style={{
          padding:'12px 16px', display:'flex', alignItems:'center', gap: 12,
          background:'var(--neg-dim)', borderColor:'var(--neg-b)',
        }}>
          <span>⛔</span>
          <div style={{ flex:1 }}>
            <div style={{ fontFamily:'var(--mono)', fontSize: 10, fontWeight: 700,
              color:'var(--neg)', marginBottom: 2 }}>
              {jackalCB ? 'Vault Halt Active' : 'Circuit Breaker Active'}
            </div>
            <div style={{ fontSize: 11, color:'var(--ink3)' }}>
              {jackalCB ? (vault?.halt_reason || 'Equity floor protection') : cb?.reason}
            </div>
          </div>
          {jackalCB
            ? <button className="tab-btn" onClick={vaultResume} style={{ fontSize: 10 }}>Resume Vault</button>
            : <button className="tab-btn" onClick={resetCB} style={{ fontSize: 10 }}>Reset CB</button>
          }
        </div>
      )}

      {/* ── Loss pause banner (Jackal-only) ───────────────────────────────── */}
      {engineMode === 'jackal' && lossPause && (
        <div className="card fade-up" style={{
          padding:'10px 16px', display:'flex', alignItems:'center', gap: 10,
          background:'var(--amber-dim, rgba(245,158,11,.08))', borderColor:'var(--amber)',
        }}>
          <span>⏸</span>
          <div style={{ fontSize: 11, color:'var(--ink3)', flex:1 }}>
            Loss pause active — Jackal pausing after streak. Auto-resumes in ~60s.
          </div>
          <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--amber)' }}>PAUSED</span>
        </div>
      )}

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="card" style={{ padding:'16px 20px' }}>
        <div style={{ display:'flex', alignItems:'center', gap: 14 }}>

          {/* Engine toggle + identity */}
          <div style={{ display:'flex', flexDirection:'column', gap: 8, flex: 1, minWidth: 0 }}>
            <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
              <LiveDot on={running}/>
              <div>
                <div style={{ fontFamily:'var(--mono)', fontSize: 12, fontWeight: 700,
                  letterSpacing:'0.08em', color:'var(--ink)', lineHeight: 1.1 }}>
                  {eng.emoji} {eng.name} HFT
                </div>
                <div style={{ fontSize: 10, color:'var(--ink4)', marginTop: 2 }}>
                  {running ? eng.subtitle : 'Idle — ready to deploy'}
                </div>
              </div>
              {running
                ? <span className="badge badge-green" style={{ marginLeft: 4 }}>Live</span>
                : <span className="badge badge-muted" style={{ marginLeft: 4 }}>{eng.badge}</span>
              }
            </div>
            <EnginePill engineMode={engineMode} onChange={setEngineMode} running={running}/>
          </div>

          {/* Equity */}
          <div style={{ textAlign:'right' }}>
            <div style={{ fontFamily:'var(--mono)', fontSize: 22, fontWeight: 800,
              letterSpacing:'-0.03em', color:'var(--ink)', fontVariantNumeric:'tabular-nums', lineHeight: 1 }}>
              ${fmt(equity)}
            </div>
            <div style={{ fontFamily:'var(--mono)', fontSize: 10, fontWeight: 600,
              color: clr(pnl), marginTop: 3 }}>
              {fmtUSD(pnl)}&ensp;({fmtPct(pnlPct)})
            </div>
          </div>

          {/* Controls */}
          <div style={{ display:'flex', gap: 6, alignItems:'center', flexShrink: 0 }}>
            {!running ? (
              <button onClick={startBot} disabled={loading} style={{
                background:'var(--pos)', border:'none', borderRadius:'var(--radius-sm)',
                padding:'8px 18px', fontFamily:'var(--mono)', fontSize: 10,
                fontWeight: 700, color:'#fff', cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.5 : 1, letterSpacing:'0.06em',
              }}>{loading ? '…' : '▶ Start'}</button>
            ) : (
              <>
                <button onClick={closeAll} style={{
                  background:'transparent', border:'1px solid var(--border2)',
                  borderRadius:'var(--radius-sm)', padding:'7px 14px',
                  fontFamily:'var(--mono)', fontSize: 10, fontWeight: 600,
                  color:'var(--amber)', cursor:'pointer', letterSpacing:'0.06em',
                }}>Close All</button>
                <button onClick={stopBot} disabled={loading} style={{
                  background:'var(--neg)', border:'none', borderRadius:'var(--radius-sm)',
                  padding:'8px 18px', fontFamily:'var(--mono)', fontSize: 10,
                  fontWeight: 700, color:'#fff', cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.5 : 1, letterSpacing:'0.06em',
                }}>{loading ? '…' : '■ Stop'}</button>
              </>
            )}
            <button onClick={resetBot} title="Reset session" style={{
              background:'transparent', border:'1px solid var(--border)',
              borderRadius:'var(--radius-sm)', width: 32, height: 32,
              display:'flex', alignItems:'center', justifyContent:'center',
              color:'var(--ink4)', cursor:'pointer', fontSize: 14,
              transition:'border-color .15s, color .15s',
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor='var(--border3)'; e.currentTarget.style.color='var(--ink2)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor='var(--border)';  e.currentTarget.style.color='var(--ink4)'; }}
            >↺</button>
          </div>
        </div>

        {/* Position slots bar */}
        {running && (
          <div style={{ marginTop: 14, display:'flex', alignItems:'center', gap: 10 }}>
            <span style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--ink4)',
              letterSpacing:'0.1em', textTransform:'uppercase', flexShrink: 0 }}>Slots</span>
            <div style={{ display:'flex', gap: 4, flex: 1 }}>
              {Array.from({ length: status?.max_positions || cfg.max_positions }).map((_, i) => {
                const used = i < (status?.open_count || 0);
                return <div key={i} style={{ flex: 1, height: 4, borderRadius: 2,
                  background: used ? 'var(--ink2)' : 'var(--surface3)',
                  transition:'background .3s' }}/>;
              })}
            </div>
            <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--ink3)', flexShrink: 0 }}>
              {status?.open_count || 0} / {status?.max_positions || cfg.max_positions}
            </span>
          </div>
        )}

        {/* Engine comparison hint (when not running) */}
        {!running && (
          <div style={{ marginTop: 14, padding:'9px 12px',
            background:'var(--surface2)', border:'1px solid var(--border)',
            borderRadius:'var(--radius-sm)', display:'flex', gap: 20 }}>
            <div style={{ fontSize: 10, color:'var(--ink3)', lineHeight: 1.6 }}>
              <strong style={{ color: engineMode === 'predator' ? 'var(--ink)' : 'var(--ink4)' }}>🕷 Predator</strong>
              {' '}— waits for 1.5–3σ VWAP extreme, 3-gate confirmation, R:R ≥ 2.5, holds up to 60s.
            </div>
            <div style={{ width: 1, background:'var(--border)', flexShrink: 0 }}/>
            <div style={{ fontSize: 10, color:'var(--ink3)', lineHeight: 1.6 }}>
              <strong style={{ color: engineMode === 'jackal' ? 'var(--amber)' : 'var(--ink4)' }}>🐺 Jackal</strong>
              {' '}— enters on 3 consecutive momentum ticks, fixed TP/SL, holds 3–12s. High frequency.
            </div>
          </div>
        )}
      </div>

      {/* ── Stats strip ──────────────────────────────────────────────────────── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap: 8 }}>
        {[
          { label:'Trades',    value: st.total_trades ?? 0,                  color: null },
          { label:'Win Rate',  value:`${fmt(st.win_rate ?? 0, 1)}%`,          color: clr((st.win_rate ?? 0) - 50) },
          { label:'P.Factor',  value: fmt(st.profit_factor ?? 0, 2),          color: clr((st.profit_factor ?? 0) - 1) },
          { label:'Avg PnL',   value: fmtUSD(st.avg_net_pnl ?? 0),            color: clr(st.avg_net_pnl ?? 0) },
          { label:'/Hour',     value: fmt((st.trades_per_hour ?? (st.trades_per_minute ?? 0) * 60), 1), color: null },
          { label:'Max DD',    value:`${fmt(st.max_drawdown_pct ?? 0, 2)}%`,  color:(st.max_drawdown_pct??0)>5?'var(--neg)':'var(--amber)' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card" style={{ padding:'12px 14px' }}>
            <div style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.1em',
              textTransform:'uppercase', color:'var(--ink4)', marginBottom: 6 }}>{label}</div>
            <div style={{ fontFamily:'var(--mono)', fontSize: 15, fontWeight: 700,
              color: color || 'var(--ink3)', fontVariantNumeric:'tabular-nums' }}>{value}</div>
          </div>
        ))}
      </div>

      {/* ── Tabbed panel ──────────────────────────────────────────────────────── */}
      <div className="card">
        {/* Tab bar */}
        <div style={{ display:'flex', borderBottom:'1px solid var(--border)', padding:'0 6px', overflowX:'auto' }}>
          {TABS.map(({ id, label, count }) => (
            <button key={id}
              className={`tab-btn${tab===id?' active':''}`}
              onClick={() => setTab(id)}
              style={{ borderRadius:0, borderBottom: tab===id ? '2px solid var(--ink)' : '2px solid transparent',
                margin:'0 1px', whiteSpace:'nowrap' }}>
              {label}
              {count != null && count > 0 && (
                <span className={`badge ${tab===id ? 'badge-accent' : 'badge-muted'}`}
                  style={{ marginLeft: 6, fontSize: 8 }}>{count}</span>
              )}
            </button>
          ))}
        </div>

        {/* ════ TAB: OPEN POSITIONS ═══════════════════════════════════════════ */}
        {tab === 'positions' && (
          <div style={{ padding:'16px 20px' }}>
            {openPos.length === 0 ? (
              <div style={{ padding:'44px 0', textAlign:'center',
                display:'flex', flexDirection:'column', alignItems:'center', gap: 10 }}>
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                  stroke="var(--ink5)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <p style={{ fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                  {running
                    ? engineMode === 'predator'
                      ? 'Scanning for mean-reversion setups…'
                      : 'Watching for burst momentum entries…'
                    : 'Start the engine to begin'
                  }
                </p>
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap: 8 }}>
                {openPos.map(pos => {
                  const expanded = expandPos === pos.id;
                  return (
                    <div key={pos.id} className="card fade-up"
                      style={{ background: clrDim(pos.unrealized_pnl), borderColor: clrB(pos.unrealized_pnl), overflow:'hidden' }}>
                      <div style={{ height: 2, background:'var(--border)' }}>
                        <div style={{ height:'100%', background: clr(pos.unrealized_pnl),
                          width:`${Math.min(100, Math.abs(pos.unrealized_pct ?? 0) * 8)}%`,
                          transition:'width .5s ease' }}/>
                      </div>
                      <div style={{ padding:'12px 16px', display:'flex', alignItems:'center', gap: 12 }}>
                        <div style={{ minWidth: 80 }}>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 13, fontWeight: 800,
                            color:'var(--ink)', letterSpacing:'-0.01em', marginBottom: 5 }}>{pos.coin}</div>
                          <div style={{ display:'flex', alignItems:'center', gap: 5 }}>
                            <DirBadge d={pos.direction}/>
                            <span style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--ink4)' }}>
                              {fmtS(pos.hold_seconds || 0)}
                            </span>
                          </div>
                        </div>
                        <div style={{ flex:1, display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 10 }}>
                          <Stat label="Entry"   value={`$${fmt(pos.entry_price, 4)}`}/>
                          <Stat label="Current" value={`$${fmt(pos.current_price, 4)}`}/>
                          <Stat label={engineMode === 'predator' ? 'Stop' : 'SL'}
                            value={`$${fmt(pos.stop_price, 4)}`} color="var(--neg)"/>
                        </div>
                        <div style={{ textAlign:'right', minWidth: 90 }}>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 16, fontWeight: 800,
                            color: clr(pos.unrealized_pnl), lineHeight: 1, fontVariantNumeric:'tabular-nums' }}>
                            {fmtUSD(pos.unrealized_pnl)}
                          </div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 10, fontWeight: 600,
                            color: clr(pos.unrealized_pnl), marginTop: 3 }}>
                            {fmtPct(pos.unrealized_pct ?? 0)}
                          </div>
                        </div>
                        <div style={{ display:'flex', gap: 5, flexShrink: 0 }}>
                          {engineMode === 'predator' && (
                            <button onClick={() => setExpandPos(expanded ? null : pos.id)} style={{
                              background:'transparent', border:'1px solid var(--border)',
                              borderRadius:'var(--radius-sm)', width: 26, height: 26,
                              display:'flex', alignItems:'center', justifyContent:'center',
                              color: expanded ? 'var(--ink2)' : 'var(--ink4)', cursor:'pointer', fontSize: 10,
                              borderColor: expanded ? 'var(--border3)' : 'var(--border)',
                              transition:'all .15s' }}>⌗</button>
                          )}
                          <button onClick={() => closeOne(pos.id)} style={{
                            background:'transparent', border:'1px solid var(--border)',
                            borderRadius:'var(--radius-sm)', width: 26, height: 26,
                            display:'flex', alignItems:'center', justifyContent:'center',
                            color:'var(--ink4)', cursor:'pointer', fontSize: 11, transition:'all .15s' }}
                            onMouseEnter={e => { e.currentTarget.style.borderColor='var(--neg-b)'; e.currentTarget.style.color='var(--neg)'; }}
                            onMouseLeave={e => { e.currentTarget.style.borderColor='var(--border)'; e.currentTarget.style.color='var(--ink4)'; }}
                          >✕</button>
                        </div>
                      </div>

                      {/* Predator expanded view */}
                      {engineMode === 'predator' && expanded && (
                        <div style={{ padding:'0 16px 14px', borderTop:'1px solid var(--border)',
                          paddingTop: 13, display:'grid', gridTemplateColumns:'1fr 1fr', gap: 16 }}>
                          <div>
                            <SecLabel>Price Ladder</SecLabel>
                            <PriceLadder entry={pos.entry_price} stop={pos.stop_price}
                              tp={pos.take_profit} current={pos.current_price}/>
                          </div>
                          <div>
                            <SecLabel>Position Details</SecLabel>
                            <div className="data-row"><span className="data-label">Capital</span>
                              <span className="data-value num">${fmt(pos.capital || 0)}</span></div>
                            <div className="data-row"><span className="data-label">Z-Score at entry</span>
                              <span className="data-value num" style={{ color:'var(--amber)' }}>
                                {pos.entry_zscore ? `${pos.entry_zscore.toFixed(2)}σ` : '—'}</span></div>
                            <div className="data-row"><span className="data-label">OFI at entry</span>
                              <span className="data-value num">
                                {pos.entry_ofi ? `${(pos.entry_ofi * 100).toFixed(1)}%` : '—'}</span></div>
                            <div className="data-row"><span className="data-label">Expected PnL</span>
                              <span className="data-value num" style={{ color:'var(--pos)' }}>
                                {pos.expected_pnl ? fmtUSD(pos.expected_pnl) : '—'}</span></div>
                            <div className="data-row" style={{ borderBottom:'none' }}>
                              <span className="data-label">Fee est.</span>
                              <span className="data-value num" style={{ color:'var(--ink3)' }}>
                                {pos.fee_estimate ? `−$${fmt(pos.fee_estimate, 3)}` : '—'}</span></div>
                          </div>
                        </div>
                      )}

                      {/* Jackal expanded: TP info */}
                      {engineMode === 'jackal' && (
                        <div style={{ padding:'8px 16px 12px', borderTop:'1px solid var(--border)',
                          display:'flex', gap: 20 }}>
                          <div className="data-row" style={{ borderBottom:'none', flex:1 }}>
                            <span className="data-label">TP Target</span>
                            <span className="data-value num" style={{ color:'var(--pos)' }}>
                              ${fmt(pos.tp_price || pos.take_profit, 4)}</span></div>
                          <div className="data-row" style={{ borderBottom:'none', flex:1 }}>
                            <span className="data-label">Capital</span>
                            <span className="data-value num">${fmt(pos.capital || 0)}</span></div>
                          <div className="data-row" style={{ borderBottom:'none', flex:1 }}>
                            <span className="data-label">Peak PnL</span>
                            <span className="data-value num" style={{ color:'var(--pos)' }}>
                              {fmtUSD(pos.peak_pnl || 0)}</span></div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: POSITION FINDER (Predator) / BURST SCANNER (Jackal) ════ */}
        {tab === 'finder' && engineMode === 'predator' && (
          <div style={{ padding:'16px 20px' }}>
            <SecLabel right="Real-time setup quality per coin">Position Finder</SecLabel>
            <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
              borderRadius:'var(--radius-sm)', padding:'10px 14px', marginBottom: 14,
              display:'flex', gap: 10, alignItems:'flex-start' }}>
              <span style={{ fontSize: 14, flexShrink: 0 }}>💡</span>
              <p style={{ fontSize: 10, color:'var(--ink3)', lineHeight: 1.6 }}>
                Shows where each coin sits relative to its mean-reversion entry zone.
                Green border = VWAP z-score threshold reached with OFI alignment.
              </p>
            </div>
            {ms.length === 0 ? (
              <div style={{ padding:'36px 0', textAlign:'center',
                fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                {running ? 'Warming up — need at least 20 ticks…' : 'Start the engine to see live data'}
              </div>
            ) : (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10 }}>
                {ms.map(m => {
                  const isLong = m.signal_long, isShort = m.signal_short;
                  const hasSig = isLong || isShort;
                  const inPos  = m.in_position;
                  const zAbs   = Math.abs(m.zscore ?? 0);
                  const zColor = isLong ? 'var(--pos)' : isShort ? 'var(--neg)' : 'var(--ink3)';
                  const ofiPct = ((m.ofi ?? 0.5) * 100).toFixed(0);
                  const ofiColor = m.ofi > 0.6 ? 'var(--pos)' : m.ofi < 0.4 ? 'var(--neg)' : 'var(--ink3)';
                  const zMax   = (predCfg.zscore_entry || 1.8) * 1.6;
                  const quality = Math.min(100, Math.round((zAbs / zMax) * 50 + (hasSig ? 30 : 0) + (m.spread_ok ? 20 : 0)));
                  const qualityColor = quality >= 70 ? 'var(--pos)' : quality >= 40 ? 'var(--amber)' : 'var(--ink4)';
                  return (
                    <div key={m.coin} className="card" style={{ padding:'14px 16px',
                      background: hasSig && !inPos ? clrDim(isLong ? 1 : -1) : 'var(--surface)',
                      borderColor: hasSig && !inPos ? clrB(isLong ? 1 : -1) : 'var(--border)',
                      transition:'all .3s' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 12 }}>
                        <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 13, fontWeight: 800, color:'var(--ink)' }}>{m.coin}</span>
                          {inPos ? <span className="badge badge-accent">In Position</span>
                            : isLong ? <span className="badge badge-green">↑ Long Setup</span>
                            : isShort ? <span className="badge badge-red">↓ Short Setup</span>
                            : !m.ticks_ready ? <span className="badge badge-muted">Warming</span>
                            : <span className="badge badge-muted">Watching</span>}
                        </div>
                        <div style={{ textAlign:'right' }}>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--ink4)',
                            textTransform:'uppercase', letterSpacing:'0.08em', marginBottom: 2 }}>Quality</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700, color: qualityColor }}>{quality}</div>
                        </div>
                      </div>
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>Z-Score</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700, color: zColor, fontVariantNumeric:'tabular-nums' }}>
                            {(m.zscore ?? 0) >= 0 ? '+' : ''}{(m.zscore ?? 0).toFixed(2)}σ</div>
                        </div>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>OFI (bid)</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700, color: ofiColor, fontVariantNumeric:'tabular-nums' }}>{ofiPct}%</div>
                        </div>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>Price</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 11, fontWeight: 600, color:'var(--ink2)', fontVariantNumeric:'tabular-nums' }}>
                            {m.price >= 1 ? `$${fmt(m.price)}` : `$${m.price?.toFixed(5) ?? '—'}`}</div>
                        </div>
                      </div>
                      <div style={{ marginBottom: 10 }}>
                        <div style={{ display:'flex', justifyContent:'space-between', marginBottom: 4 }}>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 7, color:'var(--ink4)',
                            textTransform:'uppercase', letterSpacing:'0.08em' }}>Z-Score pressure</span>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 7, color:'var(--ink4)' }}>
                            threshold {predCfg.zscore_entry}σ</span>
                        </div>
                        <div className="prog-bar" style={{ height: 5 }}>
                          <div className="prog-fill" style={{ height: 5, background: zColor,
                            width:`${Math.min(100, (zAbs / zMax) * 100)}%` }}/>
                        </div>
                      </div>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--ink4)' }}>Spread</span>
                        {m.spread_ok
                          ? <span className="badge badge-muted" style={{ fontSize: 8 }}>Normal ✓</span>
                          : <span className="badge badge-amber" style={{ fontSize: 8 }}>Wide ⚠</span>}
                      </div>
                      {inPos && m.position && (
                        <div style={{ marginTop: 12, paddingTop: 12, borderTop:'1px solid var(--border)' }}>
                          <SecLabel>Live Position Ladder</SecLabel>
                          <PriceLadder entry={m.position.entry_price} stop={m.position.stop_price}
                            tp={m.position.take_profit} current={m.price}/>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ════ Jackal: BURST SCANNER ═════════════════════════════════════════ */}
        {tab === 'finder' && engineMode === 'jackal' && (
          <div style={{ padding:'16px 20px' }}>
            <SecLabel right={`Min streak: ${jackCfg.min_streak} ticks · Move ≥ ${jackCfg.min_move_pct}%`}>
              Burst Scanner
            </SecLabel>
            <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
              borderRadius:'var(--radius-sm)', padding:'10px 14px', marginBottom: 14,
              display:'flex', gap: 10, alignItems:'flex-start' }}>
              <span style={{ fontSize: 14, flexShrink: 0 }}>⚡</span>
              <p style={{ fontSize: 10, color:'var(--ink3)', lineHeight: 1.6 }}>
                Detects consecutive tick momentum. Entry fires on {jackCfg.min_streak}+ ticks in one direction
                with minimum {jackCfg.min_move_pct}% total move. OFI gate prevents extreme opposing flow.
              </p>
            </div>
            {burst.length === 0 ? (
              <div style={{ padding:'36px 0', textAlign:'center',
                fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                {running ? 'Collecting burst ticks…' : 'Start Jackal to see live burst data'}
              </div>
            ) : (
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 10 }}>
                {burst.map(b => {
                  const up     = b.up_streak >= jackCfg.min_streak;
                  const dn     = b.down_streak >= jackCfg.min_streak;
                  const hasSig = up || dn;
                  const inPos  = b.in_position;
                  const streakColor = up ? 'var(--pos)' : dn ? 'var(--neg)' : 'var(--ink3)';
                  const ofiColor = b.ofi > 0.6 ? 'var(--pos)' : b.ofi < 0.4 ? 'var(--neg)' : 'var(--ink3)';
                  return (
                    <div key={b.coin} className="card" style={{ padding:'14px 16px',
                      background: hasSig && !inPos ? clrDim(up ? 1 : -1) : 'var(--surface)',
                      borderColor: hasSig && !inPos ? clrB(up ? 1 : -1) : 'var(--border)',
                      transition:'all .3s' }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 12 }}>
                        <div style={{ display:'flex', alignItems:'center', gap: 8 }}>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 13, fontWeight: 800, color:'var(--ink)' }}>{b.coin}</span>
                          {inPos ? <span className="badge badge-accent">In Position</span>
                            : up ? <span className="badge badge-green">↑ Burst Long</span>
                            : dn ? <span className="badge badge-red">↓ Burst Short</span>
                            : <span className="badge badge-muted">Watching</span>}
                        </div>
                        <div style={{ textAlign:'right' }}>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--ink4)',
                            textTransform:'uppercase', letterSpacing:'0.08em', marginBottom: 2 }}>Price</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 11, fontWeight: 600, color:'var(--ink2)' }}>
                            {b.price >= 1 ? `$${fmt(b.price)}` : `$${b.price?.toFixed(5) ?? '—'}`}</div>
                        </div>
                      </div>
                      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>↑ Streak</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 18, fontWeight: 800,
                            color: up ? 'var(--pos)' : 'var(--ink4)', fontVariantNumeric:'tabular-nums' }}>
                            {b.up_streak ?? 0}</div>
                        </div>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>↓ Streak</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 18, fontWeight: 800,
                            color: dn ? 'var(--neg)' : 'var(--ink4)', fontVariantNumeric:'tabular-nums' }}>
                            {b.down_streak ?? 0}</div>
                        </div>
                        <div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 7, letterSpacing:'0.1em',
                            textTransform:'uppercase', color:'var(--ink4)', marginBottom: 4 }}>OFI</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700, color: ofiColor, fontVariantNumeric:'tabular-nums' }}>
                            {((b.ofi ?? 0.5) * 100).toFixed(0)}%</div>
                        </div>
                      </div>
                      {/* Streak bar */}
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ display:'flex', gap: 3 }}>
                          {Array.from({ length: Math.max(jackCfg.min_streak + 2, 5) }).map((_, i) => (
                            <div key={i} style={{ flex: 1, height: 5, borderRadius: 2,
                              background: i < (b.up_streak || 0) ? 'var(--pos)'
                                : i < (b.down_streak || 0) ? 'var(--neg)' : 'var(--surface3)',
                              transition:'background .2s' }}/>
                          ))}
                        </div>
                        <div style={{ display:'flex', justifyContent:'space-between', marginTop: 3 }}>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 7, color:'var(--ink4)' }}>streak</span>
                          <span style={{ fontFamily:'var(--mono)', fontSize: 7, color:'var(--ink4)' }}>
                            need {jackCfg.min_streak}</span>
                        </div>
                      </div>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                        <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--ink4)' }}>Spread</span>
                        {(b.spread_pct ?? 0) < (jackCfg.max_spread_pct ?? 0.08)
                          ? <span className="badge badge-muted" style={{ fontSize: 8 }}>OK ✓</span>
                          : <span className="badge badge-amber" style={{ fontSize: 8 }}>Wide ⚠</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: HISTORY ══════════════════════════════════════════════════ */}
        {tab === 'log' && (
          <div>
            {logs.length === 0 ? (
              <div style={{ padding:'44px 0', textAlign:'center',
                fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                No completed trades yet
              </div>
            ) : (
              <div style={{ overflowX:'auto', maxHeight: 480, overflowY:'auto' }}>
                <table className="aq-table">
                  <thead>
                    <tr>
                      {['Time','Coin','Dir','Entry','Exit','Hold','Reason','Net PnL'].map(h => (
                        <th key={h} style={{ textAlign: h === 'Net PnL' ? 'right' : 'left' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {[...logs].reverse().map(t => (
                      <tr key={t.id}>
                        <td style={{ fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                          {new Date(t.closed_at * 1000).toLocaleTimeString('en-US', { hour12:false })}
                        </td>
                        <td style={{ fontFamily:'var(--mono)', fontSize: 12, fontWeight: 700, color:'var(--ink)' }}>{t.coin}</td>
                        <td><DirBadge d={t.direction}/></td>
                        <td style={{ fontFamily:'var(--mono)', fontSize: 11, color:'var(--ink3)', fontVariantNumeric:'tabular-nums' }}>
                          ${fmt(t.entry_price, 4)}</td>
                        <td style={{ fontFamily:'var(--mono)', fontSize: 11, color:'var(--ink3)', fontVariantNumeric:'tabular-nums' }}>
                          ${fmt(t.exit_price, 4)}</td>
                        <td style={{ fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                          {fmtS(Math.round(t.hold_seconds ?? 0))}</td>
                        <td><ExitBadge r={t.exit_reason}/></td>
                        <td style={{ textAlign:'right' }}>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 13, fontWeight: 700,
                            color: clr(t.net_pnl), fontVariantNumeric:'tabular-nums' }}>{fmtUSD(t.net_pnl)}</div>
                          <div style={{ fontFamily:'var(--mono)', fontSize: 9, color: clr(t.net_pnl), marginTop: 1 }}>
                            {fmtPct(t.net_pct ?? 0)}</div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: STATS ════════════════════════════════════════════════════ */}
        {tab === 'stats' && (
          <div style={{ padding:'16px 20px', display:'flex', gap: 18 }}>
            <div style={{ flex:1, display:'grid', gridTemplateColumns:'1fr 1fr', gap: 8 }}>
              {[
                { label:'Total Trades',  value: st.total_trades ?? 0 },
                { label:'Win Rate',      value:`${fmt(st.win_rate ?? 0, 1)}%`,          color: clr((st.win_rate??0)-50) },
                { label:'Profit Factor', value: fmt(st.profit_factor ?? 0, 2),           color: clr((st.profit_factor??0)-1) },
                { label:'Sharpe',        value: fmt(st.sharpe_trades ?? 0, 3),            color: clr(st.sharpe_trades??0) },
                { label:'Total Net PnL', value: fmtUSD(st.total_net_pnl ?? st.net_pnl ?? 0),  color: clr(st.total_net_pnl ?? st.net_pnl ?? 0) },
                { label:'Total Fees',    value:`−$${fmt(Math.abs(st.total_fees??0), 2)}`, color:'var(--amber)' },
                { label:'Best Trade',    value: fmtPct(st.best_trade_pct ?? 0),           color:'var(--pos)' },
                { label:'Worst Trade',   value: fmtPct(st.worst_trade_pct ?? 0),          color:'var(--neg)' },
                { label:'Max Drawdown',  value:`${fmt(st.max_drawdown_pct??0, 2)}%`,       color:'var(--amber)' },
                { label:'Loss Streak',   value: st.max_loss_streak ?? 0,
                  color:(st.max_loss_streak??0)>=3 ? 'var(--neg)' : 'var(--ink3)' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                  borderRadius:'var(--radius-sm)', padding:'11px 13px' }}>
                  <div style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.1em',
                    textTransform:'uppercase', color:'var(--ink4)', marginBottom: 6 }}>{label}</div>
                  <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700,
                    color: color || 'var(--ink3)', fontVariantNumeric:'tabular-nums' }}>{value}</div>
                </div>
              ))}
            </div>
            <div style={{ width: 186, display:'flex', flexDirection:'column', gap: 8 }}>
              <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                borderRadius:'var(--radius-sm)', padding:'12px 14px' }}>
                <SecLabel>Equity Curve</SecLabel>
                <Spark data={status?.equity_curve || []} w={158} h={54}/>
              </div>
              <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                borderRadius:'var(--radius-sm)', padding:'12px 14px' }}>
                <div className="data-row">
                  <span className="data-label">Balance</span>
                  <span className="data-value num">${fmt(status?.balance ?? balance)}</span>
                </div>
                <div className="data-row" style={{ borderBottom:'none' }}>
                  <span className="data-label">Unrealized</span>
                  <span className="data-value num" style={{ color: clr(status?.unrealized_pnl ?? 0) }}>
                    {fmtUSD(status?.unrealized_pnl ?? 0)}</span>
                </div>
              </div>
              {/* Jackal: latency */}
              {engineMode === 'jackal' && status?.latency_ms != null && (
                <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                  borderRadius:'var(--radius-sm)', padding:'12px 14px' }}>
                  <div className="data-row" style={{ borderBottom:'none' }}>
                    <span className="data-label">Avg Latency</span>
                    <span className="data-value num" style={{
                      color: status.latency_ms < 150 ? 'var(--pos)' : status.latency_ms < 300 ? 'var(--amber)' : 'var(--neg)' }}>
                      {fmt(status.latency_ms, 1)}ms</span>
                  </div>
                </div>
              )}
              {st.exit_breakdown && Object.values(st.exit_breakdown).some(v => v > 0) && (
                <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                  borderRadius:'var(--radius-sm)', padding:'12px 14px' }}>
                  <SecLabel>Exit Breakdown</SecLabel>
                  {Object.entries(st.exit_breakdown).filter(([,v]) => v > 0).map(([k, v]) => (
                    <div key={k} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 6 }}>
                      <ExitBadge r={k}/>
                      <span style={{ fontFamily:'var(--mono)', fontSize: 11, fontWeight: 600, color:'var(--ink3)' }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════ TAB: VAULT (Jackal only) ══════════════════════════════════════ */}
        {tab === 'vault' && engineMode === 'jackal' && (
          <div style={{ padding:'16px 20px' }}>
            <SecLabel right="Dynamic equity floor protection">The Vault</SecLabel>
            {!vault || Object.keys(vault).length === 0 ? (
              <div style={{ padding:'36px 0', textAlign:'center',
                fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink4)' }}>
                Start Jackal to initialise vault
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap: 12 }}>
                {/* Status banner */}
                <div style={{ padding:'12px 16px', borderRadius:'var(--radius-sm)',
                  background: vault.is_halted ? 'var(--neg-dim)' : 'var(--pos-dim)',
                  border:`1px solid ${vault.is_halted ? 'var(--neg-b)' : 'var(--pos-b)'}`,
                  display:'flex', alignItems:'center', gap: 12 }}>
                  <span style={{ fontSize: 20 }}>{vault.is_halted ? '🔒' : '🟢'}</span>
                  <div style={{ flex:1 }}>
                    <div style={{ fontFamily:'var(--mono)', fontSize: 11, fontWeight: 700,
                      color: vault.is_halted ? 'var(--neg)' : 'var(--pos)' }}>
                      {vault.is_halted ? 'VAULT HALTED' : 'VAULT ACTIVE'}
                    </div>
                    {vault.halt_reason && (
                      <div style={{ fontSize: 10, color:'var(--ink3)', marginTop: 2 }}>{vault.halt_reason}</div>
                    )}
                  </div>
                  {vault.is_halted && (
                    <button onClick={vaultResume} style={{
                      background:'var(--pos)', border:'none', borderRadius:'var(--radius-sm)',
                      padding:'6px 14px', fontFamily:'var(--mono)', fontSize: 10,
                      fontWeight: 700, color:'#fff', cursor:'pointer' }}>Resume</button>
                  )}
                </div>

                {/* Vault stats grid */}
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap: 10 }}>
                  {[
                    { label:'Starting Balance', value:`$${fmt(vault.initial)}` },
                    { label:'Peak Equity',      value:`$${fmt(vault.peak)}`,   color: clr(vault.peak - vault.initial) },
                    { label:'Floor (Protected)',value:`$${fmt(vault.floor)}`,   color:'var(--amber)' },
                    { label:'Locked Gains',     value:`$${fmt(Math.max(0, vault.floor - vault.initial))}`, color:'var(--pos)' },
                    { label:'Peak Gain %',      value:`${fmtPct(vault.peak_pct ?? 0)}`, color: clr(vault.peak_pct ?? 0) },
                    { label:'Floor Lock %',     value:`${fmt(vault.floor_pct ?? 0, 2)}%`, color: (vault.floor_pct??0)>0?'var(--pos)':'var(--ink3)' },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                      borderRadius:'var(--radius-sm)', padding:'12px 14px' }}>
                      <div style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.1em',
                        textTransform:'uppercase', color:'var(--ink4)', marginBottom: 6 }}>{label}</div>
                      <div style={{ fontFamily:'var(--mono)', fontSize: 14, fontWeight: 700,
                        color: color || 'var(--ink3)', fontVariantNumeric:'tabular-nums' }}>{value}</div>
                    </div>
                  ))}
                </div>

                {/* Equity vs Floor progress */}
                <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                  borderRadius:'var(--radius-sm)', padding:'14px 16px' }}>
                  <SecLabel right={`Lock step: +${jackCfg.lock_step_pct}% → locks ${(jackCfg.lock_ratio*100).toFixed(0)}%`}>
                    Equity vs Floor
                  </SecLabel>
                  <div style={{ display:'flex', alignItems:'center', gap: 12 }}>
                    <div style={{ flex:1 }}>
                      <div style={{ height: 8, background:'var(--surface3)', borderRadius: 4, overflow:'hidden' }}>
                        <div style={{
                          height:'100%', borderRadius: 4,
                          background: 'linear-gradient(90deg, var(--amber), var(--pos))',
                          width:`${Math.min(100, Math.max(0, vault.peak_pct ?? 0) * 10)}%`,
                          transition:'width .5s ease',
                        }}/>
                      </div>
                      <div style={{ display:'flex', justifyContent:'space-between', marginTop: 6 }}>
                        <span style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--ink4)' }}>
                          Start ${fmt(vault.initial)}</span>
                        <span style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--amber)' }}>
                          Floor ${fmt(vault.floor)}</span>
                        <span style={{ fontFamily:'var(--mono)', fontSize: 8, color:'var(--pos)' }}>
                          Peak ${fmt(vault.peak)}</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ marginTop: 10, fontSize: 10, color:'var(--ink4)', lineHeight: 1.5 }}>
                    Every +{jackCfg.lock_step_pct}% gain ratchets the floor up to lock {(jackCfg.lock_ratio*100).toFixed(0)}% of gains.
                    Floor never drops. Trading halts if equity hits floor.
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ════ TAB: CONFIG ═══════════════════════════════════════════════════ */}
        {tab === 'config' && (
          <div style={{ padding:'16px 20px', display:'flex', flexDirection:'column', gap: 18 }}>
            {!running && (
              <div>
                <SecLabel>Starting Balance</SecLabel>
                <div style={{ position:'relative' }}>
                  <span style={{ position:'absolute', left: 11, top:'50%',
                    transform:'translateY(-50%)', fontFamily:'var(--mono)',
                    fontSize: 13, color:'var(--ink4)', pointerEvents:'none' }}>$</span>
                  <input type="number" value={balance}
                    onChange={e => setBalance(Number(e.target.value))}
                    style={{ width:'100%', background:'var(--surface2)',
                      border:'1px solid var(--border)', borderRadius:'var(--radius-sm)',
                      padding:'10px 10px 10px 24px',
                      fontFamily:'var(--mono)', fontSize: 16, fontWeight: 700,
                      color:'var(--ink)', outline:'none', transition:'border-color .15s' }}
                    onFocus={e => e.target.style.borderColor = 'var(--border3)'}
                    onBlur={e  => e.target.style.borderColor = 'var(--border)'}
                  />
                </div>
              </div>
            )}

            {running && (
              <div style={{ background:'var(--surface2)', border:'1px solid var(--border)',
                borderRadius:'var(--radius-sm)', padding:'10px 14px',
                fontFamily:'var(--mono)', fontSize: 10, color:'var(--ink3)' }}>
                ℹ Config changes take effect on the next scan cycle
              </div>
            )}

            <hr className="divider" style={{ margin:0 }}/>

            {/* ── Predator config ── */}
            {engineMode === 'predator' && (
              <>
                <div>
                  <SecLabel>🕷 Predator — Mean Reversion Parameters</SecLabel>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 12 }}>
                    <CfgInput label="Max Concurrent Positions" hint="Recommended: 2–4"
                      value={predCfg.max_positions} step={1} min={1} max={10}
                      onChange={v => setPredCfg(c => ({ ...c, max_positions: v }))}/>
                    <CfgInput label="Capital Per Trade ($)" hint="Per-position USD size"
                      value={predCfg.capital_per_trade} step={10} min={10}
                      onChange={v => setPredCfg(c => ({ ...c, capital_per_trade: v }))}/>
                    <CfgInput label="Z-Score Entry Threshold" hint="1.8 = 1.8σ from VWAP"
                      value={predCfg.zscore_entry} step={0.1} min={1.0} max={4.0}
                      onChange={v => setPredCfg(c => ({ ...c, zscore_entry: v }))}/>
                    <CfgInput label="ATR Stop Multiplier" hint="Stop = ATR × this value"
                      value={predCfg.atr_stop_mult} step={0.1} min={0.5} max={5.0}
                      onChange={v => setPredCfg(c => ({ ...c, atr_stop_mult: v }))}/>
                    <CfgInput label="Min Reward:Risk Ratio" hint="TP must be ≥ this × risk"
                      value={predCfg.min_rr_ratio} step={0.1} min={1.5} max={5.0}
                      onChange={v => setPredCfg(c => ({ ...c, min_rr_ratio: v }))}/>
                    <CfgInput label="Max Hold Seconds" hint="Hard close after N seconds"
                      value={predCfg.max_hold_seconds} step={10} min={10} max={300}
                      onChange={v => setPredCfg(c => ({ ...c, max_hold_seconds: v }))}/>
                    <CfgInput label="Scan Interval (s)" hint="Lower = faster but more CPU"
                      value={predCfg.scan_interval} step={0.5} min={0.5} max={10}
                      onChange={v => setPredCfg(c => ({ ...c, scan_interval: v }))}/>
                  </div>
                </div>
                <hr className="divider" style={{ margin:0 }}/>
                <Toggle
                  on={predCfg.long_bias} onChange={() => setPredCfg(c => ({ ...c, long_bias: !c.long_bias }))}
                  label="Long Bias Only"
                  hint="Enable to skip short positions — safer in trending markets"
                />
              </>
            )}

            {/* ── Jackal config ── */}
            {engineMode === 'jackal' && (
              <>
                <div>
                  <SecLabel>🐺 Jackal — Burst Entry Parameters</SecLabel>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 12 }}>
                    <CfgInput label="Max Concurrent Positions" hint="3–8, Jackal trades fast"
                      value={jackCfg.max_positions} step={1} min={1} max={10}
                      onChange={v => setJackCfg(c => ({ ...c, max_positions: v }))}/>
                    <CfgInput label="Capital Per Trade ($)" hint="Keep small — 1–5% of balance"
                      value={jackCfg.capital_per_trade} step={10} min={10}
                      onChange={v => setJackCfg(c => ({ ...c, capital_per_trade: v }))}/>
                    <CfgInput label="Min Streak (ticks)" hint="2 = aggressive, 4 = selective"
                      value={jackCfg.min_streak} step={1} min={2} max={6}
                      onChange={v => setJackCfg(c => ({ ...c, min_streak: v }))}/>
                    <CfgInput label="Min Move % per burst" hint="0.01–0.05%"
                      value={jackCfg.min_move_pct} step={0.005} min={0.005} max={0.1}
                      onChange={v => setJackCfg(c => ({ ...c, min_move_pct: v }))}/>
                    <CfgInput label="Take Profit %" hint="0.08–0.15% target"
                      value={jackCfg.tp_pct} step={0.01} min={0.03} max={0.5}
                      onChange={v => setJackCfg(c => ({ ...c, tp_pct: v }))}/>
                    <CfgInput label="Stop Loss %" hint="0.06–0.10% — must be < TP"
                      value={jackCfg.sl_pct} step={0.01} min={0.03} max={0.3}
                      onChange={v => setJackCfg(c => ({ ...c, sl_pct: v }))}/>
                    <CfgInput label="Max Hold Seconds" hint="5–15s for micro-momentum"
                      value={jackCfg.max_hold_seconds} step={1} min={3} max={60}
                      onChange={v => setJackCfg(c => ({ ...c, max_hold_seconds: v }))}/>
                    <CfgInput label="Scan Interval (s)" hint="0.05–0.10s (70ms default)"
                      value={jackCfg.scan_interval} step={0.01} min={0.03} max={1.0}
                      onChange={v => setJackCfg(c => ({ ...c, scan_interval: v }))}/>
                  </div>
                </div>
                <hr className="divider" style={{ margin:0 }}/>
                <div>
                  <SecLabel>🔒 Vault Parameters</SecLabel>
                  <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap: 12 }}>
                    <CfgInput label="Lock Step %" hint="Every +N% gain evaluates floor"
                      value={jackCfg.lock_step_pct} step={0.1} min={0.1} max={2.0}
                      onChange={v => setJackCfg(c => ({ ...c, lock_step_pct: v }))}/>
                    <CfgInput label="Lock Ratio" hint="0.6 = lock 60% of gains"
                      value={jackCfg.lock_ratio} step={0.05} min={0.3} max={0.9}
                      onChange={v => setJackCfg(c => ({ ...c, lock_ratio: v }))}/>
                    <CfgInput label="Max Daily DD %" hint="Hard stop for the day"
                      value={jackCfg.max_daily_dd_pct} step={0.5} min={1.0} max={10.0}
                      onChange={v => setJackCfg(c => ({ ...c, max_daily_dd_pct: v }))}/>
                    <CfgInput label="OFI Floor" hint="Min bid pressure for LONG (0.35)"
                      value={jackCfg.ofi_floor} step={0.05} min={0.2} max={0.5}
                      onChange={v => setJackCfg(c => ({ ...c, ofi_floor: v }))}/>
                  </div>
                </div>
              </>
            )}

            <button
              onClick={applyConfig}
              style={{ background:'var(--surface3)', border:'1px solid var(--border2)',
                borderRadius:'var(--radius-sm)', padding:'11px 0', width:'100%',
                fontFamily:'var(--mono)', fontSize: 10, fontWeight: 700,
                letterSpacing:'0.08em', textTransform:'uppercase',
                color:'var(--ink)', cursor:'pointer', transition:'background .15s, border-color .15s' }}
              onMouseEnter={e => { e.currentTarget.style.background='var(--surface4)'; e.currentTarget.style.borderColor='var(--border3)'; }}
              onMouseLeave={e => { e.currentTarget.style.background='var(--surface3)'; e.currentTarget.style.borderColor='var(--border2)'; }}
            >Apply Config</button>
          </div>
        )}
      </div>

      {/* ── Activity log ──────────────────────────────────────────────────────── */}
      {running && events.length > 0 && (
        <div className="card">
          <div style={{ padding:'9px 16px', borderBottom:'1px solid var(--border)',
            display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <span style={{ fontFamily:'var(--mono)', fontSize: 8, letterSpacing:'0.12em',
              textTransform:'uppercase', color:'var(--ink4)' }}>Activity · {eng.emoji} {eng.name}</span>
            <LiveDot on={running}/>
          </div>
          <div style={{ maxHeight: 176, overflowY:'auto', padding:'5px 0' }}>
            {events.map((ev, i) => {
              const tagMap = { ENTRY:'badge-green', EXIT:'badge-accent', ENGINE:'badge-muted',
                CIRCUIT:'badge-red', CONFIG:'badge-amber', ERROR:'badge-red',
                VAULT:'badge-amber', BURST:'badge-green' };
              return (
                <div key={i} style={{ padding:'4px 16px', display:'flex', gap: 10, alignItems:'flex-start',
                  background: i === 0 ? 'var(--surface2)' : 'transparent' }}>
                  <span style={{ fontFamily:'var(--mono)', fontSize: 9, color:'var(--ink4)',
                    flexShrink: 0, minWidth: 46 }}>{ev.time}</span>
                  <span className={`badge ${tagMap[ev.tag] || 'badge-muted'}`}
                    style={{ fontSize: 7, flexShrink: 0 }}>{ev.tag}</span>
                  <span style={{ fontSize: 11, color:'var(--ink3)', lineHeight: 1.45 }}>{ev.msg}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}