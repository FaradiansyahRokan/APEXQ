import React from 'react';
import { Label } from './Label';

const COLOR_MAP = {
  green: 'var(--pos)',
  red:   'var(--neg)',
  // Everything else → monochromatic
  blue:  'var(--ink)',
  purple:'var(--ink)',
  amber: 'var(--amber)',
  gold:  'var(--amber)',
};

export const MetricCell = ({ label, value, color, sub, accent, last, style: sx }) => {
  const isPos = color === 'green';
  const isNeg = color === 'red';
  const isFinancial = isPos || isNeg;
  const textColor = isFinancial
    ? COLOR_MAP[color]
    : color === 'amber' || color === 'gold'
      ? 'var(--amber)'
      : 'var(--ink)';

  return (
    <div
      style={{
        paddingBottom: last ? 0 : 12,
        marginBottom: last ? 0 : 12,
        borderBottom: last ? 'none' : '1px solid var(--border)',
        ...sx,
      }}
    >
      {label && <Label style={{ marginBottom: 5 }}>{label}</Label>}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, flexWrap: 'wrap' }}>
        <span
          className="num"
          style={{
            fontSize: 15,
            fontWeight: 600,
            color: textColor,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {sub && (
          <span style={{ fontSize: 10, color: 'var(--ink4)', fontFamily: 'var(--mono)' }}>
            {sub}
          </span>
        )}
      </div>
      {accent && (
        <div style={{
          marginTop: 6,
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <div style={{ flex: 1, height: 2, background: 'var(--surface3)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${Math.min(100, Math.max(0, accent))}%`,
              background: isFinancial ? textColor : 'var(--ink3)',
              borderRadius: 2,
              transition: 'width .8s cubic-bezier(.22,1,.36,1)',
            }} />
          </div>
          <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--ink4)', flexShrink: 0 }}>
            {accent.toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
};