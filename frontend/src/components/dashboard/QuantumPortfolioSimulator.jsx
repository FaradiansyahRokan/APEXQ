import { useState, useEffect, useRef } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

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

// ─── Mini Sparkline SVG component ──────────────────────────────
function Sparkline({ data, color = "var(--green)", width = 120, height = 40 }) {
  if (!data || data.length < 2) return null;
  const vals = data.map(d => d.balance);
  const min = Math.min(...vals), max = Math.max(...vals);
  const range = max - min || 1;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");
  const last = vals[vals.length-1];
  const isUp = last >= vals[0];
  const lineColor = isUp ? "var(--green)" : "var(--red)";
  return (
    <svg width={width} height={height} style={{overflow:"visible"}}>
      <defs>
        <linearGradient id="spkGrad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={lineColor} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <polyline points={pts} fill="none" stroke={`var(--${isUp ? "green" : "red"})`} strokeWidth="1.5" />
    </svg>
  );
}

// ─── Equity Curve Chart (Recharts) ───────────────────────────
function EquityCurveChart({ data, initialBalance }) {
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!data?.length || !isMounted) return <div style={{ height: 340 }} />;

  // Format data for Recharts
  const chartData = data.map(d => ({
    ...d,
    time: d.time,
    balance: d.balance,
  }));

  const isProfit = chartData[chartData.length - 1].balance >= initialBalance;
  const accentColor = isProfit ? "#10b981" : "#f43f5e";

  const balances = chartData.map(d => d.balance);
  const minBal = Math.min(...balances, initialBalance);
  const maxBal = Math.max(...balances, initialBalance);
  const range = maxBal - minBal || 1;
  const buffer = range * 0.15;

  console.log("EquityCurveChart Render - Data Points:", chartData.length);

  return (
    <div 
      className="recharts-wrapper"
      style={{ 
        width: '100%', 
        height: 340, 
        minHeight: 340,
        minWidth: 0,
        marginTop: 10,
        position: 'relative',
        display: 'block'
      }}
    >
      <ResponsiveContainer width="99%" height="100%" debounce={50}>
        <AreaChart 
          data={chartData} 
          margin={{ top: 10, right: 30, left: -20, bottom: 10 }}
        >
          <defs>
            <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={accentColor} stopOpacity={0.3}/>
              <stop offset="95%" stopColor={accentColor} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid 
            strokeDasharray="3 3" 
            vertical={false} 
            stroke="rgba(255,255,255,0.05)" 
          />
          <XAxis 
            dataKey="time" 
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'var(--mono)' }}
            minTickGap={60}
            tickFormatter={(val) => {
              const d = new Date(val);
              return `${d.getDate()} ${d.toLocaleString('en-US', { month: 'short' })}`;
            }}
          />
          <YAxis 
            axisLine={false}
            tickLine={false}
            tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'var(--mono)' }}
            domain={[minBal - buffer, maxBal + buffer]}
            tickFormatter={(val) => `$${val.toLocaleString()}`}
            orientation="right"
          />
          <Tooltip 
            contentStyle={{ 
              background: '#1e293b', 
              border: '1px solid #334155',
              borderRadius: '8px',
              fontSize: '11px',
              fontFamily: 'var(--mono)',
              color: '#f8fafc'
            }}
            itemStyle={{ color: accentColor, fontWeight: 700 }}
            labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
            formatter={(value) => [`$${value.toLocaleString()}`, "Equity"]}
            labelFormatter={(label) => `Date: ${label}`}
          />
          <ReferenceLine 
            y={initialBalance} 
            stroke="#475569" 
            strokeDasharray="4 4" 
            label={{ 
              value: 'Initial Balance', 
              position: 'insideBottomRight', 
              fill: '#475569', 
              fontSize: 9, 
              fontFamily: 'var(--mono)',
              offset: 10
            }} 
          />
          <Area 
            type="monotone" 
            dataKey="balance" 
            stroke={accentColor} 
            strokeWidth={3}
            fillOpacity={1} 
            fill="url(#colorBalance)" 
            animationDuration={800}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Win/Loss Distribution Bar ──────────────────────────────────
function WinLossBar({ wins, losses, be }) {
  const total = wins + losses + be;
  if (total === 0) return null;
  const wp = (wins/total*100).toFixed(1);
  const lp = (losses/total*100).toFixed(1);
  const bp = (be/total*100).toFixed(1);
  return (
    <div style={{ width: "100%", height: "4px", borderRadius: "4px", overflow: "hidden", display: "flex", gap: "2px", background: 'var(--surface3)' }}>
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
  const cfg = map[regime] || { cls: "badge-muted", label: regime };
  return <span className={`badge ${cfg.cls}`} style={{ fontSize: 9 }}>{cfg.label}</span>;
}

// ══════════════════════════════════════════════════════════════════
//  MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════

export default function QuantumPortfolioSimulator() {
  const [config, setConfig]   = useState({
    initial_balance: 100,
    risk_per_trade  : 2,
    scan_universe   : "US",
    tp_rr_ratio     : 2,
    min_screener_score: 65,
  });
  const [result, setResult]         = useState(null);
  const [isRunning, setIsRunning]   = useState(false);
  const [progress, setProgress]     = useState(0);
  const [activeTab, setActiveTab]   = useState("overview");
  const [tradeFilter, setTradeFilter] = useState("ALL");
  const [animKey, setAnimKey]       = useState(0);
  const progressRef = useRef(null);

  const runSim = async () => {
    setIsRunning(true);
    setProgress(0);
    setResult(null);
    setAnimKey(k => k + 1);

    // Simulate progress animation
    let p = 0;
    progressRef.current = setInterval(() => {
      p += Math.random() * 8 + 3;
      if (p >= 95) { clearInterval(progressRef.current); p = 95; }
      setProgress(Math.min(p, 95));
    }, 80);

    try {
      const response = await fetch("http://localhost:8001/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      });
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Simulation failed");
      }
      
      const res = await response.json();
      
      clearInterval(progressRef.current);
      setProgress(100);
      setResult(res);
    } catch (error) {
      console.error("Simulation Error:", error);
      clearInterval(progressRef.current);
      alert("Simulation Error: " + error.message);
    } finally {
      setIsRunning(false);
      setProgress(0);
    }
  };

  const isProfit = result && result.summary.final_balance >= config.initial_balance;

  const filteredTrades = result?.trades?.filter(t => 
    tradeFilter === "ALL" ? true : t.outcome === tradeFilter
  ) || [];

  return (
    <div style={{ paddingTop: 40, paddingBottom: 96 }}>
      
      {/* ── PAGE HEADER ── */}
      <div className="anim" style={{ marginBottom: 40 }}>
        <p style={{
          fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 12,
        }}>
          Time Machine · Portfolio Backtest Engine
        </p>
        <h1 style={{
          fontSize: 38, fontWeight: 800, letterSpacing: '-0.03em',
          color: 'var(--ink)', lineHeight: 1.1, marginBottom: 14,
        }}>
          Quantum Portfolio Simulator
        </h1>
        <p style={{
          fontSize: 14, color: 'var(--ink)', lineHeight: 1.7, maxWidth: 660,
        }}>
          Simulasi 1 tahun perjalanan trading menggunakan pipeline kuantitatif lengkap:
          Screener, Regime Filter, ICT Entry, dan Kelly Position Sizing.
        </p>
      </div>

      {/* ── CONTROLS PANEL ── */}
      <div className="anim d1 card" style={{ padding: 24, marginBottom: 32 }}>
        
        {/* Top Controls Row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 24 }}>
          {/* Market filter tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            {["US", "IDX", "CRYPTO", "UNIVERSAL"].map(u => {
              const active = config.scan_universe === u;
              return (
                <button key={u} onClick={() => setConfig(c => ({...c, scan_universe: u}))}
                  style={{
                    background: active ? 'var(--gold)' : 'var(--surface3)',
                    border: `1px solid ${active ? 'transparent' : 'var(--border)'}`,
                    borderRadius: 6, padding: '7px 18px',
                    fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 700 : 400,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: active ? '#000' : 'var(--ink2)',
                    transition: 'all .15s', cursor: 'pointer',
                  }}>
                  {u === 'US' ? 'US Markets' : u === 'IDX' ? 'IDX (Indo)' : u === 'UNIVERSAL' ? 'Universal All' : u}
                </button>
              );
            })}
          </div>

          {/* Run button */}
          <button
            onClick={runSim}
            disabled={isRunning}
            style={{
              background: isRunning ? 'var(--surface3)' : 'var(--gold)',
              border: 'none', color: isRunning ? 'var(--ink3)' : '#000',
              padding: '9px 28px', borderRadius: 8,
              fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)',
              letterSpacing: '0.06em', textTransform: 'uppercase',
              display: 'flex', alignItems: 'center', gap: 10,
              opacity: isRunning ? 0.7 : 1,
              transition: 'all .2s', cursor: isRunning ? 'not-allowed' : 'pointer',
            }}
          >
            {isRunning ? <><Spinner size={13} /> Simulating…</> : '⬡ Run Simulation'}
          </button>
        </div>

        {/* Configuration Inputs */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "16px" }}>
          {[
            { key: "initial_balance", label: "Initial Capital", min: 10, max: 1000000, step: 100, prefix: "$" },
            { key: "risk_per_trade",   label: "Risk per Trade", min: 0.1, max: 10, step: 0.1, suffix: "%" },
            { key: "tp_rr_ratio",          label: "RR Ratio (Reward:Risk)", min: 1, max: 10, step: 0.5, suffix: ":1" },
            { key: "min_screener_score",      label: "Min Screener Score", min: 30, max: 95, step: 5 },
          ].map(({ key, label, prefix, suffix }) => (
            <div key={key}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink2)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>{label}</div>
              <div style={{
                display: 'flex', alignItems: 'center',
                background: 'var(--surface3)', border: '1px solid var(--border2)',
                borderRadius: 8, overflow: 'hidden', height: 36
              }}>
                {prefix && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingLeft: 14 }}>{prefix}</span>}
                <input
                  type="number"
                  value={config[key]}
                  onChange={e => setConfig(c => ({ ...c, [key]: +e.target.value }))}
                  style={{
                    flex: 1, background: 'none', border: 'none',
                    fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
                    color: 'var(--ink)', padding: '0 14px', textAlign: prefix ? 'left' : 'center',
                    outline: 'none', WebkitAppearance: 'none', margin: 0, width: '100%'
                  }}
                />
                {suffix && <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', paddingRight: 14 }}>{suffix}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── LOADING STATE ── */}
      {isRunning && (
        <div className="anim card" style={{ padding: 56, textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
            <div style={{ position: 'relative', width: 52, height: 52 }}>
              <div style={{
                width: 52, height: 52,
                border: '2px solid var(--border2)',
                borderTopColor: 'var(--gold)',
                borderRadius: '50%',
              }} className="spin-icon" />
              <div style={{
                position: 'absolute', inset: 10,
                border: '1.5px solid var(--border)',
                borderTopColor: 'var(--green)',
                borderRadius: '50%',
                animationDuration: '0.5s',
              }} className="spin-icon" />
            </div>
            <div>
              <p style={{
                fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink2)',
                letterSpacing: '0.08em', marginBottom: 12,
              }}>
                Simulating Portfolio… {progress.toFixed(0)}%
              </p>
              <div style={{ width: 240, height: 4, background: 'var(--surface3)', borderRadius: 2, margin: '0 auto', overflow: 'hidden' }}>
                  <div style={{ width: `${progress}%`, height: '100%', background: 'var(--gold)', transition: 'width 0.1s' }} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── RESULTS ── */}
      {result && !isRunning && (
        <div key={animKey} className="anim d2">
          
          {/* Headline Card */}
          <div className="card" style={{
            background: isProfit ? 'rgba(0,255,136,0.03)' : 'rgba(255,68,102,0.03)',
            border: `1px solid ${isProfit ? 'var(--green)' : 'var(--red)'}44`,
            padding: "32px", marginBottom: "24px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexWrap: "wrap", gap: "24px", position: 'relative', overflow: 'hidden'
          }}>
            {/* Profit/Loss Glow */}
            <div style={{
              position: 'absolute', top: -50, right: -50, width: 200, height: 200,
              background: isProfit ? 'var(--green)' : 'var(--red)',
              filter: 'blur(100px)', opacity: 0.1, pointerEvents: 'none'
            }} />

            <div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)', letterSpacing: "0.2em", marginBottom: "12px", textTransform: 'uppercase' }}>
                Portfolio Final Value · {result.config.scan_universe} Universe
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: "20px" }}>
                <div style={{
                  fontSize: "48px", fontWeight: 900, letterSpacing: "-0.04em",
                  color: isProfit ? "var(--green)" : "var(--red)",
                  fontVariantNumeric: 'tabular-nums'
                }}>
                  ${result.summary.final_balance.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                </div>
                <div style={{
                  fontSize: "18px", fontWeight: 700, fontFamily: 'var(--mono)',
                  color: isProfit ? "var(--green)" : "var(--red)",
                  padding: "6px 14px",
                  background: isProfit ? "rgba(0,255,136,0.1)" : "rgba(255,68,102,0.1)",
                  borderRadius: "8px", border: '1px solid currentColor'
                }}>
                  {result.summary.total_return_pct >= 0 ? "+" : ""}{result.summary.total_return_pct}%
                </div>
              </div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: "11px", color: 'var(--ink)', marginTop: "12px" }}>
                Initial: ${result.config.initial_balance.toLocaleString()} 
                <span style={{ margin: '0 10px', opacity: 0.3 }}>|</span>
                Net: <span style={{ color: isProfit ? 'var(--green)' : 'var(--red)' }}>
                 {isProfit ? "+" : "-"}${Math.abs(result.summary.final_balance - result.config.initial_balance).toLocaleString(undefined, {minimumFractionDigits:2})}
                </span>
              </div>
            </div>
            <div style={{ flexShrink: 0 }}>
              {/* <Sparkline data={result.equity_curve} width={220} height={80} /> */}
            </div>
          </div>

          {/* Navigation Tabs (Match Screener style) */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
            {[
              { id: "overview", label: "Overview" },
              { id: "equity",   label: "Equity Curve" },
              { id: "trades",   label: "Trade Log" },
              { id: "analytics",label: "Deep Analytics" }
            ].map(tab => {
              const active = activeTab === tab.id;
              return (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                  background: active ? 'var(--surface3)' : 'transparent',
                  border: `1px solid ${active ? 'var(--border3)' : 'transparent'}`,
                  borderRadius: 6, padding: '7px 16px',
                  fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 600 : 400,
                  letterSpacing: '0.1em', textTransform: 'uppercase',
                  color: active ? 'var(--ink)' : 'var(--ink2)',
                  transition: 'all .15s', cursor: 'pointer',
                }}>
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* ── TAB: OVERVIEW ── */}
          {activeTab === "overview" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "12px" }}>
              {[
                { label: "Sharpe Ratio",     value: result.summary.sharpe_ratio, format: "num", threshold: 1, good: "≥ 1.0", icon: "ALPHA" },
                { label: "Sortino Ratio",    value: result.summary.sortino_ratio, format: "num", threshold: 1, good: "≥ 1.0", icon: "RISK" },
                { label: "Max Drawdown",     value: result.summary.max_drawdown_pct, format: "pct_neg", threshold: -20, good: "> -15%", icon: "DD", invert: true },
                { label: "Profit Factor",    value: result.summary.profit_factor, format: "num", threshold: 1.5, good: "≥ 1.5", icon: "PF" },
                { label: "Win Rate",         value: result.summary.win_rate_pct, format: "pct", threshold: 50, good: "≥ 50%", icon: "HIT" },
                { label: "Total Trades",     value: result.summary.total_trades, format: "int", icon: "QTY" },
                { label: "Calmar Ratio",     value: result.summary.calmar_ratio, format: "num", threshold: 0.5, good: "≥ 0.5", icon: "CAL" },
                { label: "Expectancy/Trade", value: result.summary.expectancy_usd, format: "usd", threshold: 0, icon: "EXP" },
              ].map(({ label, value, format, threshold, good, icon, invert }) => {
                const isGood = threshold !== undefined 
                  ? (invert ? value > threshold : value >= threshold)
                  : value > 0;
                const color = format === "int" || threshold === undefined ? "var(--ink)"
                  : isGood ? "var(--green)" : "var(--red)";
                const display = format === "num" ? value.toFixed(3)
                  : format === "pct" ? `${value}%`
                  : format === "pct_neg" ? `${value}%`
                  : format === "usd" ? `$${value.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
                  : value.toString();
                return (
                  <div key={label} className="card" style={{ padding: "20px", background: 'var(--surface2)' }}>
                      <div style={{ 
                        fontFamily: 'var(--mono)', fontSize: "8px", color: "var(--ink2)", 
                        letterSpacing: "0.15em", marginBottom: "12px", display: "flex", justifyContent: "space-between",
                        textTransform: 'uppercase'
                      }}>
                      <span>{label}</span>
                      <span style={{ color: 'var(--gold)' }}>[{icon}]</span>
                    </div>
                    <div style={{ 
                      fontSize: "28px", fontWeight: 800, color, letterSpacing: "-0.02em",
                      fontVariantNumeric: 'tabular-nums', fontFamily: 'var(--mono)'
                    }}>
                      {display}
                    </div>
                      {good && <div style={{ fontFamily: 'var(--mono)', fontSize: "7px", color: "var(--ink2)", marginTop: "8px", textTransform: 'uppercase', letterSpacing: '0.05em' }}>Ideal: {good}</div>}
                  </div>
                );
              })}
              
              {/* Win/Loss Distribution */}
              <div className="card" style={{
                gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px"
              }}>
                <div style={{ 
                  fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", 
                  letterSpacing: "0.15em", marginBottom: "20px", textTransform: 'uppercase'
                }}>
                  Trade Outcome Distribution
                </div>
                <WinLossBar wins={result.summary.winning_trades} losses={result.summary.losing_trades}
                  be={result.summary.total_trades - result.summary.winning_trades - result.summary.losing_trades} />
                
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: "16px", fontFamily: 'var(--mono)', fontSize: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--green)' }} />
                    <span style={{ color: "var(--green)", fontWeight: 700 }}>WIN: {result.summary.winning_trades} ({result.summary.win_rate_pct}%)</span>
                  </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ink2)' }} />
                      <span style={{ color: "var(--ink2)" }}>
                        B/E: {result.summary.total_trades - result.summary.winning_trades - result.summary.losing_trades}
                      </span>
                    </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red)' }} />
                    <span style={{ color: "var(--red)", fontWeight: 700 }}>
                      LOSS: {result.summary.losing_trades} ({(result.summary.losing_trades/result.summary.total_trades*100).toFixed(1)}%)
                    </span>
                  </div>
                </div>
              </div>

              {/* Best/Worst trade */}
              {[{ label: "Top Performance", trade: result.best_trade, accent: "var(--green)" },
                { label: "Maximum Drawdown Trade", trade: result.worst_trade, accent: "var(--red)" }
              ].map(({ label, trade, accent }) => trade && (
                <div key={label} className="card" style={{
                  background: 'var(--surface2)', border: `1px solid ${accent}22`,
                  padding: "20px"
                }}>
                  <div style={{ 
                    fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", 
                    letterSpacing: "0.15em", marginBottom: "12px", textTransform: 'uppercase'
                  }}>{label}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "18px", fontWeight: 800, color: 'var(--ink)' }}>{trade.ticker}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color: accent, marginTop: "6px" }}>
                    {trade.pnl_usd >= 0 ? "+" : ""}${trade.pnl_usd.toLocaleString(undefined, {minimumFractionDigits: 2})} 
                    <span style={{ fontSize: '11px', marginLeft: 8 }}>
                      ({trade.pnl_pct >= 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%)
                    </span>
                  </div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", marginTop: "10px", textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {trade.direction} · {trade.entry_date} → {trade.exit_date}
                    </div>
                </div>
              ))}
            </div>
          )}

          {/* ── TAB: EQUITY CURVE ── */}
          {activeTab === "equity" && (
            <div className="card" style={{ background: 'var(--surface2)', padding: "32px" }}>
              <div style={{ 
                fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink4)", 
                letterSpacing: "0.15em", marginBottom: "32px", textTransform: 'uppercase'
              }}>
                Portfolio Equity Progression (1 Year)
              </div>
              {/* UBAH DI BARIS BAWAH INI: result.equity_curve -> result.equityCurve */}
              <EquityCurveChart data={result.equity_curve} initialBalance={result.config.initial_balance} />
                <div style={{ display: "flex", gap: "32px", marginTop: "32px", justifyContent: "center", fontFamily: 'var(--mono)', fontSize: '10px' }}>
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
              <div style={{ display: "flex", gap: "6px", marginBottom: "20px", flexWrap: "wrap" }}>
                {["ALL", "WIN", "LOSS", "BE"].map(f => {
                  const active = tradeFilter === f;
                  const count = f === "ALL" ? result.trades.length : result.trades.filter(t=>t.outcome===f).length;
                  return (
                    <button key={f} onClick={() => setTradeFilter(f)}
                      style={{
                        background: active ? 'var(--surface3)' : 'transparent',
                        border: `1px solid ${active ? 'var(--border3)' : 'var(--border)'}`,
                        borderRadius: 6, padding: '6px 16px',
                        fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 600 : 400,
                        letterSpacing: '0.1em', textTransform: 'uppercase',
                          color: active ? 'var(--ink)' : 'var(--ink2)',
                          transition: 'all .15s', cursor: 'pointer',
                      }}>
                      {f} <span style={{ opacity: 0.5, marginLeft: 4 }}>[{count}]</span>
                    </button>
                  );
                })}
              </div>

              <div className="card" style={{ overflow: "hidden" }}>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "50px 100px 70px 70px 90px 90px 100px 100px 1fr",
                  alignItems: 'center', gap: 16,
                  padding: "12px 20px", background: "var(--surface2)",
                  borderBottom: "1px solid var(--border)",
                }}>
                  <ColHead>ID</ColHead>
                  <ColHead>TICKER</ColHead>
                  <ColHead>SIDE</ColHead>
                  <ColHead>SCORE</ColHead>
                  <ColHead>ENTRY</ColHead>
                  <ColHead>EXIT</ColHead>
                  <ColHead style={{ textAlign: 'right' }}>P&L</ColHead>
                  <ColHead style={{ textAlign: 'right' }}>BALANCE</ColHead>
                  <ColHead>REGIME</ColHead>
                </div>
                <div style={{ maxHeight: "480px", overflowY: "auto" }}>
                  {filteredTrades.slice().reverse().map((t, i) => {
                    const isWin = t.outcome === "WIN";
                    const isLoss = t.outcome === "LOSS";
                    const pnlColor = isWin ? "var(--green)" : isLoss ? "var(--red)" : "var(--gold)";
                    return (
                      <div key={t.trade_id} style={{
                        display: "grid",
                        gridTemplateColumns: "50px 100px 70px 70px 90px 90px 100px 100px 1fr",
                        alignItems: "center", gap: 16,
                        padding: "14px 20px",
                        borderBottom: "1px solid var(--border)",
                        background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
                        transition: 'background .15s ease',
                      }}>
                          <span style={{ fontFamily: 'var(--mono)', color: "var(--ink2)", fontSize: 10 }}>#{t.trade_id}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 700, color: 'var(--ink)' }}>{t.ticker}</span>
                        <span style={{ 
                          fontFamily: 'var(--mono)', fontSize: "9px", fontWeight: 700,
                          color: t.direction === "LONG" ? "var(--blue)" : "var(--amber)", 
                        }}>
                          {t.direction}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: (t.screener_score || 0) >= 75 ? "var(--green)" : "var(--gold)" }}>
                          {t.screener_score ?? "0"}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: "var(--ink)" }}>{t.entry_date.slice(5)}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: "var(--ink)" }}>{t.exit_date.slice(5)}</span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: pnlColor, fontWeight: 700, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                          {t.pnl_usd >= 0 ? "+" : ""}${t.pnl_usd.toLocaleString(undefined, {minimumFractionDigits: 2})}
                        </span>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: "var(--ink)", textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                          ${t.balance_after.toLocaleString(undefined, {maximumFractionDigits: 0})}
                        </span>
                        <div><RegimeBadge regime={t.regime} /></div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── TAB: ANALYTICS ── */}
          {activeTab === "analytics" && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
              {/* Risk/Reward */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink2)", letterSpacing: "0.15em", marginBottom: "24px", textTransform: 'uppercase' }}>
                    Risk/Reward Metrics
                  </div>
                {[
                  { label: "Average Win",   value: `+${result.summary.avg_win_pct}%`,   color: "var(--green)" },
                  { label: "Average Loss",  value: `${result.summary.avg_loss_pct}%`,    color: "var(--red)" },
                  { label: "Actual Win Rate",  value: `${result.summary.win_rate_pct}%`,    color: "var(--blue)" },
                  { label: "Profit Factor", value: result.summary.profit_factor.toFixed(3), color: result.summary.profit_factor > 1.5 ? "var(--green)" : "var(--gold)" },
                  { label: "Expectancy/Trade",value: `$${result.summary.expectancy_usd.toLocaleString(undefined, {minimumFractionDigits:2})}`, color: isProfit ? "var(--green)" : "var(--red)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "10px", color: "var(--ink2)", textTransform: 'uppercase' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color }}>{value}</span>
                  </div>
                ))}
              </div>

              {/* Stability */}
              <div className="card" style={{ background: 'var(--surface2)', padding: "24px" }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink2)", letterSpacing: "0.15em", marginBottom: "24px", textTransform: 'uppercase' }}>
                    Portfolio Stability
                  </div>
                {[
                  { label: "Max Drawdown",  value: `${result.summary.max_drawdown_pct}%`, color: result.summary.max_drawdown_pct > -15 ? "var(--green)" : "var(--red)" },
                  { label: "Sharpe Ratio",  value: result.summary.sharpe_ratio.toFixed(3), color: result.summary.sharpe_ratio >= 1 ? "var(--green)" : "var(--gold)" },
                  { label: "Sortino Ratio", value: result.summary.sortino_ratio.toFixed(3), color: result.summary.sortino_ratio >= 1 ? "var(--green)" : "var(--gold)" },
                  { label: "Calmar Ratio",  value: result.summary.calmar_ratio.toFixed(3), color: result.summary.calmar_ratio >= 0.5 ? "var(--green)" : "var(--gold)" },
                  { label: "Total Return",  value: `${result.summary.total_return_pct >= 0 ? "+" : ""}${result.summary.total_return_pct}%`, color: isProfit ? "var(--green)" : "var(--red)" },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "10px", color: "var(--ink2)", textTransform: 'uppercase' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: "14px", fontWeight: 700, color }}>{value}</span>
                  </div>
                ))}
              </div>

              {/* Regime Attribution */}
              <div className="card" style={{ gridColumn: "1 / -1", background: 'var(--surface2)', padding: "24px" }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: "9px", color: "var(--ink)", letterSpacing: "0.15em", marginBottom: "24px", textTransform: 'uppercase' }}>
                    Performance Attribution by Market Regime
                  </div>
                {["LOW_VOL_BULLISH","SIDEWAYS_CHOP","HIGH_VOL_BEARISH"].map(regime => {
                  const regimeTrades = result.trades.filter(t => t.regime === regime);
                  if (!regimeTrades.length) return null;
                  const rWins = regimeTrades.filter(t => t.outcome === "WIN").length;
                  const rPnl  = regimeTrades.reduce((s, t) => s + t.pnl_usd, 0);
                  const wr    = (rWins / regimeTrades.length * 100).toFixed(0);
                  return (
                    <div key={regime} style={{ display: "flex", alignItems: "center", gap: "24px", padding: "16px 0", borderBottom: "1px solid var(--border)" }}>
                      <RegimeBadge regime={regime} />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", gap: "4px", flexWrap: 'wrap' }}>
                          {regimeTrades.map((t, i) => (
                            <div key={i} style={{
                              width: "6px", height: "12px", borderRadius: "1px",
                              background: t.outcome === "WIN" ? "var(--green)" : t.outcome === "LOSS" ? "var(--red)" : "var(--ink4)",
                              opacity: 0.8
                            }} />
                          ))}
                        </div>
                      </div>
                      <div style={{ textAlign: "right", fontFamily: 'var(--mono)' }}>
                        <div style={{ fontSize: "14px", fontWeight: 700, color: rPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                          {rPnl >= 0 ? "+" : ""}${rPnl.toLocaleString(undefined, {minimumFractionDigits:2})}
                        </div>
                          <div style={{ fontSize: "9px", color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 4 }}>
                            {regimeTrades.length} Trades · {wr}% Win Rate
                          </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── EMPTY STATE ── */}
      {!result && !isRunning && (
        <div className="anim d2 card" style={{ padding: 72, textAlign: 'center' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{
              width: 56, height: 56, margin: '0 auto 20px',
              border: '1px solid var(--border2)', borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 22, color: 'var(--ink2)' }}>⬡</span>
            </div>
            <h3 style={{ fontFamily: 'var(--mono)', fontSize: "14px", letterSpacing: "0.2em", textTransform: 'uppercase', color: 'var(--white)', marginBottom: 12 }}>Simulator Standby</h3>
            <p style={{ fontSize: 13, color: 'var(--ink2)', lineHeight: 1.7, maxWidth: 480, margin: '0 auto' }}>
              Pilih universe pasar dan atur manajemen risiko di atas, lalu klik <strong style={{ color: 'var(--gold)' }}>Run Simulation</strong> untuk melihat performa algoritma APEX secara historis.
            </p>
          </div>

          <div style={{
            display: 'inline-grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 16, padding: '20px 32px',
            background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 10, marginTop: 8,
          }}>
            {[
              { label: 'Screener', pts: 'Step 1', color: 'var(--green)' },
              { label: 'HMM Regime',  pts: 'Step 2', color: 'var(--purple)' },
              { label: 'ICT Entry', pts: 'Step 3', color: 'var(--blue)' },
              { label: 'Risk Manager', pts: 'Step 4', color: 'var(--amber)' },
            ].map(({ label, pts, color }) => (
              <div key={label} style={{ textAlign: 'center' }}>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 800, color, marginBottom: 4 }}>{pts}</p>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink2)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <style>{`
        .spin-icon { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        /* Tabular nums for all stats */
        [style*="tabular-nums"] { font-variant-numeric: tabular-nums; }
      `}</style>
    </div>
  );
}