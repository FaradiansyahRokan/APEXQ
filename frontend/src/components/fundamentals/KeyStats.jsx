import React from 'react';

const fmt = (n) => {
  if (!n || n === 'N/A') return '—';
  if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9)  return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6)  return (n / 1e6).toFixed(2) + 'M';
  return Number(n).toLocaleString();
};

const Item = ({ label, value, highlight }) => (
  <div style={{
    padding: '14px 16px',
    background: highlight ? 'rgba(201,169,110,0.04)' : 'var(--surface3)',
    borderRadius: 8,
    border: `1px solid ${highlight ? 'rgba(201,169,110,0.16)' : 'var(--border)'}`,
    display: 'flex', flexDirection: 'column', gap: 8,
  }}>
    <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)' }}>{label}</span>
    <span style={{ fontSize: 16, fontWeight: 700, letterSpacing: '-0.01em', color: highlight ? 'var(--gold)' : 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
  </div>
);

export default function KeyStats({ stats, currency = 'USD' }) {
  if (!stats) return null;
  const cur = currency || 'USD';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
      <Item label="Market Cap"    value={`${cur} ${fmt(stats.market_cap)}`}            highlight />
      <Item label="24h Volume"    value={fmt(stats.volume_24h)} />
      <Item label="P/E Ratio"     value={stats.pe_ratio !== 'N/A' ? stats.pe_ratio : '—'} />
      <Item label="P/B Ratio"     value={stats.pb_ratio !== 'N/A' ? stats.pb_ratio : '—'} />
      <Item label="Shares Out."   value={fmt(stats.shares_outstanding)} />
      <Item label="Free Float"    value={fmt(stats.float_shares)} />
    </div>
  );
}