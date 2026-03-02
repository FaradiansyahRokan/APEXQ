import React from 'react';
import { Label } from './Label';

const COLORS = {
  green: 'var(--green)', red: 'var(--red)', gold: 'var(--gold)',
  blue: 'var(--blue)', purple: 'var(--purple)', amber: 'var(--amber)',
};

export const MetricCell = ({ label, value, color, sub, accent }) => {
  const textColor = COLORS[color] || 'var(--ink)';
  return (
    <div style={{
      padding: '22px 24px',
      borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', gap: 10,
      position: 'relative',
      background: accent ? `${accent}05` : 'transparent',
    }}>
      {accent && (
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 1, background: `linear-gradient(90deg, ${accent}60, transparent)` }} />
      )}
      <Label>{label}</Label>
      <p style={{
        fontSize: 26, fontWeight: 700, letterSpacing: '-0.025em', lineHeight: 1,
        color: textColor, fontFamily: 'var(--font)', fontVariantNumeric: 'tabular-nums',
      }}>{value ?? '—'}</p>
      {sub && <span style={{ fontSize: 10, color: 'var(--ink3)', fontFamily: 'var(--mono)' }}>{sub}</span>}
    </div>
  );
};