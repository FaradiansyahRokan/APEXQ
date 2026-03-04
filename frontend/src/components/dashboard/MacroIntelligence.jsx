import React from 'react';

// ─── Sub-components ──────────────────────────────────────────────

const MiniBar = ({ value, max, color = 'var(--ink3)' }) => (
  <div style={{ flex: 1, height: 2, background: 'var(--surface3)', borderRadius: 2, overflow: 'hidden' }}>
    <div style={{
      height: '100%',
      width: `${Math.min(100, (value / max) * 100)}%`,
      background: color, borderRadius: 2,
      transition: 'width 1s cubic-bezier(.22,1,.36,1)',
    }} />
  </div>
);

const Row = ({ label, value, color }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 0', borderBottom: '1px solid var(--border)',
  }}>
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 9,
      letterSpacing: '0.09em', textTransform: 'uppercase',
      color: 'var(--ink4)',
    }}>{label}</span>
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 11,
      fontWeight: 500,
      color: color || 'var(--ink2)',
    }}>{value}</span>
  </div>
);

const Panel = ({ label, children }) => (
  <div style={{
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '16px 18px',
    transition: 'border-color .2s',
  }}>
    <p style={{
      fontFamily: 'var(--mono)', fontSize: 8,
      letterSpacing: '0.14em', textTransform: 'uppercase',
      color: 'var(--ink4)', marginBottom: 14,
    }}>{label}</p>
    {children}
  </div>
);

// ─── Main Component ───────────────────────────────────────────────

export function MacroIntelligence({ apexData }) {
  if (!apexData?.macro && !apexData?.hmm_regime && !apexData?.factor_lab) return null;

  const { macro, hmm_regime, factor_lab } = apexData;
  const stats   = apexData?.statistics || {};
  const ict     = apexData?.ict_analysis || {};
  const kelly   = apexData?.kelly || {};
  const mc      = stats?.monte_carlo || {};
  const regime  = stats?.regime || {};
  const zscore  = stats?.zscore || {};
  const varcvar = stats?.var_cvar || {};
  const probP   = mc?.probability_analysis?.prob_profit_pct ?? 50;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* Section title */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <p className="section-title" style={{ marginBottom: 0, borderBottom: 'none' }}>
          Macro Intelligence & Factor Decomposition
        </p>
        <span className="badge badge-muted">APEX v2</span>
      </div>

      {/* Row 1 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>

        {/* Cross-Asset */}
        <Panel label="Cross-Asset">
          {macro && Object.entries(macro).map(([key, val]) => {
            const up    = (val?.change_pct ?? 0) > 0;
            const isRisk = key !== 'DXY' ? up : !up;
            return (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink3)' }}>{key}</span>
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500,
                  color: isRisk ? 'var(--pos)' : 'var(--neg)',
                }}>
                  {up ? '▲' : '▼'} {Math.abs(val?.change_pct ?? 0).toFixed(2)}%
                </span>
              </div>
            );
          })}
          {macro?.DXY && (
            <div style={{ marginTop: 8, padding: '5px 8px', background: 'var(--surface2)', borderRadius: 5 }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>
                DXY @ {macro.DXY.current?.toFixed(2)}
              </span>
            </div>
          )}
        </Panel>

        {/* HMM State */}
        <Panel label="Market Regime">
          <p style={{
            fontSize: 13, fontWeight: 700, letterSpacing: '-0.01em',
            color: 'var(--ink)', lineHeight: 1.25, marginBottom: 10,
          }}>
            {(hmm_regime?.regime || regime?.market_regime || 'SCANNING').replace(/_/g, ' ')}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <MiniBar value={hmm_regime?.confidence || 0} max={100} color="var(--ink3)" />
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)', flexShrink: 0 }}>
              {Math.round(hmm_regime?.confidence || 0)}%
            </span>
          </div>
          <Row label="Hurst"   value={`H=${(hmm_regime?.hurst_exponent || 0).toFixed(3)}`} />
          <Row label="Persist" value={`${hmm_regime?.regime_persistence_days || 0}d`} />
          <Row label="Vol 30D" value={`${(hmm_regime?.vol_30d_annualized || 0).toFixed(1)}%`}
            color={(hmm_regime?.vol_30d_annualized || 0) > 40 ? 'var(--neg)' : 'var(--ink2)'} />
        </Panel>

        {/* Factor Alpha */}
        <Panel label="Factor Alpha">
          <Row
            label="Momentum"
            value={apexData?.factor?.momentum_factor?.acceleration_label || '—'}
            color={apexData?.factor?.momentum_factor?.acceleration_label === 'ACCELERATING' ? 'var(--pos)' : 'var(--neg)'}
          />
          <Row label="VRP Level" value={`${(apexData?.factor?.vol_risk_premium?.vrp_meaningful_pct ?? 0).toFixed(2)}%`} />
          <Row
            label="Vol Premium"
            value={apexData?.factor?.vol_risk_premium?.vrp_regime?.replace(/_/g, ' ') || '—'}
            color={apexData?.factor?.vol_risk_premium?.vrp_regime === 'ELEVATED_MEAN_REVERSION' ? 'var(--pos)' : undefined}
          />
          <Row
            label="Sortino"
            value={(apexData?.quant?.sortino ?? 0).toFixed(2)}
            color={(apexData?.quant?.sortino ?? 0) > 0 ? 'var(--pos)' : 'var(--neg)'}
          />
          <Row label="Max DD" value={`${(apexData?.quant?.max_drawdown ?? 0).toFixed(2)}%`} color="var(--neg)" />
        </Panel>

        {/* ICT */}
        <Panel label="Smart Money (ICT)">
          <Row label="FVG Open" value={ict?.fvg_analysis ? (ict.fvg_analysis.unfilled_bullish?.length || 0) + (ict.fvg_analysis.unfilled_bearish?.length || 0) : '—'} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
            <span className={`badge ${
              ict?.composite_bias === 'BULLISH' ? 'badge-green'
              : ict?.composite_bias === 'BEARISH' ? 'badge-red'
              : 'badge-muted'
            }`}>
              {ict?.composite_bias || 'NEUTRAL'}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)' }}>
              {ict?.bullish_factors ?? 0}B / {ict?.bearish_factors ?? 0}R
            </span>
          </div>
          <Row label="POC"       value={ict?.volume_profile?.poc_price ? ict.volume_profile.poc_price.toFixed(4) : "—"} />
          <Row label="Price Pos" value={ict?.market_structure?.market_structure?.replace(/_/g, ' ') || '—'} />
          <Row label="Liquidity" value={apexData?.liq_regime?.liquidity_regime || '—'} />
          <Row label="Structure" value={ict?.market_structure?.market_structure?.replace(/_/g, ' ') || '—'} />
        </Panel>
      </div>

      {/* Row 2 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>

        {/* Monte Carlo */}
        <Panel label="Monte Carlo · 5K sim · 30D">
          <div style={{ display: 'flex', gap: 14, marginBottom: 14 }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)', marginBottom: 4 }}>WIN PROB</p>
              <p className="num" style={{
                fontSize: 22, fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1,
                color: probP > 50 ? 'var(--pos)' : 'var(--neg)',
              }}>{probP}%</p>
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)', marginBottom: 4 }}>MEDIAN</p>
              <p className="num" style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink)', lineHeight: 1 }}>
                {mc?.price_median?.toFixed(2) ?? '—'}
              </p>
            </div>
          </div>
          <Row label="Best 5%"    value={mc?.price_p95?.toFixed(2) ?? '—'}  color="var(--pos)" />
          <Row label="Worst 5%"   value={mc?.price_p5?.toFixed(2) ?? '—'} color="var(--neg)" />
          <Row label="CVaR Sim"   value={`${Math.abs(mc?.cvar_pct ?? 0).toFixed(2)}%`} color="var(--neg)" />
        </Panel>

        {/* Risk Metrics */}
        <Panel label="Risk Metrics">
          <p style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)', marginBottom: 4 }}>Z-SCORE</p>
          <p className="num" style={{
            fontSize: 24, fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 8,
            color: Math.abs(zscore?.current_zscore ?? 0) >= 2 ? 'var(--neg)' : 'var(--ink)',
          }}>
            {(zscore?.current_zscore ?? 0) > 0 ? '+' : ''}{(zscore?.current_zscore ?? 0).toFixed(2)}σ
          </p>
          <span className={`badge ${
            zscore?.signal?.includes('OVERSOLD')   ? 'badge-green'
            : zscore?.signal?.includes('OVERBOUGHT') ? 'badge-red'
            : 'badge-muted'
          }`} style={{ marginBottom: 12, display: 'inline-flex' }}>
            {zscore?.signal || 'NEUTRAL'}
          </span>
          <Row label="VaR 95%"  value={`${Math.abs(apexData?.quant?.var_95_cf_pct ?? 0).toFixed(3)}%`}  color="var(--neg)" />
          <Row label="CVaR"     value={`${Math.abs(apexData?.quant?.cvar_95_cf_pct ?? 0).toFixed(3)}%`} color="var(--neg)" />
          <Row label="Method"   value="Cornish-Fisher" />
        </Panel>

        {/* Kelly */}
        <Panel label="Kelly Criterion">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span className={`badge ${
              kelly?.edge_quality === 'STRONG' || kelly?.edge_quality === 'MODERATE' ? 'badge-green'
              : kelly?.edge_quality === 'WEAK' ? 'badge-amber'
              : 'badge-red'
            }`}>
              {kelly?.edge_quality || '—'}
            </span>
            <span className="num" style={{
              fontSize: 11, fontWeight: 500,
              color: (kelly?.expected_value_pct ?? 0) >= 0 ? 'var(--pos)' : 'var(--neg)',
            }}>
              EV {(kelly?.expected_value_pct ?? 0) > 0 ? '+' : ''}{(kelly?.expected_value_pct ?? 0).toFixed(4)}%
            </span>
          </div>
          <Row label="Safe Kelly"  value={`${(kelly?.safe_kelly_pct ?? 0).toFixed(3)}%`} />
          <Row label="Dollar Risk" value={`$${(kelly?.dollar_risk_safe ?? 0).toFixed(0)}`}
            color={(kelly?.dollar_risk_safe ?? 0) > 600 ? 'var(--neg)' : undefined} />
          <Row
            label="Ruin Prob"
            value={`${(kelly?.ruin_probability_pct ?? 0).toFixed(2)}%`}
            color={(kelly?.ruin_probability_pct ?? 100) < 10 ? 'var(--pos)' : 'var(--neg)'}
          />
          <Row label="Reward/Risk" value={`${(kelly?.reward_risk_ratio ?? 0).toFixed(2)}×`} />
        </Panel>
      </div>
    </div>
  );
}