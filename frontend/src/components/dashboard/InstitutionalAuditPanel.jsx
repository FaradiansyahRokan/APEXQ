import { useState, useCallback } from "react";

const G  = "var(--gold)";
const GN = "var(--green, #10b981)";
const RD = "var(--red,  #f43f5e)";
const AM = "var(--amber, #f59e0b)";
const MN = "var(--mono, 'IBM Plex Mono', monospace)";
import { API } from "../../config";
const BASE = API;

const Spin = () => (
  <div style={{ width:14,height:14,border:"1.5px solid rgba(255,255,255,.1)",borderTopColor:G,borderRadius:"50%",animation:"spin .7s linear infinite",flexShrink:0 }} />
);

const Badge = ({ label, color=G, size=9 }) => (
  <span style={{ fontFamily:MN,fontSize:size,letterSpacing:".12em",textTransform:"uppercase",color,opacity:.85 }}>{label}</span>
);

const VerdictChip = ({ verdict }) => {
  const map = { DEPLOY:{bg:"#10b981",text:"#000"}, RESEARCH:{bg:"#3b82f6",text:"#fff"}, DISCARD:{bg:"#f43f5e",text:"#fff"} };
  const key = Object.keys(map).find(k => verdict?.includes(k)) || "RESEARCH";
  const {bg,text} = map[key];
  return <span style={{ background:bg,color:text,fontFamily:MN,fontSize:10,fontWeight:700,letterSpacing:".1em",textTransform:"uppercase",padding:"3px 10px",borderRadius:4 }}>{verdict}</span>;
};

const PassFail = ({ ok, label, detail }) => (
  <div style={{ display:"flex",alignItems:"baseline",gap:8,padding:"5px 0",borderBottom:"1px solid rgba(255,255,255,.05)" }}>
    <span style={{ color:ok?GN:RD,fontFamily:MN,fontSize:11,flexShrink:0 }}>{ok?"":""}</span>
    <span style={{ fontFamily:MN,fontSize:10,color:"var(--ink2)",flex:1 }}>{label}</span>
    <span style={{ fontFamily:MN,fontSize:10,color:ok?GN:RD }}>{detail}</span>
  </div>
);

const Metric = ({ label, value, color="var(--ink)", sub }) => (
  <div style={{ flex:1,minWidth:100 }}>
    <div style={{ fontFamily:MN,fontSize:8,color:"var(--ink4)",letterSpacing:".1em",textTransform:"uppercase",marginBottom:3 }}>{label}</div>
    <div style={{ fontFamily:MN,fontSize:18,fontWeight:700,color,fontVariantNumeric:"tabular-nums" }}>{value}</div>
    {sub && <div style={{ fontFamily:MN,fontSize:8,color:"var(--ink3)",marginTop:2 }}>{sub}</div>}
  </div>
);

const SectionHead = ({ children }) => (
  <div style={{ fontFamily:MN,fontSize:8,color:G,letterSpacing:".2em",textTransform:"uppercase",marginBottom:10,paddingBottom:7,borderBottom:"1px solid var(--border)" }}>{children}</div>
);

const BootstrapBar = ({ lower, upper, observed }) => {
  const min_ = Math.min(lower||0, 0) - .3;
  const max_ = Math.max(upper||2, 2.0) + .3;
  const range = max_ - min_;
  const pct = v => `${((v - min_) / range) * 100}%`;
  return (
    <div>
      <div style={{ fontFamily:MN,fontSize:9,color:"var(--ink3)",marginBottom:6 }}>Sharpe distribution — 5,000 bootstrap samples (no normality assumption)</div>
      <div style={{ position:"relative",height:22,background:"var(--surface3)",borderRadius:4,overflow:"hidden" }}>
        <div style={{ position:"absolute",top:0,height:"100%",left:pct(lower||0),width:`${((upper-lower)/range)*100}%`,background:(observed>=1.5?"rgba(16,185,129,.25)":"rgba(244,63,94,.25)") }} />
        <div style={{ position:"absolute",top:0,height:"100%",left:pct(1.0),width:1,background:"rgba(255,255,255,.2)" }} />
        <div style={{ position:"absolute",top:0,height:"100%",left:pct(1.5),width:1,background:`${G}66` }} />
        <div style={{ position:"absolute",top:"50%",transform:"translate(-50%,-50%)",left:pct(observed||0),width:9,height:9,borderRadius:"50%",background:(observed>=1.5?GN:RD),zIndex:2 }} />
      </div>
      <div style={{ display:"flex",justifyContent:"space-between",fontFamily:MN,fontSize:8,color:"var(--ink4)",marginTop:4 }}>
        <span>lo {lower?.toFixed(2)}</span>
        <span style={{ color:observed>=1.5?GN:RD }}>SR={observed?.toFixed(2)}</span>
        <span>hi {upper?.toFixed(2)}</span>
      </div>
    </div>
  );
};

const CVarRow = ({ label, var_, cvar_ }) => (
  <div style={{ display:"flex",alignItems:"center",gap:12,padding:"4px 0",borderBottom:"1px solid rgba(255,255,255,.04)" }}>
    <Badge label={label} color={AM} size={8} />
    <div style={{ flex:1 }} />
    <div style={{ fontFamily:MN,fontSize:10,color:RD,minWidth:70,textAlign:"right" }}>VaR {var_?.toFixed(2)}%</div>
    <div style={{ fontFamily:MN,fontSize:10,color:"#ff6b6b",minWidth:80,textAlign:"right" }}>CVaR {cvar_?.toFixed(2)}%</div>
  </div>
);

export default function InstitutionalAuditPanel() {
  const [ticker,  setTicker]  = useState("AAPL");
  const [nTrials, setNTrials] = useState(1);
  const [loading, setLoading] = useState(false);
  const [data,    setData]    = useState(null);
  const [error,   setError]   = useState(null);
  const [tab,     setTab]     = useState("overview");

  const run = useCallback(async () => {
    setLoading(true); setError(null); setData(null);
    try {
      const [repRes, riskRes] = await Promise.all([
        fetch(`${BASE}/api/v4/institutional/report`, {
          method:"POST", headers:{"Content-Type":"application/json"},
          body: JSON.stringify({ ticker, strategy_name:ticker, n_trials_tested:nTrials }),
        }),
        fetch(`${BASE}/api/v4/risk/advanced/${ticker}`),
      ]);
      if (!repRes.ok)  throw new Error((await repRes.json()).detail  || "Report error");
      if (!riskRes.ok) throw new Error((await riskRes.json()).detail || "Risk error");
      const [report, risk] = await Promise.all([repRes.json(), riskRes.json()]);
      setData({ report, risk });
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }, [ticker, nTrials]);

  // ── Field mapping: align frontend to actual API response keys ──
  const _perf = data?.report?.performance || {};
  // Normalise field names — API returns cagr_pct, sharpe_raw, volatility_pct
  const perf = {
    annualized_return_pct : _perf.cagr_pct,
    annualized_vol_pct    : _perf.volatility_pct,
    raw_sharpe            : _perf.sharpe_raw,
    calmar_ratio          : _perf.calmar_ratio,
    max_drawdown_pct      : _perf.max_drawdown_pct,
    n_observations        : data?.report?.statistical_validity?.n_obs,
  };
  const stat = data?.report?.statistical_validity;
  const boot = stat?.bootstrap_sharpe_95ci;
  const dsr  = stat?.deflated_sharpe_ratio;
  const lo   = stat?.lo2002_autocorr_adj;
  const risk = data?.risk;

  const TABS = [{ id:"overview",label:"Overview" },{ id:"statistics",label:"Statistics" },{ id:"risk",label:"Risk Lab" }];

  return (
    <div style={{ paddingTop:40,paddingBottom:80,maxWidth:900 }}>
      <div style={{ marginBottom:32 }}>
        <Badge label="Institutional Audit · Phase 2-4" color={G} size={9} />
        <h1 style={{ fontSize:30,fontWeight:800,letterSpacing:"-.02em",color:"var(--ink)",margin:"10px 0 8px" }}>Statistical Validity & Risk Report</h1>
        <p style={{ fontSize:13,color:"var(--ink2)",lineHeight:1.7,maxWidth:620 }}>
          Validates return series against institutional deployment criteria: Lo-adjusted Sharpe · DSR · Bootstrap CI · CVaR 95/99 · Tail Ratio.
        </p>
      </div>

      {/* CONTROLS */}
      <div className="card" style={{ padding:20,marginBottom:24 }}>
        <div style={{ display:"flex",gap:12,flexWrap:"wrap",alignItems:"flex-end" }}>
          <div>
            <div style={{ fontFamily:MN,fontSize:8,color:"var(--ink4)",letterSpacing:".1em",marginBottom:5 }}>TICKER</div>
            <input value={ticker} onChange={e=>setTicker(e.target.value.toUpperCase())}
              onKeyDown={e=>e.key==="Enter"&&run()}
              style={{ background:"var(--surface3)",border:"1px solid var(--border)",borderRadius:6,padding:"8px 14px",fontFamily:MN,fontSize:13,fontWeight:700,color:"var(--ink)",width:110,outline:"none" }} />
          </div>
          <div>
            <div style={{ fontFamily:MN,fontSize:8,color:"var(--ink4)",letterSpacing:".1em",marginBottom:5 }}>STRATEGIES TESTED (DSR)</div>
            <input type="number" min={1} value={nTrials} onChange={e=>setNTrials(parseInt(e.target.value)||1)}
              style={{ background:"var(--surface3)",border:"1px solid var(--border)",borderRadius:6,padding:"8px 14px",fontFamily:MN,fontSize:13,color:"var(--ink)",width:90,outline:"none" }} />
          </div>
          <button onClick={run} disabled={loading} style={{ background:loading?"var(--surface3)":G,border:"none",color:loading?"var(--ink3)":"#000",padding:"9px 26px",borderRadius:8,fontSize:12,fontWeight:700,fontFamily:MN,letterSpacing:".06em",textTransform:"uppercase",display:"flex",alignItems:"center",gap:8,cursor:loading?"not-allowed":"pointer" }}>
            {loading ? <><Spin /> Analysing…</> : "⬡ Run Audit"}
          </button>
        </div>
        {error && <div style={{ marginTop:14,padding:"10px 14px",borderRadius:6,background:"rgba(244,63,94,.1)",border:"1px solid rgba(244,63,94,.3)",fontFamily:MN,fontSize:11,color:RD }}>Error: {error}</div>}
      </div>

      {/* VERDICT BANNER */}
      {data && (
        <div className="card" style={{ padding:"18px 22px",marginBottom:24,display:"flex",alignItems:"center",gap:18,flexWrap:"wrap" }}>
          <VerdictChip verdict={data.report.overall_verdict} />
          <div style={{ fontFamily:MN,fontSize:11,color:"var(--ink2)" }}>{data.report.checks_passed} institutional checks passed</div>
          <div style={{ flex:1 }} />
          <div style={{ fontFamily:MN,fontSize:10,color:"var(--ink3)" }}>{ticker} · {perf?.n_observations} trading days</div>
        </div>
      )}

      {/* TABS */}
      {data && (
        <>
          <div style={{ display:"flex",gap:4,marginBottom:20 }}>
            {TABS.map(t => {
              const active = tab === t.id;
              return <button key={t.id} onClick={()=>setTab(t.id)} style={{ background:active?G:"var(--surface3)",border:`1px solid ${active?"transparent":"var(--border)"}`,borderRadius:6,padding:"7px 18px",fontFamily:MN,fontSize:9,fontWeight:active?700:400,letterSpacing:".1em",textTransform:"uppercase",color:active?"#000":"var(--ink2)",cursor:"pointer" }}>{t.label}</button>;
            })}
          </div>

          {/* OVERVIEW */}
          {tab === "overview" && (
            <div className="card" style={{ padding:22 }}>
              <SectionHead>Performance Summary</SectionHead>
              <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginBottom:28 }}>
                <Metric label="Ann. Return" value={`${(perf?.annualized_return_pct||0)>=0?"+":""}${perf?.annualized_return_pct?.toFixed(2)}%`} color={(perf?.annualized_return_pct||0)>=0?GN:RD} />
                <Metric label="Volatility" value={`${perf?.annualized_vol_pct?.toFixed(2)}%`} />
                <Metric label="Raw Sharpe" value={perf?.raw_sharpe?.toFixed(3)} color={(perf?.raw_sharpe||0)>=1.5?GN:(perf?.raw_sharpe||0)>=1?AM:RD} sub="unadjusted" />
                <Metric label="Lo Adj. SR" value={lo?.adjusted_sharpe_lo2002?.toFixed(3)||"—"} color={(lo?.adjusted_sharpe_lo2002||0)>=1.5?GN:AM} sub="autocorr. corrected" />
                <Metric label="Calmar" value={perf?.calmar_ratio?.toFixed(3)} color={(perf?.calmar_ratio||0)>=1?GN:(perf?.calmar_ratio||0)>=0.5?AM:RD} sub="ret / max DD" />
                <Metric label="Max DD" value={`${perf?.max_drawdown_pct?.toFixed(2)}%`} color={Math.abs(perf?.max_drawdown_pct||0)<=15?GN:Math.abs(perf?.max_drawdown_pct||0)<=25?AM:RD} />
              </div>
              <SectionHead>Institutional Target Checklist</SectionHead>
              <PassFail ok={(lo?.adjusted_sharpe_lo2002||0)>=1.5} label="Sharpe (Lo-adjusted) ≥ 1.5" detail={`SR = ${lo?.adjusted_sharpe_lo2002?.toFixed(3)||"—"}`} />
              <PassFail ok={Math.abs(perf?.max_drawdown_pct||0)<=25} label="Max Drawdown < 25%" detail={`MDD = ${perf?.max_drawdown_pct?.toFixed(2)}%`} />
              <PassFail ok={stat?.is_significant_05} label="Statistical significance p < 0.05" detail={`p = ${stat?.p_value?.toFixed(4)||"—"}`} />
              <PassFail ok={dsr?.is_significant_05} label="Deflated Sharpe significant (accounts for N strategies tested)" detail={`DSR = ${dsr?.dsr_probability?.toFixed(3)||"—"}`} />
              <PassFail ok={(boot?.prob_sr_above_1||0)>=60} label="Bootstrap P(SR > 1.0) ≥ 60%" detail={`P = ${boot?.prob_sr_above_1?.toFixed(1)||"—"}%`} />
            </div>
          )}

          {/* STATISTICS */}
          {tab === "statistics" && stat && (
            <div style={{ display:"flex",flexDirection:"column",gap:16 }}>
              <div className="card" style={{ padding:22 }}>
                <SectionHead>Bootstrapped Sharpe CI</SectionHead>
                <BootstrapBar lower={boot?.lower} upper={boot?.upper} observed={perf?.raw_sharpe} />
                <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginTop:18 }}>
                  <Metric label="P(SR > 0)"   value={`${boot?.prob_sr_positive?.toFixed(1)}%`}  color={(boot?.prob_sr_positive||0)>=80?GN:AM} />
                  <Metric label="P(SR > 1.0)" value={`${boot?.prob_sr_above_1?.toFixed(1)}%`}   color={(boot?.prob_sr_above_1||0)>=60?GN:AM} />
                  <Metric label="P(SR > 1.5)" value={boot?.prob_sr_above_15 != null ? `${boot.prob_sr_above_15.toFixed(1)}%` : "—"}  color={(boot?.prob_sr_above_15||0)>=40?GN:RD} />
                </div>
              </div>
              <div className="card" style={{ padding:22 }}>
                <SectionHead>Lo (2002) Autocorrelation Adjustment</SectionHead>
                <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginBottom:14 }}>
                  <Metric label="Raw Sharpe"    value={lo?.raw_sharpe?.toFixed(3)||"—"}                 sub="uncorrected" />
                  <Metric label="Adjusted SR"   value={lo?.adjusted_sharpe_lo2002?.toFixed(3)||"—"}     color={AM} sub="Lo (2002)" />
                  <Metric label="η Correction"  value={lo?.autocorr_factor_eta?.toFixed(3)||"—"}        sub="η > 1 = over-stated" />
                </div>
                <div style={{ fontFamily:MN,fontSize:9,color:"var(--ink3)",padding:"8px 12px",background:"var(--surface3)",borderRadius:6,marginBottom:16 }}>{lo?.interpretation}</div>
                <SectionHead>Deflated Sharpe Ratio (Bailey-López de Prado 2016)</SectionHead>
                <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginBottom:12 }}>
                  <Metric label="DSR Probability" value={`${((dsr?.dsr_probability||0)*100).toFixed(1)}%`} color={dsr?.is_significant_05?GN:RD} sub={`threshold SR* = ${dsr?.sr_star_threshold?.toFixed(3)}`} />
                  <Metric label="Strategies N"    value={dsr?.n_trials||"—"}   color="var(--ink2)" sub="tested (your input)" />
                </div>
                <div style={{ fontFamily:MN,fontSize:9,color:"var(--ink3)",padding:"8px 12px",background:"var(--surface3)",borderRadius:6 }}>{dsr?.interpretation}</div>
              </div>
              <div className="card" style={{ padding:22 }}>
                <SectionHead>t-test: Is Return 0?</SectionHead>
                <div style={{ display:"flex",gap:24,flexWrap:"wrap" }}>
                  <Metric label="t-stat" value={stat?.t_statistic?.toFixed(3)||"—"} color={Math.abs(stat?.t_statistic||0)>=1.96?GN:RD} sub="≥1.96 for p<0.05" />
                  <Metric label="p-value" value={stat?.p_value?.toFixed(4)||"—"}    color={(stat?.p_value||1)<=0.05?GN:(stat?.p_value||1)<=0.10?AM:RD} sub="one-sided" />
                  <Metric label="N" value={perf?.n_observations||"—"} color={(perf?.n_observations||0)>=200?GN:AM} sub="≥200 for power" />
                </div>
              </div>
            </div>
          )}

          {/* RISK LAB */}
          {tab === "risk" && risk && (
            <div style={{ display:"flex",flexDirection:"column",gap:16 }}>
              <div className="card" style={{ padding:22 }}>
                <SectionHead>CVaR — Conditional Value at Risk (Cornish-Fisher corrected)</SectionHead>
                <CVarRow label="95% Hist"  var_={risk?.var_95_hist_pct} cvar_={risk?.cvar_95_hist_pct} />
                <CVarRow label="95% C-F"   var_={risk?.var_95_cf_pct}   cvar_={risk?.cvar_95_cf_pct} />
                <CVarRow label="99% Hist"  var_={risk?.var_99_hist_pct} cvar_={risk?.cvar_99_hist_pct} />
                <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginTop:18 }}>
                  <Metric label="Tail Ratio"   value={risk.tail_ratio?.toFixed(3)}    color={(risk.tail_ratio||0)>=1?GN:RD} sub="P95↑ / |P5↓|" />
                  <Metric label="CDaR 95%"     value={`${risk.cdar_95_pct?.toFixed(2)}%`} color={RD} sub="conditional drawdown at risk" />
                  <Metric label="Ulcer Index"  value={risk.ulcer_index?.toFixed(3)}   color={AM} sub="RMS of drawdowns" />
                  <Metric label="Omega Ratio"  value={risk.omega_ratio?.toFixed(3)}   color={(risk.omega_ratio||0)>=1?GN:RD} />
                </div>
              </div>
              <div className="card" style={{ padding:22 }}>
                <SectionHead>Return Distribution Diagnostics</SectionHead>
                <div style={{ display:"flex",gap:24,flexWrap:"wrap",marginBottom:14 }}>
                  <Metric label="Skewness"        value={risk.skewness?.toFixed(4)}        color={(risk.skewness||0)>=0?GN:RD} sub="≥0 = positive tail" />
                  <Metric label="Excess Kurtosis" value={risk.excess_kurtosis?.toFixed(4)} color={(risk.excess_kurtosis||0)>3?RD:GN} sub=">3 = fat-tail" />
                  <Metric label="Ann. Return"     value={`${risk.annualized_return_pct?.toFixed(2)}%`} color={(risk.annualized_return_pct||0)>=0?GN:RD} />
                  <Metric label="Ann. Vol"        value={`${risk.annualized_vol_pct?.toFixed(2)}%`} />
                </div>
                {risk.fat_tail_present && (
                  <div style={{ padding:"8px 12px",borderRadius:6,background:"rgba(244,63,94,.08)",border:"1px solid rgba(244,63,94,.2)",fontFamily:MN,fontSize:9,color:RD,marginBottom:8 }}>
                     Fat-tail detected (excess kurtosis = {risk.excess_kurtosis?.toFixed(2)}). Gaussian VaR understates risk 30-50%. Use Cornish-Fisher CVaR above.
                  </div>
                )}
                {risk.negative_skew_warning && (
                  <div style={{ padding:"8px 12px",borderRadius:6,background:"rgba(245,158,11,.08)",border:"1px solid rgba(245,158,11,.2)",fontFamily:MN,fontSize:9,color:AM }}>
                     Negative skew ({risk.skewness?.toFixed(2)}). Strategy has asymmetric downside. Check for short-gamma/short-vol exposure.
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}