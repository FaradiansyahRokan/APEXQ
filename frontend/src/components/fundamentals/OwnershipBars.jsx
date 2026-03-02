import React from 'react';

const Seg = ({ label, pct, color, dotColor }) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    <div style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
    <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>{label}</span>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600, color: 'var(--ink)', marginLeft: 'auto' }}>{pct}%</span>
  </div>
);

export default function OwnershipBar({ ownership }) {
  if (!ownership) return null;
  const { insider = 0, institutions = 0, public: pub = 0 } = ownership;

  return (
    <div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
        <Seg label="Institutions (Whale)" pct={institutions} dotColor="var(--blue)" />
        <Seg label="Insiders (C-Level)"   pct={insider}      dotColor="var(--gold)" />
        <Seg label="Retail / Public"      pct={pub}          dotColor="var(--ink4)" />
      </div>

      {/* Stacked bar */}
      <div style={{ width: '100%', height: 6, borderRadius: 4, overflow: 'hidden', display: 'flex', gap: 1 }}>
        <div style={{ width: `${institutions}%`, background: 'var(--blue)', transition: 'width 1s ease', borderRadius: '4px 0 0 4px' }} />
        <div style={{ width: `${insider}%`, background: 'var(--gold)', transition: 'width 1s ease' }} />
        <div style={{ flex: 1, background: 'var(--surface3)', borderRadius: '0 4px 4px 0' }} />
      </div>

      {/* Insight */}
      <div style={{ marginTop: 14, padding: '10px 14px', background: 'var(--surface3)', borderRadius: 8, borderLeft: '2px solid var(--gold3)' }}>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink3)', lineHeight: 1.7 }}>
          {institutions > 40
            ? `Institutional presence (${institutions}%) is strong — smart money conviction high.`
            : insider > 15
            ? `Insider ownership (${insider}%) elevated — alignment with shareholders.`
            : `Retail-dominated (${pub}%) — more susceptible to sentiment swings.`}
        </p>
      </div>
    </div>
  );
}