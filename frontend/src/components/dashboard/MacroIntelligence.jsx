import React from 'react';

const MiniBar = ({ value, max, color }) => (
  <div style={{ flex: 1, height: 3, background: 'var(--surface3)', borderRadius: 2, overflow: 'hidden' }}>
    <div style={{ height: '100%', width: `${Math.min(100, (value / max) * 100)}%`, background: color, borderRadius: 2, transition: 'width 1s ease' }} />
  </div>
);

const StatRow = ({ label, value, color = 'var(--ink)' }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--ink3)' }}>{label}</span>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500, color }}>{value}</span>
  </div>
);

const Card = ({ children, accentColor, style: sx }) => (
  <div style={{
    background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12,
    overflow: 'hidden', position: 'relative', ...sx,
  }}>
    {accentColor && <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: `linear-gradient(90deg, ${accentColor}, transparent)` }} />}
    {children}
  </div>
);

export function MacroIntelligence({ apexData }) {
  if (!apexData?.macro && !apexData?.hmm_regime && !apexData?.factor_lab) return null;

  const { macro, hmm_regime, factor_lab } = apexData;
  const stats   = apexData?.statistics || {};
  const ict     = apexData?.ict_analysis || {};
  const kelly   = apexData?.kelly || {};
  const apex    = apexData?.apex_score || {};
  const mc      = stats?.monte_carlo || {};
  const regime  = stats?.regime || {};
  const zscore  = stats?.zscore || {};
  const varcvar = stats?.var_cvar || {};

  const regimeColor = (r) => {
    if (!r) return 'var(--ink3)';
    if (r.includes('BULL') || r.includes('LOW_VOL')) return 'var(--green)';
    if (r.includes('BEAR') || r.includes('HIGH_VOL')) return 'var(--red)';
    if (r.includes('SIDE') || r.includes('CHOP')) return 'var(--amber)';
    return 'var(--blue)';
  };

  return (
    <div className="anim d3">
      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, padding: '0 2px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 3, height: 18, background: 'var(--gold)', borderRadius: 2 }} />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--ink2)' }}>Macro Intelligence & Factor Decomposition</span>
        </div>
        <span className="badge badge-gold">APEX v2</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 12 }}>

        {/* 1 — Cross-Asset Correlation */}
        <Card accentColor="var(--blue)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--blue)', marginBottom: 14 }}>Cross-Asset</p>
          {macro && Object.entries(macro).map(([key, val]) => {
            const up = (val?.change_pct ?? 0) > 0;
            const isRisk = key === 'DXY';
            const green = isRisk ? !up : up;
            return (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>{key}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 600, color: green ? 'var(--green)' : 'var(--red)' }}>
                    {up ? '▲' : '▼'} {Math.abs(val?.change_pct ?? 0).toFixed(2)}%
                  </span>
                </div>
              </div>
            );
          })}
          {macro?.DXY && (
            <div style={{ marginTop: 12, padding: '8px 10px', background: 'var(--surface3)', borderRadius: 6 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>DXY @ {macro.DXY.current?.toFixed(2)}</span>
            </div>
          )}
        </Card>

        {/* 2 — HMM Market State */}
        <Card accentColor="var(--purple)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--purple)', marginBottom: 14 }}>Hidden Markov State</p>
          <div style={{ marginBottom: 14 }}>
            <p style={{ fontSize: 15, fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--ink)', lineHeight: 1.2, marginBottom: 6 }}>
              {(hmm_regime?.regime || regime?.market_regime || 'SCANNING').replace(/_/g, ' ')}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <MiniBar value={hmm_regime?.confidence || 0} max={100} color="var(--purple)" />
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--purple)', whiteSpace: 'nowrap' }}>{Math.round(hmm_regime?.confidence || 0)}%</span>
            </div>
          </div>
          <StatRow label="Hurst" value={`H=${(regime?.hurst_exponent || 0).toFixed(3)}`} color="var(--ink2)" />
          <StatRow label="Persist" value={`${regime?.regime_persistence_days || 0}d`} color="var(--ink2)" />
          <StatRow label="30D Vol" value={`${(regime?.vol_30d_annualized || 0).toFixed(1)}%`} color="var(--amber)" />
        </Card>

        {/* 3 — Factor Research Lab */}
        <Card accentColor="var(--green)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--green)', marginBottom: 14 }}>Factor Alpha</p>
          {factor_lab && (
            <>
              <StatRow label="Momentum" value={factor_lab.momentum_acceleration} color={factor_lab.momentum_acceleration === 'ACCELERATING' ? 'var(--green)' : 'var(--red)'} />
              <StatRow label="Beta / Nasdaq" value={(factor_lab.market_beta_nasdaq ?? 0).toFixed(3)} color="var(--ink2)" />
              <StatRow label="Risk Mode" value={factor_lab.risk_mode} color={factor_lab.risk_mode === 'RISK_ON' ? 'var(--green)' : 'var(--amber)'} />
            </>
          )}
          <StatRow label="Sortino" value={apexData?.metrics?.sortino?.toFixed(2) || (apexData?.quant?.sortino ?? 0).toFixed(2)} color={(apexData?.quant?.sortino ?? 0) > 0 ? 'var(--green)' : 'var(--red)'} />
          <StatRow label="Max DD" value={`${(apexData?.quant?.max_drawdown ?? 0).toFixed(2)}%`} color="var(--red)" />
        </Card>

        {/* 4 — ICT / Smart Money */}
        <Card accentColor="var(--gold)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 14 }}>Smart Money (ICT)</p>

          {/* Bias pill */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
            <span className={`badge ${ict?.composite_bias === 'BULLISH' ? 'badge-green' : ict?.composite_bias === 'BEARISH' ? 'badge-red' : 'badge-muted'}`}>
              {ict?.composite_bias || 'NEUTRAL'}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)' }}>
              {(ict?.bullish_factors ?? 0)}B / {(ict?.bearish_factors ?? 0)}R
            </span>
          </div>

          <StatRow label="POC" value={(ict?.volume_profile?.poc_price ?? 0).toFixed(4)} color="var(--gold)" />
          <StatRow label="Price Pos" value={ict?.volume_profile?.price_position?.replace(/_/g, ' ') || '—'} color="var(--ink2)" />
          <StatRow label="Liq Bias" value={ict?.liquidity_zones?.liquidity_bias || '—'} color="var(--amber)" />
          <StatRow label="Structure" value={ict?.market_structure?.market_structure?.replace(/_/g, ' ') || '—'} color="var(--ink2)" />
        </Card>
      </div>

      {/* Second row — Stats Engine */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 12 }}>

        {/* Monte Carlo */}
        <Card accentColor="var(--blue)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--blue)', marginBottom: 14 }}>Monte Carlo (5K sim · 30D)</p>
          <div style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', marginBottom: 4 }}>WIN PROB</p>
              <p style={{ fontSize: 22, fontWeight: 700, color: (mc?.probability_analysis?.prob_profit_pct ?? 50) > 50 ? 'var(--green)' : 'var(--red)', letterSpacing: '-0.02em' }}>
                {mc?.probability_analysis?.prob_profit_pct ?? '—'}%
              </p>
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', marginBottom: 4 }}>MEDIAN PATH</p>
              <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink)', letterSpacing: '-0.01em', fontVariantNumeric: 'tabular-nums' }}>
                {mc?.price_projections?.median_50pct?.toFixed(2) ?? '—'}
              </p>
            </div>
          </div>
          <StatRow label="Best 5%" value={mc?.price_projections?.best_5pct?.toFixed(2) ?? '—'} color="var(--green)" />
          <StatRow label="Worst 5%" value={mc?.price_projections?.worst_5pct?.toFixed(2) ?? '—'} color="var(--red)" />
          <StatRow label="Max DD Sim" value={`${Math.abs(mc?.drawdown_analysis?.worst_5pct_drawdown ?? 0).toFixed(2)}%`} color="var(--red)" />
        </Card>

        {/* Z-Score + VaR */}
        <Card accentColor="var(--amber)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--amber)', marginBottom: 14 }}>Risk Metrics</p>
          <div style={{ marginBottom: 14 }}>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', marginBottom: 4 }}>Z-SCORE</p>
            <p style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', color: Math.abs(zscore?.current_zscore ?? 0) >= 2 ? 'var(--red)' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
              {(zscore?.current_zscore ?? 0) > 0 ? '+' : ''}{(zscore?.current_zscore ?? 0).toFixed(2)}σ
            </p>
            <span className={`badge ${zscore?.signal?.includes('OVERSOLD') ? 'badge-green' : zscore?.signal?.includes('OVERBOUGHT') ? 'badge-red' : 'badge-muted'}`} style={{ marginTop: 6 }}>
              {zscore?.signal || 'NEUTRAL'}
            </span>
          </div>
          <StatRow label="VaR 95%" value={`${(varcvar?.var_pct ?? 0).toFixed(3)}%`} color="var(--red)" />
          <StatRow label="CVaR" value={`${(varcvar?.cvar_pct ?? 0).toFixed(3)}%`} color="var(--red)" />
          <StatRow label="Prob (Param)" value={`${varcvar?.method || 'Historical'}`} color="var(--ink3)" />
        </Card>

        {/* Kelly Edge */}
        <Card accentColor="var(--green)" style={{ padding: 20 }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--green)', marginBottom: 14 }}>Kelly Criterion</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <span className={`badge ${kelly?.edge_quality === 'STRONG' || kelly?.edge_quality === 'MODERATE' ? 'badge-green' : kelly?.edge_quality === 'WEAK' ? 'badge-gold' : 'badge-red'}`}>
              {kelly?.edge_quality || '—'}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: (kelly?.expected_value_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
              EV {(kelly?.expected_value_pct ?? 0) > 0 ? '+' : ''}{(kelly?.expected_value_pct ?? 0).toFixed(4)}%
            </span>
          </div>
          <StatRow label="Safe Kelly %" value={`${(kelly?.safe_kelly_pct ?? 0).toFixed(3)}%`} color="var(--ink2)" />
          <StatRow label="Dollar Risk" value={`$${(kelly?.dollar_risk_safe ?? 0).toFixed(0)}`} color="var(--gold)" />
          <StatRow label="Ruin Prob" value={`${(kelly?.ruin_probability_pct ?? 0).toFixed(2)}%`} color={(kelly?.ruin_probability_pct ?? 100) < 10 ? 'var(--green)' : 'var(--red)'} />
          <StatRow label="Reward/Risk" value={`${(kelly?.reward_risk_ratio ?? 0).toFixed(2)}×`} color="var(--ink2)" />
        </Card>
      </div>
    </div>
  );
}