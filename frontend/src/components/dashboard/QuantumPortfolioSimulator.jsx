import { useState, useEffect, useRef } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, BarChart, Bar, Cell } from 'recharts';
import { API } from "../../config";

// ─── Shared UI Components ──────────────────────────────────────

const Spinner = ({ size = 16, color = 'var(--gold)' }) => (
  <div style={{
    width: size, height: size, flexShrink: 0,
    border: `1.5px solid var(--border2)`,
    borderTopColor: color, borderRadius: '50%',
  }} className="spin-icon" />
);

const ColHead = ({ children, style: sx }) => (
  <span style={{
    fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em',
    textTransform: 'uppercase', color: 'var(--ink4)', ...sx,
  }}>{children}</span>
);

const Toggle = ({ value, onChange, label }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }} onClick={() => onChange(!value)}>
    <div style={{
      width: 36, height: 20, borderRadius: 10,
      background: value ? 'var(--gold)' : 'var(--surface3)',
      border: `1px solid ${value ? 'transparent' : 'var(--border2)'}`,
      position: 'relative', transition: 'all .2s', flexShrink: 0
    }}>
      <div style={{
        width: 14, height: 14, borderRadius: '50%',
        background: value ? '#000' : 'var(--ink3)',
        position: 'absolute', top: 2,
        left: value ? 18 : 2,
        transition: 'left .2s'
      }} />
    </div>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: value ? 'var(--ink)' : 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</span>
  </div>
);

const SectionTitle = ({ children }) => (
  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--gold)', letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: 14, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>{children}</div>
);

// ─── Equity Curve Chart ────────────────────────────────────────
function EquityCurveChart({ data, initialBalance }) {
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => { setIsMounted(true); }, []);

  if (!data?.length || !isMounted) return <div style={{ height: 340 }} />;

  const isProfit = data[data.length - 1].balance >= initialBalance;
  const accentColor = isProfit ? "#10b981" : "#f43f5e";
  const balances = data.map(d => d.balance);
  const minBal = Math.min(...balances, initialBalance);
  const maxBal = Math.max(...balances, initialBalance);
  const buffer = (maxBal - minBal) * 0.12 || 1;

  return (
    <div style={{ width: '100%', height: 340, minHeight: 340, minWidth: 0 }}>
      <ResponsiveContainer width="99%" height="100%" debounce={50}>
        <AreaChart data={data} margin={{ top: 10, right: 30, left: -20, bottom: 10 }}>
          <defs>
            <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={accentColor} stopOpacity={0.3}/>
              <stop offset="95%" stopColor={accentColor} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
          <XAxis dataKey="time" axisLine={false} tickLine={false}
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'var(--mono)' }}
            minTickGap={60}
            tickFormatter={(val) => { const d = new Date(val); return `${d.getDate()} ${d.toLocaleString('en-US', { month: 'short' })}`; }}
          />
          <YAxis axisLine={false} tickLine={false}
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'var(--mono)' }}
            domain={[minBal - buffer, maxBal + buffer]}
            tickFormatter={(val) => `$${val.toLocaleString()}`} orientation="right"
          />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '11px', fontFamily: 'var(--mono)', color: '#f8fafc' }}
            itemStyle={{ color: accentColor, fontWeight: 700 }}
            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
            formatter={(value) => [`$${value.toLocaleString(undefined, {minimumFractionDigits:2})}`, "Equity"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <ReferenceLine y={initialBalance} stroke="#475569" strokeDasharray="4 4"
            label={{ value: 'Initial', position: 'insideBottomRight', fill: '#475569', fontSize: 9, fontFamily: 'var(--mono)' }}
          />
          <Area type="monotone" dataKey="balance" stroke={accentColor} strokeWidth={2.5}
            fillOpacity={1} fill="url(#colorBalance)" dot={false} animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Win/Loss Bar ───────────────────────────────────────────────
function WinLossBar({ wins, losses, be }) {
  const total = wins + losses + be;
  if (total === 0) return null;
  const wp = (wins/total*100).toFixed(1);
  const lp = (losses/total*100).toFixed(1);
  const bp = (be/total*100).toFixed(1);
  return (
    <div style={{ width: "100%", height: "6px", borderRadius: "4px", overflow: "hidden", display: "flex", gap: "2px", background: 'var(--surface3)' }}>
      <div style={{ width: `${wp}%`, background: "var(--green)", borderRadius: "4px 0 0 4px" }} />
      <div style={{ width: `${bp}%`, background: "var(--ink4)" }} />
      <div style={{ width: `${lp}%`, background: "var(--red)", borderRadius: "0 4px 4px 0" }} />
    </div>
  );
}

// ─── Regime Badge ───────────────────────────────────────────────
function RegimeBadge({ regime }) {
  const map = {
    LOW_VOL_BULLISH : { cls: "badge-green", label: "BULL" },
    SIDEWAYS_CHOP   : { cls: "badge-gold",  label: "CHOP" },
    HIGH_VOL_BEARISH: { cls: "badge-red",   label: "BEAR" },
  };
  const cfg = map[regime] || { cls: "badge-muted", label: regime?.replace(/_/g,' ').slice(0,6) || '?' };
  return <span className={`badge ${cfg.cls}`} style={{ fontSize: 9 }}>{cfg.label}</span>;
}

// ─── ICT Strength Badge ─────────────────────────────────────────
function IctBadge({ strength }) {
  const map = {
    STRONG     : { color: 'var(--green)', bg: 'rgba(0,255,136,0.1)' },
    VERY_STRONG: { color: 'var(--green)', bg: 'rgba(0,255,136,0.15)' },
    MODERATE   : { color: 'var(--gold)',  bg: 'rgba(255,193,7,0.1)' },
    WEAK       : { color: 'var(--red)',   bg: 'rgba(255,68,102,0.1)' },
  };
  const cfg = map[strength] || { color: 'var(--ink2)', bg: 'transparent' };
  return (
    <span style={{ fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 700, color: cfg.color,
      background: cfg.bg, padding: '2px 6px', borderRadius: 4, letterSpacing: '0.05em' }}>
      {strength || '?'}
    </span>
  );
}

// ─── Metric Card ────────────────────────────────────────────────
function MetricCard({ label, value, color, sublabel, icon }) {
  return (
    <div className="card" style={{ padding: "20px", background: 'var(--surface2)' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: "8px", color: "var(--ink2)", letterSpacing: "0.15em",
        marginBottom: "12px", display: "flex", justifyContent: "space-between", textTransform: 'uppercase' }}>
        <span>{label}</span>
        {icon && <span style={{ color: 'var(--gold)' }}>[{icon}]</span>}
      </div>
      <div style={{ fontSize: "26px", fontWeight: 800, color, letterSpacing: "-0.02em", fontVariantNumeric: 'tabular-nums', fontFamily: 'var(--mono)' }}>
        {value}
      </div>
      {sublabel && <div style={{ fontFamily: 'var(--mono)', fontSize: "7px", color: "var(--ink2)", marginTop: "8px", textTransform: 'uppercase', letterSpacing: '0.05em' }}>{sublabel}</div>}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════

const DEFAULT_CONFIG = {
  initial_balance      : 100,
  risk_per_trade       : 2,
  scan_universe        : "US",
  tp_rr_ratio          : 2,
  min_screener_score   : 70,
  // v2.0 additions
  use_adaptive_kelly   : true,
  kelly_fraction       : 0.25,
  min_regime_conf      : 55,
  min_ict_strength     : "MODERATE",
  consec_loss_guard    : 3,
  regime_size_bull     : 1.0,
  regime_size_chop     : 0.6,
  circuit_breaker_dd   : 15,
  max_risk_cap_pct     : 3.0,
  use_partial_tp       : true,
  lookback_years       : 1,
};

export default function QuantumPortfolioSimulator() {
  const [config, setConfig]         = useState(DEFAULT_CONFIG);
  const [result, setResult]         = useState(null);
  const [isRunning, setIsRunning]   = useState(false);
  const [progress, setProgress]     = useState(0);
  const [activeTab, setActiveTab]   = useState("overview");
  const [tradeFilter, setTradeFilter] = useState("ALL");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [animKey, setAnimKey]       = useState(0);
  const progressRef  = useRef(null);
  const readerRef    = useRef(null);   // fetch reader para cancel
  const [simPhase, setSimPhase]       = useState(0);
  const [simLog, setSimLog]           = useState([]);
  const [liveTrades, setLiveTrades]   = useState(0);
  const [liveBalance, setLiveBalance] = useState(0);
  const [liveWins, setLiveWins]       = useState(0);
  const [liveDD, setLiveDD]           = useState(0);

  const setCfg = (key, val) => setConfig(c => ({ ...c, [key]: val }));

  // ── Phase definitions — driven by real SSE events from backend ──
  const SIM_PHASES = [
    { label: "FETCH",   long: "FETCHING DATA",        sub: "Pulling historical OHLCV from API — all tickers",       color: "#38bdf8" },
    { label: "GATE",    long: "INITIALIZING ARMOR",   sub: "Equity Armor + 3-Layer gate setup",                     color: "#fbbf24" },
    { label: "SIM",     long: "HFT TRADES",    sub: "Kelly sizing — partial TP — equity armor enforcement",  color: "#34d399" },
    { label: "METRICS", long: "COMPUTING METRICS",    sub: "Sharpe — Calmar — walk-forward validation — DSR",       color: "#f472b6" },
  ];

  const PHASE_IDX = { FETCH: 0, GATE: 1, SIM: 2, METRICS: 3 };

  const runSim = async () => {
    setIsRunning(true);
    setProgress(0);
    setResult(null);
    setAnimKey(k => k + 1);
    setSimPhase(0);
    setSimLog([]);
    setLiveTrades(0);
    setLiveBalance(config.initial_balance);
    setLiveWins(0);
    setLiveDD(0);

    // Cleanup function untuk cancel stream kalau component unmount
    const cleanup = () => {
      if (readerRef.current) {
        try { readerRef.current.cancel(); } catch (_) {}
        readerRef.current = null;
      }
    };

    try {
      const response = await fetch(`${API}/api/simulate/stream`, {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify(config),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const reader  = response.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let   buf     = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        // SSE format: "data: <json>


        const parts = buf.split("\n\n");
        buf = parts.pop(); 

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          let evt;
          try { evt = JSON.parse(line.slice(6)); } catch (_) { continue; }

          switch (evt.type) {

            case "phase":
              setSimPhase(PHASE_IDX[evt.phase] ?? 0);
              setProgress(evt.progress ?? 0);
              break;

            case "tick":
              // Data 100% real dari backend loop
              setProgress(evt.progress ?? 0);
              if (evt.phase && PHASE_IDX[evt.phase] !== undefined)
                setSimPhase(PHASE_IDX[evt.phase]);
              setLiveBalance(evt.balance ?? config.initial_balance);
              setLiveTrades(evt.trades ?? 0);
              setLiveWins(evt.wins ?? 0);
              setLiveDD(evt.dd_pct ?? 0);
              if (evt.log) setSimLog(prev => [...prev.slice(-24), evt.log]);
              break;

            case "trade":
              // Per-trade event — sudah terekam di tick wins/losses
              // Kita tambahkan ke log stream sebagai info tambahan
              if (evt.ticker) {
                const sign = (evt.pnl_usd ?? 0) >= 0 ? "+" : "";
                setSimLog(prev => [...prev.slice(-24), {
                  tag : evt.outcome === "WIN" ? "WIN" : "LOSS",
                  text: `${evt.ticker}  ${evt.direction}  pnl=${sign}$${(evt.pnl_usd??0).toFixed(2)}  bal=$${(evt.balance??0).toFixed(2)}`,
                }]);
              }
              break;

            case "done":
              setProgress(100);
              setSimPhase(SIM_PHASES.length - 1);
              if (evt.report) setResult(evt.report);
              break;

            case "error":
              throw new Error(evt.message || "Simulation error");
          }
        }
      }

    } catch (error) {
      console.error("Simulation Error:", error);
      alert("Simulation Error: " + error.message);
    } finally {
      cleanup();
      setIsRunning(false);
      setProgress(0);
    }
  };

  const isProfit = result && result.summary.final_balance >= config.initial_balance;
  const filteredTrades = result?.trades?.filter(t =>
    tradeFilter === "ALL" ? true : t.outcome === tradeFilter
  ) || [];

  // ── Pre-compute gate quality stats ──
  const gateStats = result ? (() => {
    const totalConsidered = result.summary.total_trades + (result.summary.trades_filtered || 0);
    const filterRate = totalConsidered > 0
      ? ((result.summary.trades_filtered || 0) / totalConsidered * 100).toFixed(1)
      : 0;
    const strongICT = result.trades?.filter(t => t.ict_strength === "STRONG" || t.ict_strength === "VERY_STRONG").length || 0;
    const avgRegConf = result.trades?.length
      ? (result.trades.reduce((s, t) => s + (t.regime_conf || 0), 0) / result.trades.length).toFixed(1)
      : 0;
    return { filterRate, strongICT, avgRegConf };
  })() : null;

  return (
    <div style={{ paddingTop: 40, paddingBottom: 96 }}>

      {/* ── PAGE HEADER ── */}
      <div className="anim" style={{ marginBottom: 40 }}>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 12 }}>
          Time Machine · Portfolio Backtest Engine v2.0
        </p>
        <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--ink)', lineHeight: 1.1, marginBottom: 14 }}>
          Quantum Portfolio Simulator
        </h1>
        <p style={{ fontSize: 14, color: 'var(--ink)', lineHeight: 1.7, maxWidth: 680 }}>
          Pipeline kuantitatif 4 layer: Screener → 3-Layer Confirmation Gate → Kelly-Adaptive Sizing → Partial TP Risk Manager.
          Mendukung analisis data historis hingga 10 tahun untuk bukti validitas strategi yang lebih kuat.
        </p>
      </div>

      {/* ── CONTROLS PANEL ── */}
      <div className="anim d1 card" style={{ padding: 24, marginBottom: 32 }}>

        {/* Universe + Run */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 24 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            {["US", "IDX", "CRYPTO", "UNIVERSAL"].map(u => {
              const active = config.scan_universe === u;
              return (
                <button key={u} onClick={() => setCfg('scan_universe', u)} style={{
                  background: active ? 'var(--gold)' : 'var(--surface3)',
                  border: `1px solid ${active ? 'transparent' : 'var(--border)'}`,
                  borderRadius: 6, padding: '7px 16px',
                  fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 700 : 400,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  color: active ? '#ffffffff' : 'var(--ink2)', cursor: 'pointer', transition: 'all .15s',
                }}>{u === 'US' ? 'US Markets' : u === 'IDX' ? 'IDX (Indo)' : u === 'UNIVERSAL' ? 'Universal' : u}</button>
              );
            })}
          </div>

          <button onClick={runSim} disabled={isRunning} style={{
            background: isRunning ? 'var(--surface3)' : 'var(--gold)',
            border: 'none', color: isRunning ? 'var(--ink3)' : '#ffffffff',
            padding: '9px 28px', borderRadius: 8,
            fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)',
            letterSpacing: '0.06em', textTransform: 'uppercase',
            display: 'flex', alignItems: 'center', gap: 10,
            opacity: isRunning ? 0.7 : 1, cursor: isRunning ? 'not-allowed' : 'pointer', transition: 'all .2s',
          }}>
            {isRunning ? <><Spinner size={13} /> Simulating…</> : '⬡ Run Simulation'}
          </button>
        </div>

        {/* Core Config */}
        <SectionTitle>Core Configuration</SectionTitle>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "14px", marginBottom: 20 }}>
          {[
            { key: "initial_balance",     label: "Initial Capital",     prefix: "$" },
            { key: "risk_per_trade",       label: "Base Risk/Trade",     suffix: "%" },
            { key: "tp_rr_ratio",          label: "Reward:Risk Ratio",   suffix: ":1" },
            { key: "min_screener_score",   label: "Min Screener Score",  suffix: "" },
            { key: "lookback_years",       label: "Lookback Period",     suffix: "Years" },
          ].map(({ key, label, prefix, suffix }) => (
            <div key={key}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>{label}</div>
              <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface3)', border: '1px solid var(--border2)', borderRadius: 8, overflow: 'hidden', height: 36 }}>
                {prefix && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingLeft: 12 }}>{prefix}</span>}
                <input type="number" value={config[key]} onChange={e => setCfg(key, +e.target.value)}
                  style={{ flex: 1, background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', padding: '0 12px', textAlign: prefix ? 'left' : 'center', outline: 'none', width: '100%' }}
                />
                {suffix && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingRight: 12 }}>{suffix}</span>}
              </div>
            </div>
          ))}
        </div>

        {/* Advanced Toggle */}
        <button onClick={() => setShowAdvanced(!showAdvanced)} style={{
          background: 'transparent', border: '1px solid var(--border)', borderRadius: 6,
          padding: '6px 14px', fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)',
          letterSpacing: '0.1em', textTransform: 'uppercase', cursor: 'pointer', marginBottom: showAdvanced ? 20 : 0,
          display: 'flex', alignItems: 'center', gap: 8
        }}>
          {showAdvanced ? '▲' : '▼'} Advanced Configuration (v2.0 Upgrades)
        </button>

        {showAdvanced && (
          <div style={{ marginTop: 4 }}>

            {/* Gate Configuration */}
            <SectionTitle>Gate Configuration — 3-Layer Filter</SectionTitle>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "14px", marginBottom: 20 }}>
              <div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>Min HMM Confidence</div>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface3)', border: '1px solid var(--border2)', borderRadius: 8, overflow: 'hidden', height: 36 }}>
                  <input type="number" value={config.min_regime_conf} onChange={e => setCfg('min_regime_conf', +e.target.value)}
                    style={{ flex: 1, background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', padding: '0 12px', textAlign: 'center', outline: 'none' }}
                  />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingRight: 12 }}>%</span>
                </div>
              </div>
              <div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>Min ICT Strength</div>
                <div style={{ background: 'var(--surface3)', border: '1px solid var(--border2)', borderRadius: 8, height: 36, overflow: 'hidden' }}>
                  <select value={config.min_ict_strength} onChange={e => setCfg('min_ict_strength', e.target.value)}
                    style={{ width: '100%', height: '100%', background: 'transparent', border: 'none', fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink)', padding: '0 12px', outline: 'none' }}>
                    <option value="WEAK">WEAK (Loose)</option>
                    <option value="MODERATE">MODERATE (Default)</option>
                    <option value="STRONG">STRONG (Strict)</option>
                  </select>
                </div>
              </div>
              <div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>Circuit Breaker DD</div>
                <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface3)', border: '1px solid var(--border2)', borderRadius: 8, overflow: 'hidden', height: 36 }}>
                  <input type="number" value={config.circuit_breaker_dd} onChange={e => setCfg('circuit_breaker_dd', +e.target.value)}
                    style={{ flex: 1, background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', padding: '0 12px', textAlign: 'center', outline: 'none' }}
                  />
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingRight: 12 }}>%</span>
                </div>
              </div>
            </div>

            {/* Kelly Configuration */}
            <SectionTitle>Kelly Criterion — Adaptive Position Sizing</SectionTitle>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center', marginBottom: 16 }}>
              <Toggle value={config.use_adaptive_kelly} onChange={v => setCfg('use_adaptive_kelly', v)} label="Kelly Adaptive Sizing" />
              <Toggle value={config.use_partial_tp} onChange={v => setCfg('use_partial_tp', v)} label="Partial TP at 1.5R" />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "14px", marginBottom: 20 }}>
              {[
                { key: "kelly_fraction",  label: "Kelly Fraction",    suffix: "×",  note: "0.25=Quarter" },
                { key: "max_risk_cap_pct",label: "Max Risk Cap",       suffix: "%",  note: "Hard ceiling" },
                { key: "consec_loss_guard",label: "Loss Streak Guard", suffix: "trades", note: "Then cut size" },
              ].map(({ key, label, suffix, note }) => (
                <div key={key}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>{label}</div>
                  <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface3)', border: '1px solid var(--border2)', borderRadius: 8, overflow: 'hidden', height: 36 }}>
                    <input type="number" value={config[key]} onChange={e => setCfg(key, +e.target.value)}
                      style={{ flex: 1, background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', padding: '0 12px', textAlign: 'center', outline: 'none' }}
                    />
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', paddingRight: 10 }}>{suffix}</span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginTop: 4 }}>{note}</div>
                </div>
              ))}
            </div>

            {/* Regime Sizing */}
            <SectionTitle>Regime-Dynamic Size Scaling</SectionTitle>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "14px" }}>
              {[
                { key: "regime_size_bull", label: "Bull Regime Scale",  color: 'var(--green)', note: "×1.0 = full size" },
                { key: "regime_size_chop", label: "Chop Regime Scale",  color: 'var(--gold)',  note: "×0.6 = reduced" },
              ].map(({ key, label, color, note }) => (
                <div key={key}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 7 }}>
                    <span style={{ color }}>{label}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface3)', border: `1px solid ${color}44`, borderRadius: 8, overflow: 'hidden', height: 36 }}>
                    <input type="number" step="0.05" min="0.1" max="1.5" value={config[key]} onChange={e => setCfg(key, +e.target.value)}
                      style={{ flex: 1, background: 'none', border: 'none', fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color, padding: '0 12px', textAlign: 'center', outline: 'none' }}
                    />
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingRight: 12 }}>×</span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginTop: 4 }}>{note}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── PIPELINE INDICATOR ── */}
      {!result && !isRunning && (
        <div className="card" style={{ padding: '16px 24px', marginBottom: 24, background: 'var(--surface2)' }}>
          <div style={{ display: 'flex', gap: 0, alignItems: 'center', flexWrap: 'wrap' }}>
            {[
              { label: 'Screener', sub: 'Score ≥ ' + config.min_screener_score, color: 'var(--green)', icon: '①' },
              { label: 'HMM Soft', sub: 'Conf → Size Scale', color: 'var(--purple)', icon: '②' },
              { label: 'ICT Soft', sub: 'Strength → Size Scale', color: 'var(--blue)', icon: '③' },
              { label: 'Kelly Size', sub: config.use_adaptive_kelly ? 'Adaptive ' + (config.kelly_fraction * 100).toFixed(0) + '%K' : 'Fixed ' + config.risk_per_trade + '%', color: 'var(--gold)', icon: '④' },
              { label: 'Partial TP', sub: config.use_partial_tp ? '1.5R Lock' : 'Disabled', color: 'var(--amber)', icon: '⑤' },
            ].map(({ label, sub, color, icon }, i, arr) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ textAlign: 'center', padding: '8px 16px' }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 16, color, marginBottom: 2 }}>{icon}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginTop: 2 }}>{sub}</div>
                </div>
                {i < arr.length - 1 && <span style={{ color: 'var(--border2)', fontSize: 18, marginRight: 4 }}>→</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── LOADING STATE v3 — Clean Data Monitor ── */}
      {isRunning && (() => {
        const phase      = SIM_PHASES[Math.min(simPhase, SIM_PHASES.length - 1)];
        const pct        = progress.toFixed(0);
        const balanceDelta = liveBalance - config.initial_balance;
        const isUp       = balanceDelta >= 0;
        const winRate    = liveTrades > 0 ? (liveWins / liveTrades * 100) : 0;

        return (
          <div className="anim" style={{ marginBottom: 24 }}>

            {/* ── Row 1: Phase header + progress bar ── */}
            <div style={{
              padding: '16px 20px 14px', marginBottom: 10,
              background: 'var(--surface2)',
              border: '1px solid var(--border)',
              borderTop: `2px solid ${phase.color}`,
              borderRadius: 10,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 10 }}>
                {/* Left: phase label + sub */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 3 }}>
                    <div style={{
                      width: 7, height: 7, borderRadius: '50%',
                      background: phase.color,
                      boxShadow: `0 0 8px ${phase.color}`,
                      animation: 'pulse-dot 1.2s ease-in-out infinite',
                    }} />
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 700, color: phase.color, letterSpacing: '0.18em', textTransform: 'uppercase' }}>
                      {phase.long}
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', letterSpacing: '0.04em', paddingLeft: 17 }}>
                    {phase.sub}
                  </div>
                </div>
                {/* Right: % + pip strip */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 900, color: 'var(--ink)', letterSpacing: '-0.04em', lineHeight: 1 }}>{pct}<span style={{ fontSize: 11, color: 'var(--ink3)', marginLeft: 1 }}>%</span></span>
                  <div style={{ display: 'flex', gap: 4 }}>
                    {SIM_PHASES.map((ph, i) => (
                      <div key={i} title={ph.label} style={{
                        height: 3,
                        width: i === simPhase ? 24 : 10,
                        borderRadius: 2,
                        background: i < simPhase ? '#34d399' : i === simPhase ? ph.color : 'var(--border2)',
                        transition: 'all 0.4s ease',
                        boxShadow: i === simPhase ? `0 0 6px ${ph.color}88` : 'none',
                      }} />
                    ))}
                  </div>
                </div>
              </div>
              {/* Progress track */}
              <div style={{ height: 2, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                <div style={{
                  width: `${progress}%`, height: '100%',
                  background: phase.color,
                  transition: 'width 0.15s ease',
                  boxShadow: `0 0 6px ${phase.color}88`,
                }} />
              </div>
            </div>

            {/* ── Row 2: Stats left | Log right ── */}
            <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 10, marginBottom: 10 }}>

              {/* Left: stat grid */}
              <div style={{
                background: 'var(--surface2)', border: '1px solid var(--border)',
                borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 16,
              }}>
                {/* Balance */}
                <div style={{ borderBottom: '1px solid var(--border)', paddingBottom: 14 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 5 }}>Running Balance</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 24, fontWeight: 900, letterSpacing: '-0.03em', fontVariantNumeric: 'tabular-nums',
                    color: isUp ? '#34d399' : '#f87171' }}>
                    ${liveBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: isUp ? '#34d399' : '#f87171', marginTop: 3 }}>
                    {isUp ? '+' : ''}{((balanceDelta / config.initial_balance) * 100).toFixed(2)}%
                    <span style={{ color: 'var(--ink3)', marginLeft: 6 }}>vs ${config.initial_balance.toLocaleString()}</span>
                  </div>
                </div>

                {/* Trade count */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderBottom: '1px solid var(--border)', paddingBottom: 14 }}>
                  {[
                    { label: 'Trades', val: liveTrades, color: 'var(--ink)' },
                    { label: 'Win Rate', val: liveTrades > 0 ? winRate.toFixed(1) + '%' : '--', color: winRate >= 50 ? '#34d399' : winRate > 0 ? '#f87171' : 'var(--ink3)' },
                  ].map(({label, val, color}) => (
                    <div key={label}>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 4 }}>{label}</div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 800, color, fontVariantNumeric: 'tabular-nums' }}>{val}</div>
                    </div>
                  ))}
                </div>

                {/* Drawdown */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>Max Drawdown</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)' }}>limit {config.circuit_breaker_dd}%</div>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 700, fontVariantNumeric: 'tabular-nums', marginBottom: 6,
                    color: liveDD > 10 ? '#f87171' : liveDD > 5 ? '#fbbf24' : '#34d399' }}>
                    -{liveDD.toFixed(2)}%
                  </div>
                  <div style={{ height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(liveDD / config.circuit_breaker_dd * 100, 100)}%`,
                      height: '100%', borderRadius: 2,
                      background: liveDD > 10 ? '#f87171' : liveDD > 5 ? '#fbbf24' : '#34d399',
                      transition: 'width 0.4s, background 0.4s',
                    }} />
                  </div>
                </div>
              </div>

              {/* Right: log stream */}
              <div style={{
                background: '#080c10', border: '1px solid #1a2332',
                borderRadius: 10, overflow: 'hidden', display: 'flex', flexDirection: 'column',
              }}>
                {/* Log header — clean, no traffic dots */}
                <div style={{
                  padding: '9px 16px', borderBottom: '1px solid #1a2332',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  background: '#0d1117',
                }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#4a5568', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                    apex_engine  /  stdout
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#34d399', animation: 'pulse-dot 1.4s ease-in-out infinite' }} />
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 7, color: '#34d399', letterSpacing: '0.1em' }}>RUNNING</span>
                  </div>
                </div>

                {/* Log body */}
                <div style={{ flex: 1, padding: '10px 0', overflowY: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                  {simLog.length === 0 && (
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: '#2a3a4a', padding: '0 16px' }}>
                      initializing apex engine...
                    </div>
                  )}
                  {simLog.map((entry, i) => {
                    const isLast = i === simLog.length - 1;
                    const tag    = entry.tag || 'INFO';
                    const tagColors = {
                      WIN:    { tag: '#34d399', text: '#a7f3d0' },
                      LOSS:   { tag: '#f87171', text: '#fca5a5' },
                      ARMOR:  { tag: '#fbbf24', text: '#fde68a' },
                      GATE:   { tag: '#a78bfa', text: '#c4b5fd' },
                      SCREEN: { tag: '#38bdf8', text: '#7dd3fc' },
                      DATA:   { tag: '#4a5568', text: '#718096' },
                    };
                    const colors = tagColors[tag] || { tag: '#4a5568', text: '#718096' };
                    const rowOpacity = 0.35 + (i / Math.max(simLog.length - 1, 1)) * 0.65;

                    return (
                      <div key={i} style={{
                        display: 'grid', gridTemplateColumns: '28px 52px 1fr',
                        alignItems: 'baseline', gap: 0,
                        padding: '2px 16px',
                        opacity: rowOpacity,
                        background: isLast ? 'rgba(255,255,255,0.02)' : 'transparent',
                        borderLeft: isLast ? `2px solid ${phase.color}44` : '2px solid transparent',
                      }}>
                        {/* Line number */}
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: '#2a3a4a', userSelect: 'none' }}>
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        {/* Tag */}
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 7, fontWeight: 700, letterSpacing: '0.08em',
                          color: colors.tag, textTransform: 'uppercase',
                        }}>
                          [{tag}]
                        </span>
                        {/* Text */}
                        <span style={{
                          fontFamily: 'var(--mono)', fontSize: 9, color: colors.text,
                          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          letterSpacing: '0.01em',
                        }}>
                          {entry.text}
                        </span>
                      </div>
                    );
                  })}
                  {/* Blinking cursor on last line */}
                  <div style={{ padding: '2px 16px', fontFamily: 'var(--mono)', fontSize: 9 }}>
                    <span style={{ color: phase.color, animation: 'blink-cursor 0.9s step-end infinite' }}>_</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ── Row 3: Phase timeline — text-only, no icons ── */}
            <div style={{
              display: 'flex', alignItems: 'stretch',
              background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 10, overflow: 'hidden',
            }}>
              {SIM_PHASES.map((ph, i) => {
                const done    = i < simPhase;
                const active  = i === simPhase;
                const pending = i > simPhase;
                return (
                  <div key={i} style={{
                    flex: 1, padding: '10px 14px',
                    borderRight: i < SIM_PHASES.length - 1 ? '1px solid var(--border)' : 'none',
                    background: active ? `${ph.color}0d` : 'transparent',
                    borderTop: active ? `2px solid ${ph.color}` : '2px solid transparent',
                    transition: 'all 0.3s',
                    opacity: pending ? 0.35 : 1,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{
                        fontFamily: 'var(--mono)', fontSize: 7, fontWeight: 700,
                        color: done ? '#34d399' : active ? ph.color : 'var(--ink3)',
                        letterSpacing: '0.12em', textTransform: 'uppercase',
                      }}>
                        {ph.label}
                      </span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 7,
                        color: done ? '#34d399' : active ? ph.color : 'var(--border2)' }}>
                        {done ? 'done' : active ? 'running' : '...'}
                      </span>
                    </div>
                    <div style={{ height: 1, background: done ? '#34d39944' : active ? `${ph.color}44` : 'var(--border)', borderRadius: 1, transition: 'background 0.4s' }} />
                  </div>
                );
              })}
            </div>

          </div>
        );
      })()}

            {/* ── RESULTS ── */}
      {result && !isRunning && (
        <div key={animKey} className="anim d2">

          {/* Headline Card */}
          <div className="card" style={{
            background: isProfit ? 'rgba(0,255,136,0.03)' : 'rgba(255,68,102,0.03)',
            border: `1px solid ${isProfit ? 'var(--green)' : 'var(--red)'}44`,
            padding: "28px 32px", marginBottom: "20px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexWrap: "wrap", gap: "24px", position: 'relative', overflow: 'hidden'
          }}>
            <div style={{ position: 'absolute', top: -50, right: -50, width: 200, height: 200,
              background: isProfit ? 'var(--green)' : 'var(--red)', filter: 'blur(100px)', opacity: 0.08, pointerEvents: 'none' }} />
            <div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', letterSpacing: "0.2em", marginBottom: "10px", textTransform: 'uppercase' }}>
                Final Portfolio Value · {result.config.scan_universe} · v2.0 Engine
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "16px" }}>
                <div style={{ fontSize: "44px", fontWeight: 900, letterSpacing: "-0.04em",
                  color: isProfit ? "var(--green)" : "var(--red)", fontVariantNumeric: 'tabular-nums' }}>
                  ${result.summary.final_balance.toLocaleString("en-US", {minimumFractionDigits: 2})}
                </div>
                <div style={{ fontSize: "16px", fontWeight: 700, fontFamily: 'var(--mono)',
                  color: isProfit ? "var(--green)" : "var(--red)", padding: "5px 12px",
                  background: isProfit ? "rgba(0,255,136,0.1)" : "rgba(255,68,102,0.1)",
                  borderRadius: "8px", border: '1px solid currentColor' }}>
                  {result.summary.total_return_pct >= 0 ? "+" : ""}{result.summary.total_return_pct}%
                </div>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: "11px", color: 'var(--ink)', marginTop: "10px", display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                <span>Initial: ${result.config.initial_balance.toLocaleString()}</span>
                <span style={{ opacity: 0.3 }}>|</span>
                <span>Kelly Avg: {(result.summary.kelly_avg_fraction * 100).toFixed(1)}%K</span>
                <span style={{ opacity: 0.3 }}>|</span>
                <span style={{ color: result.summary.max_leverage_used > 1.0 ? 'var(--red)' : 'var(--gold)' }}>
                  Max Leverage: {result.summary.max_leverage_used}x
                </span>
                <span style={{ opacity: 0.3 }}>|</span>
                <span style={{ color: 'var(--gold)' }}>
                  {result.summary.trades_filtered || 0} trades filtered
                </span>
              </div>
            </div>
            {result.summary.total_return_pct < -result.config.circuit_breaker_dd * 0.9 && (
              <div style={{
                background: 'rgba(255,68,102,0.1)', border: '1px solid var(--red)',
                borderRadius: 8, padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 12
              }}>
                <span style={{ fontSize: 20 }}></span>
                <div style={{ fontFamily: 'var(--mono)' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--red)', textTransform: 'uppercase' }}>Circuit Breaker Active</div>
                  <div style={{ fontSize: 9, color: 'var(--ink2)' }}>Simulation halted to protect capital</div>
                </div>
              </div>
            )}
          </div>

          {/* Gate Quality Banner */}
          {gateStats && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
              {[
                { label: 'Gate Filter Rate', value: `${gateStats.filterRate}%`, sub: 'Trades blocked by 3-layer gate', color: 'var(--purple)' },
                { label: 'Avg Regime Confidence', value: `${gateStats.avgRegConf}%`, sub: 'Mean HMM confidence at entry', color: 'var(--blue)' },
                { label: 'Strong ICT Entries', value: gateStats.strongICT, sub: 'STRONG/VERY_STRONG signals', color: 'var(--green)' },
              ].map(({ label, value, sub, color }) => (
                <div key={label} className="card" style={{ padding: '14px 18px', background: 'var(--surface2)', borderLeft: `2px solid ${color}` }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>{label}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 800, color }}>{value}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginTop: 4 }}>{sub}</div>
                </div>
              ))}
            </div>
          )}

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
            {[
              { id: "overview",  label: "Overview"    },
              { id: "equity",    label: "Equity Curve" },
              { id: "trades",    label: "Trade Log"   },
              { id: "analytics", label: "Deep Analytics" },
              { id: "gate",      label: "Gate Analysis" },
            ].map(tab => {
              const active = activeTab === tab.id;
              return (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                  background: active ? 'var(--surface3)' : 'transparent',
                  border: `1px solid ${active ? 'var(--border3)' : 'transparent'}`,
                  borderRadius: 6, padding: '7px 16px',
                  fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 600 : 400,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  color: active ? 'var(--ink)' : 'var(--ink2)', cursor: 'pointer', transition: 'all .15s',
                }}>{tab.label}</button>
              );
            })}
          </div>

          {/* ── TAB: OVERVIEW ── */}
          {activeTab === "overview" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "12px" }}>
              {[
                { label: "Sharpe Ratio",     value: result.summary.sharpe_ratio.toFixed(3),  color: result.summary.sharpe_ratio >= 1 ? "var(--green)" : "var(--red)",   icon: "ALPHA", sub: "≥1.0 ideal · daily returns" },
                { label: "Sortino Ratio",    value: result.summary.sortino_ratio.toFixed(3), color: result.summary.sortino_ratio >= 1 ? "var(--green)" : "var(--red)",  icon: "RISK",  sub: "≥1.0 ideal · downside only" },
                { label: "Max Drawdown",     value: `${result.summary.max_drawdown_pct}%`,   color: result.summary.max_drawdown_pct > -15 ? "var(--green)" : "var(--red)", icon: "DD", sub: "< -15% dangerous" },
                { label: "Profit Factor",    value: result.summary.profit_factor.toFixed(3), color: result.summary.profit_factor >= 1.5 ? "var(--green)" : "var(--gold)", icon: "PF", sub: "≥1.5 ideal" },
                { label: "Win Rate",         value: `${result.summary.win_rate_pct}%`,        color: result.summary.win_rate_pct >= 50 ? "var(--green)" : "var(--red)",  icon: "HIT",  sub: "≥50% ideal" },
                { label: "Total Trades",     value: result.summary.total_trades,             color: "var(--ink)", icon: "QTY",  sub: `${result.summary.trades_filtered||0} filtered out` },
                { label: "Calmar Ratio",     value: result.summary.calmar_ratio.toFixed(3),  color: result.summary.calmar_ratio >= 0.5 ? "var(--green)" : "var(--gold)", icon: "CAL", sub: "≥0.5 ideal" },
                { label: "Expectancy/Trade", value: `$${Number(result.summary.expectancy_usd).toLocaleString("en-US", {minimumFractionDigits:0, maximumFractionDigits:0})}`, color: isProfit ? "var(--green)" : "var(--red)", icon: "EXP", sub: "avg per trade" },
                { label: "Max Leverage",     value: `${result.summary.max_leverage_used}x`, color: result.summary.max_leverage_used > 1.2 ? "var(--red)" : "var(--ink)", icon: "LEV", sub: "Cap: 1.0x (Institutional)" },
              ].map(({ label, value, color, icon, sub }) => (
                <MetricCard key={label} label={label} value={value} color={color} icon={icon} sublabel={sub} />
              ))}

              {/* Win/Loss Distribution */}
              <div className="card" style={{ gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px" }}>
                <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", letterSpacing: "0.15em", marginBottom: "16px", textTransform: 'uppercase' }}>
                  Trade Outcome Distribution
                </div>
                <WinLossBar wins={result.summary.winning_trades} losses={result.summary.losing_trades}
                  be={result.summary.total_trades - result.summary.winning_trades - result.summary.losing_trades} />
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: "14px", fontFamily: 'var(--mono)', fontSize: '10px' }}>
                  <span style={{ color: "var(--green)", fontWeight: 700 }}>WIN {result.summary.winning_trades} ({result.summary.win_rate_pct}%)</span>
                  <span style={{ color: "var(--ink2)" }}>B/E {result.summary.total_trades - result.summary.winning_trades - result.summary.losing_trades}</span>
                  <span style={{ color: "var(--red)", fontWeight: 700 }}>LOSS {result.summary.losing_trades}</span>
                </div>
              </div>

              {/* Best/Worst */}
              {[{ label: "Top Performance", trade: result.best_trade, accent: "var(--green)" },
                { label: "Worst Trade", trade: result.worst_trade, accent: "var(--red)" }
              ].map(({ label, trade, accent }) => trade && (
                <div key={label} className="card" style={{ background: 'var(--surface2)', border: `1px solid ${accent}22`, padding: "20px" }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", letterSpacing: "0.15em", marginBottom: "12px", textTransform: 'uppercase' }}>{label}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "18px", fontWeight: 800, color: 'var(--ink)' }}>{trade.ticker}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color: accent, marginTop: "6px" }}>
                    {trade.pnl_usd >= 0 ? "+" : ""}${trade.pnl_usd.toLocaleString(undefined, {minimumFractionDigits: 2})}
                    <span style={{ fontSize: '10px', marginLeft: 8, opacity: 0.8 }}>
                      ({trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%)
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "8px", color: "var(--ink2)", marginTop: "8px", textTransform: 'uppercase', letterSpacing: '0.05em', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span>{trade.direction}</span>
                    <span>·</span>
                    <IctBadge strength={trade.ict_strength} />
                    <span>·</span>
                    <span>{trade.entry_date} → {trade.exit_date}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── TAB: EQUITY CURVE ── */}
          {activeTab === "equity" && (
            <div className="card" style={{ background: 'var(--surface2)', padding: "32px" }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink4)", letterSpacing: "0.15em", marginBottom: "28px", textTransform: 'uppercase' }}>
                Daily Equity Progression (1 Year · Interpolated)
              </div>
              <EquityCurveChart data={result.equity_curve} initialBalance={result.config.initial_balance} />
              <div style={{ display: "flex", gap: "32px", marginTop: "28px", justifyContent: "center", fontFamily: 'var(--mono)', fontSize: '10px' }}>
                <div style={{ color: "var(--ink)", display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "24px", height: "2px", background: isProfit ? "var(--green)" : "var(--red)" }} />
                  Portfolio Value
                </div>
                <div style={{ color: "var(--ink2)", display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{ width: "24px", height: "1px", borderTop: "1px dashed var(--border3)" }} />
                  Baseline (${result.config.initial_balance.toLocaleString()})
                </div>
              </div>
            </div>
          )}

          {/* ── TAB: TRADE LOG ── */}
          {activeTab === "trades" && (
            <div className="anim">
              <div style={{ display: "flex", gap: "6px", marginBottom: "16px", flexWrap: "wrap" }}>
                {["ALL", "WIN", "LOSS", "BE"].map(f => {
                  const active = tradeFilter === f;
                  const count  = f === "ALL" ? result.trades.length : result.trades.filter(t => t.outcome === f).length;
                  return (
                    <button key={f} onClick={() => setTradeFilter(f)} style={{
                      background: active ? 'var(--surface3)' : 'transparent',
                      border: `1px solid ${active ? 'var(--border3)' : 'var(--border)'}`,
                      borderRadius: 6, padding: '6px 16px',
                      fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 600 : 400,
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                      color: active ? 'var(--ink)' : 'var(--ink2)', cursor: 'pointer',
                    }}>
                      {f} <span style={{ opacity: 0.5, marginLeft: 4 }}>[{count}]</span>
                    </button>
                  );
                })}
              </div>
              <div className="card" style={{ overflow: "hidden" }}>
                <div style={{
                  display: "grid", gridTemplateColumns: "36px 80px 50px 50px 60px 60px 70px 80px 70px 70px 60px 1fr",
                  alignItems: 'center', gap: 10, padding: "12px 16px",
                  background: "var(--surface2)", borderBottom: "1px solid var(--border)",
                }}>
                  <ColHead>#</ColHead><ColHead>TICKER</ColHead><ColHead>SIDE</ColHead>
                  <ColHead>SCORE</ColHead><ColHead>ENTRY</ColHead><ColHead>EXIT</ColHead>
                  <ColHead style={{ textAlign:'right' }}>P&L</ColHead>
                  <ColHead style={{ textAlign:'right' }}>BALANCE</ColHead>
                  <ColHead>REGIME</ColHead><ColHead>ICT</ColHead>
                  <ColHead>TECH</ColHead><ColHead>Q / TP</ColHead>
                </div>
                <div style={{ maxHeight: "500px", overflowY: "auto" }}>
                  {filteredTrades.slice().reverse().map((t, i) => {
                    const isWin  = t.outcome === "WIN";
                    const isLoss = t.outcome === "LOSS";
                    const pnlColor = isWin ? "var(--green)" : isLoss ? "var(--red)" : "var(--gold)";
                    const techFlags = [
                      t.tech_ema_aligned ? "EMA" : null,
                      t.tech_rsi_ok      ? "RSI" : null,
                      t.tech_vol_ok      ? "VOL" : null,
                      t.tech_adx_trend   ? "ADX" : null,
                    ].filter(Boolean);
                    return (
                      <div key={t.trade_id} style={{
                        display: "grid", gridTemplateColumns: "36px 80px 50px 50px 60px 60px 70px 80px 70px 70px 60px 1fr",
                        alignItems: "center", gap: 10, padding: "11px 16px",
                        borderBottom: "1px solid var(--border)",
                        background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                      }}>
                        <span style={{ fontFamily: 'var(--mono)', color: "var(--ink2)", fontSize: 9 }}>#{t.trade_id}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>{t.ticker}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700,
                          color: t.direction === "LONG" ? "var(--blue)" : "var(--amber)" }}>{t.direction}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10,
                          color: (t.screener_score || 0) >= 80 ? "var(--green)" : "var(--gold)" }}>{t.screener_score ?? "?"}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: "var(--ink)" }}>{t.entry_date?.slice(5)}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: "var(--ink)" }}>{t.exit_date?.slice(5)}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: pnlColor, fontWeight: 700, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                          {t.pnl_usd >= 0 ? "+" : ""}${t.pnl_usd.toLocaleString(undefined, {minimumFractionDigits: 2})}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: "var(--ink)", textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                          ${t.balance_after?.toLocaleString(undefined, {maximumFractionDigits: 0})}
                        </span>
                        <div><RegimeBadge regime={t.regime} /></div>
                        <div><IctBadge strength={t.ict_strength} /></div>
                        {/* Tech flags */}
                        <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                          {["EMA","RSI","VOL","ADX"].map(flag => {
                            const active = techFlags.includes(flag);
                            return (
                              <span key={flag} style={{
                                fontFamily: 'var(--mono)', fontSize: 6, fontWeight: 700,
                                color: active ? '#000' : 'var(--ink3)',
                                background: active ? 'var(--gold)' : 'transparent',
                                border: `1px solid ${active ? 'transparent' : 'var(--border)'}`,
                                padding: '1px 3px', borderRadius: 2,
                              }}>{flag}</span>
                            );
                          })}
                        </div>
                        {/* Quality + TP mult */}
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)' }}>
                          <span style={{ color: (t.quality_score||0) >= 80 ? 'var(--green)' : (t.quality_score||0) >= 60 ? 'var(--gold)' : 'var(--red)', fontWeight: 700 }}>
                            {t.quality_score?.toFixed(0) || '?'}
                          </span>
                          {t.tp_multiplier && t.tp_multiplier !== 1 ? <span style={{ color: 'var(--purple)', marginLeft: 4 }}>×{t.tp_multiplier}TP</span> : ''}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── TAB: ANALYTICS ── */}
          {activeTab === "analytics" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
              {/* Risk/Reward */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>Risk / Reward Metrics</SectionTitle>
                {[
                  { label: "Average Win",     value: `+${result.summary.avg_win_pct}%`,    color: "var(--green)" },
                  { label: "Average Loss",    value: `${result.summary.avg_loss_pct}%`,    color: "var(--red)" },
                  { label: "Win Rate",        value: `${result.summary.win_rate_pct}%`,    color: "var(--blue)" },
                  { label: "Profit Factor",   value: result.summary.profit_factor.toFixed(3), color: result.summary.profit_factor > 1.5 ? "var(--green)" : "var(--gold)" },
                  { label: "Expectancy/Trade",value: `$${Number(result.summary.expectancy_usd).toLocaleString("en-US", {minimumFractionDigits:0, maximumFractionDigits:0})}`, color: isProfit ? "var(--green)" : "var(--red)" },
                  { label: "Kelly Avg Frac",  value: `${(result.summary.kelly_avg_fraction*100).toFixed(1)}%K`, color: "var(--gold)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "11px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "10px", color: "var(--ink2)", textTransform: 'uppercase' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color }}>{value}</span>
                  </div>
                ))}
              </div>

              {/* Stability */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>Portfolio Stability</SectionTitle>
                {[
                  { label: "Max Drawdown",  value: `${result.summary.max_drawdown_pct}%`,     color: result.summary.max_drawdown_pct > -15 ? "var(--green)" : "var(--red)" },
                  { label: "Sharpe Ratio",  value: result.summary.sharpe_ratio.toFixed(3),    color: result.summary.sharpe_ratio >= 1 ? "var(--green)" : "var(--gold)" },
                  { label: "Sortino Ratio", value: result.summary.sortino_ratio.toFixed(3),   color: result.summary.sortino_ratio >= 1 ? "var(--green)" : "var(--gold)" },
                  { label: "Calmar Ratio",  value: result.summary.calmar_ratio.toFixed(3),    color: result.summary.calmar_ratio >= 0.5 ? "var(--green)" : "var(--gold)" },
                  { label: "Total Return",  value: `${result.summary.total_return_pct >= 0 ? "+" : ""}${result.summary.total_return_pct}%`, color: isProfit ? "var(--green)" : "var(--red)" },
                  { label: "Trades Blocked",value: `${result.summary.trades_filtered || 0}`,  color: "var(--purple)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "11px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "10px", color: "var(--ink2)", textTransform: 'uppercase' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color }}>{value}</span>
                  </div>
                ))}
              </div>

              {/* Dynamic TP Attribution */}
              <div className="card" style={{ gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>Dynamic TP Multiplier Attribution</SectionTitle>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {[1.5, 1.0].map(mult => {
                    const label = mult === 1.5 ? "3R — Strong Trend" : "2R — Normal / Default";
                    const emoji = mult === 1.5 ? "" : "";
                    const trades = result.trades.filter(t => Math.abs((t.tp_multiplier||1.0) - mult) < 0.05);
                    if (!trades.length) return (
                      <div key={mult} style={{ flex: 1, minWidth: 140, padding: '16px', background: 'var(--surface3)', borderRadius: 8, borderLeft: `3px solid var(--border)`, opacity: 0.5 }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase' }}>{emoji} {label}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 800, color: 'var(--ink2)', marginTop: 8 }}>0</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', marginTop: 4 }}>No trades — needs ADX≥25 + EMA aligned + momentum</div>
                      </div>
                    );
                    const wr  = (trades.filter(t=>t.outcome==="WIN").length/trades.length*100).toFixed(0);
                    const pnl = trades.reduce((a,t)=>a+t.pnl_usd,0);
                    const col = mult === 1.5 ? 'var(--green)' : 'var(--gold)';
                    return (
                      <div key={mult} style={{ flex: 1, minWidth: 140, padding: '16px', background: 'var(--surface3)', borderRadius: 8, borderLeft: `3px solid ${col}` }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: col, fontWeight: 700, textTransform: 'uppercase', marginBottom: 8 }}>{emoji} {label}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 26, fontWeight: 800, color: 'var(--ink)' }}>{trades.length}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginTop: 2 }}>trades</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10 }}>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: +wr>=50?'var(--green)':'var(--red)', fontWeight: 700 }}>{wr}% WR</span>
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: pnl>=0?'var(--green)':'var(--red)' }}>{pnl>=0?'+':''}${Number(pnl).toLocaleString("en-US",{maximumFractionDigits:0})}</span>
                        </div>
                        {mult === 1.5 && (
                          <div style={{ fontFamily:'var(--mono)', fontSize:7, color:'var(--ink3)', marginTop:6, lineHeight:1.4 }}>
                            Aktif: ADX≥25 + EMA aligned + momentum
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Regime Attribution */}
              <div className="card" style={{ gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>Performance Attribution by Market Regime</SectionTitle>
                {["LOW_VOL_BULLISH", "SIDEWAYS_CHOP", "HIGH_VOL_BEARISH"].map(regime => {
                  const rTrades = result.trades.filter(t => t.regime === regime);
                  if (!rTrades.length) return null;
                  const rWins = rTrades.filter(t => t.outcome === "WIN").length;
                  const rPnl  = rTrades.reduce((s, t) => s + t.pnl_usd, 0);
                  const wr    = (rWins / rTrades.length * 100).toFixed(0);
                  const avgConf = (rTrades.reduce((s,t) => s + (t.regime_conf||0), 0) / rTrades.length).toFixed(1);
                  return (
                    <div key={regime} style={{ display: "flex", alignItems: "center", gap: "20px", padding: "14px 0", borderBottom: "1px solid var(--border)" }}>
                      <RegimeBadge regime={regime} />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", gap: "3px", flexWrap: 'wrap' }}>
                          {rTrades.map((t, i) => (
                            <div key={i} style={{ width: "6px", height: "12px", borderRadius: "1px",
                              background: t.outcome === "WIN" ? "var(--green)" : t.outcome === "LOSS" ? "var(--red)" : "var(--ink4)",
                              opacity: 0.85 }} />
                          ))}
                        </div>
                      </div>
                      <div style={{ textAlign: "right", fontFamily: 'var(--mono)' }}>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: rPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                          {rPnl >= 0 ? "+" : ""}${rPnl.toLocaleString(undefined, {minimumFractionDigits:2})}
                        </div>
                        <div style={{ fontSize: "8px", color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>
                          {rTrades.length} trades · {wr}% WR · Avg conf {avgConf}%
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── TAB: GATE ANALYSIS ── */}
          {activeTab === "gate" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>

              {/* Quality Score Distribution */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px", gridColumn: "1 / -1" }}>
                <SectionTitle>Quality Score Distribution — Soft Gate System</SectionTitle>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', marginBottom: 16, lineHeight: 1.6 }}>
                  Setiap trade mendapat composite quality score (0-100). Score rendah = posisi kecil, bukan diblok.
                  Hanya HIGH_VOL_BEARISH yang diblok sepenuhnya.
                </p>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                  {[
                    { min: 90, max: 101, label: "A+ (90-100)", color: 'var(--green)', scale: "×1.00" },
                    { min: 70, max: 90,  label: "A  (70-89)",  color: '#22d3ee',       scale: "×0.75" },
                    { min: 50, max: 70,  label: "B  (50-69)",  color: 'var(--gold)',   scale: "×0.55" },
                    { min: 30, max: 50,  label: "C  (30-49)",  color: 'var(--amber)',  scale: "×0.35" },
                    { min: 0,  max: 30,  label: "D  (<30)",    color: 'var(--red)',    scale: "×0.20" },
                  ].map(({ min, max, label, color, scale }) => {
                    const bucket = result.trades.filter(t => (t.quality_score || 0) >= min && (t.quality_score || 0) < max);
                    const wins   = bucket.filter(t => t.outcome === "WIN").length;
                    const wr     = bucket.length ? (wins/bucket.length*100).toFixed(0) : 0;
                    const pnl    = bucket.reduce((a,t) => a + t.pnl_usd, 0);
                    return (
                      <div key={label} style={{ flex: 1, minWidth: 110, padding: '14px 16px', background: 'var(--surface3)', borderRadius: 8, borderTop: `3px solid ${color}` }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color, marginBottom: 8 }}>Size {scale}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 20, fontWeight: 800, color }}>{bucket.length}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginTop: 2 }}>trades</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: +wr >= 50 ? 'var(--green)' : 'var(--red)', marginTop: 6, fontWeight: 600 }}>{wr}% WR</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: pnl>=0?'var(--green)':'var(--red)', marginTop: 2 }}>
                          {pnl>=0?'+':''}${pnl.toFixed(0)}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Quality score timeline */}
                <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Quality Score per Trade (chronological)
                </div>
                <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'flex-end', height: 60 }}>
                  {result.trades.map((t, i) => {
                    const q = t.quality_score || 50;
                    const h = Math.max(8, (q / 100) * 56);
                    const c = t.outcome === "WIN" ? 'var(--green)' : t.outcome === "LOSS" ? 'var(--red)' : 'var(--gold)';
                    return (
                      <div key={i} title={`#${t.trade_id} ${t.ticker} Q:${q}`}
                        style={{ width: 6, height: h, background: c, opacity: 0.8, borderRadius: 2, flexShrink: 0 }} />
                    );
                  })}
                </div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink3)', marginTop: 4 }}>
                  Bar height = quality score. Green=WIN Red=LOSS Yellow=BE
                </div>
              </div>

              {/* Tech Confirmation Stats */}
              <div className="card" style={{ gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>v3 Technical Confirmation — Win Rate Impact</SectionTitle>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', marginBottom: 16, lineHeight: 1.6 }}>
                  Apakah konfirmasi teknikal benar-benar meningkatkan win rate? Data dari seluruh trade.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                  {[
                    { key: "tech_ema_aligned", label: "EMA Aligned", desc: "Price > EMA20 > EMA50 (bull) atau sebaliknya (bear)" },
                    { key: "tech_rsi_ok",      label: "RSI Optimal", desc: "RSI 35-72 (long) atau 28-65 (short)" },
                    { key: "tech_vol_ok",      label: "Vol Confirmed", desc: "Volume ≥ 0.9× 20-day average" },
                    { key: "tech_adx_trend",   label: "ADX Trending", desc: "ADX ≥ 20 (trending market)" },
                  ].map(({ key, label, desc }) => {
                    const withFlag    = result.trades.filter(t => t[key]);
                    const withoutFlag = result.trades.filter(t => !t[key]);
                    const wrWith    = withFlag.length    ? (withFlag.filter(t=>t.outcome==="WIN").length/withFlag.length*100)    : 0;
                    const wrWithout = withoutFlag.length ? (withoutFlag.filter(t=>t.outcome==="WIN").length/withoutFlag.length*100) : 0;
                    const pnlWith    = withFlag.reduce((a,t)=>a+t.pnl_usd,0);
                    const pnlWithout = withoutFlag.reduce((a,t)=>a+t.pnl_usd,0);
                    const impact = wrWith - wrWithout;
                    const color  = impact > 0 ? 'var(--green)' : impact < -2 ? 'var(--red)' : 'var(--gold)';
                    return (
                      <div key={key} style={{ padding: '16px', background: 'var(--surface3)', borderRadius: 8, borderTop: `3px solid ${color}` }}>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color: 'var(--ink)', marginBottom: 4, textTransform: 'uppercase' }}>{label}</div>
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink2)', marginBottom: 12, lineHeight: 1.5 }}>{desc}</div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                          <div>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginBottom: 2 }}>WITH flag ({withFlag.length})</div>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 800, color: wrWith >= 50 ? 'var(--green)' : 'var(--red)' }}>{wrWith.toFixed(0)}%</div>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: pnlWith>=0?'var(--green)':'var(--red)' }}>{pnlWith>=0?'+':''}${pnlWith.toFixed(0)}</div>
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', marginBottom: 2 }}>WITHOUT ({withoutFlag.length})</div>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 16, fontWeight: 800, color: wrWithout >= 50 ? 'var(--green)' : 'var(--red)' }}>{wrWithout.toFixed(0)}%</div>
                            <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: pnlWithout>=0?'var(--green)':'var(--red)' }}>{pnlWithout>=0?'+':''}${pnlWithout.toFixed(0)}</div>
                          </div>
                        </div>
                        <div style={{ textAlign: 'center', fontFamily: 'var(--mono)', fontSize: 10, color, fontWeight: 700 }}>
                          {impact >= 0 ? '+' : ''}{impact.toFixed(1)}% impact
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>ICT Strength Impact</SectionTitle>
                {["VERY_STRONG","STRONG","MODERATE","WEAK","VERY_WEAK"].map(s => {
                  const trades = result.trades.filter(t => t.ict_strength === s);
                  if (!trades.length) return null;
                  const wins = trades.filter(t => t.outcome === "WIN").length;
                  const wr   = (wins/trades.length*100).toFixed(0);
                  const pnl  = trades.reduce((a,t) => a + t.pnl_usd, 0);
                  const colors = { VERY_STRONG: 'var(--green)', STRONG: 'var(--green)', MODERATE: 'var(--gold)', WEAK: 'var(--red)', VERY_WEAK: 'var(--red)' };
                  return (
                    <div key={s} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <IctBadge strength={s} />
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>{trades.length} trades</span>
                      </div>
                      <div style={{ fontFamily: 'var(--mono)', fontSize: 10, textAlign: 'right' }}>
                        <div style={{ color: colors[s], fontWeight: 700 }}>{wr}% WR</div>
                        <div style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', fontSize: 9 }}>
                          {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Screener Score vs Win Rate buckets */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                <SectionTitle>Screener Score → Win Rate</SectionTitle>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {[
                    { min: 90, max: 100, label: "90-100" },
                    { min: 80, max: 90,  label: "80-90" },
                    { min: 70, max: 80,  label: "70-80" },
                    { min: 60, max: 70,  label: "60-70" },
                    { min: 0,  max: 60,  label: "<60" },
                  ].map(({ min, max, label }) => {
                    const bucket = result.trades.filter(t => t.screener_score >= min && t.screener_score < max);
                    if (!bucket.length) return null;
                    const wr   = (bucket.filter(t=>t.outcome==="WIN").length/bucket.length*100);
                    const color = wr >= 60 ? 'var(--green)' : wr >= 45 ? 'var(--gold)' : 'var(--red)';
                    return (
                      <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', width: 50, flexShrink: 0 }}>Score {label}</span>
                        <div style={{ flex: 1, height: 14, background: 'var(--surface3)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${wr}%`, height: '100%', background: color, borderRadius: 3 }} />
                        </div>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700, color, width: 36, textAlign: 'right' }}>{wr.toFixed(0)}%</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', width: 48 }}>{bucket.length} trades</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

          )}
        </div>
      )}

      <style>{`
        .spin-icon { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.4; transform: scale(0.7); }
        }
        @keyframes blink-cursor {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0; }
        }
        @keyframes slide-in-log {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}