import React from 'react';
import { Label } from '../common/Label';
import MarketOverview from '../MarketOverview';

export const WatchlistCard = ({ item, onClick }) => {
  const up = (item.change ?? 0) >= 0;
  const clr = up ? 'var(--green)' : 'var(--red)';
  const chartHex = up ? '#10B981' : '#F43F5E';

  return (
    <div onClick={onClick} className="card" style={{
      padding: 24, display: 'flex', flexDirection: 'column', gap: 18,
      cursor: 'pointer', transition: 'all .25s cubic-bezier(.22,1,.36,1)',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.borderColor = 'var(--border3)';
      e.currentTarget.style.transform = 'translateY(-3px)';
      e.currentTarget.style.boxShadow = '0 16px 40px rgba(0,0,0,.5)';
    }}
    onMouseLeave={e => {
      e.currentTarget.style.borderColor = 'var(--border)';
      e.currentTarget.style.transform = 'translateY(0)';
      e.currentTarget.style.boxShadow = 'none';
    }}>
      {/* Top row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Label style={{ marginBottom: 6 }}>{item.symbol}</Label>
          <h4 style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--ink)' }}>{item.name}</h4>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ fontSize: 20, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>{item.price?.toLocaleString() ?? '—'}</p>
          <span style={{ fontSize: 11, fontWeight: 600, color: clr, fontFamily: 'var(--mono)' }}>
            {up ? '▲' : '▼'} {Math.abs(item.change ?? 0).toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Sparkline */}
      <div style={{ width: '100%', height: 80, borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
        {item.sparkline?.length > 0
          ? <MarketOverview data={item.sparkline} isMini={true} color={chartHex} />
          : <div className="shimmer" style={{ height: '100%', borderRadius: 8 }} />
        }
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 1, background: 'var(--border)', borderRadius: 8, overflow: 'hidden' }}>
        {[['Open', item.open], ['High', item.high], ['Low', item.low], ['Vol', null]].map(([l, v], i) => (
          <div key={i} style={{ background: 'var(--surface2)', padding: '10px 12px' }}>
            <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 4 }}>{l}</p>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 500,
              color: l === 'High' ? 'var(--green)' : l === 'Low' ? 'var(--red)' : 'var(--ink)',
            }}>{v != null ? v.toLocaleString() : '—'}</span>
          </div>
        ))}
      </div>
    </div>
  );
};