import React from 'react';
import MarketOverview from '../MarketOverview';

export const WatchlistCard = ({ item, onClick }) => {
  const up  = (item.change ?? 0) >= 0;
  const clr = up ? 'var(--pos)' : 'var(--neg)';
  const hex = up ? '#22c55e' : '#ef4444';

  return (
    <div
      onClick={onClick}
      style={{
        padding: '18px 20px',
        cursor: 'pointer',
        borderBottom: '1px solid var(--border)',
        transition: 'background .15s',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--surface2)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>

        {/* Left: ticker + name */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            fontSize: 13, fontWeight: 700,
            color: 'var(--ink)', letterSpacing: '0.01em',
            marginBottom: 2,
          }}>
            {item.ticker}
          </p>
          {item.name && (
            <p style={{
              fontSize: 10, color: 'var(--ink4)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {item.name}
            </p>
          )}
        </div>

        {/* Right: price + change */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <p className="num" style={{
            fontSize: 14, fontWeight: 600,
            color: 'var(--ink)', marginBottom: 2,
          }}>
            {typeof item.price === 'number'
              ? item.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: item.price > 100 ? 2 : 4 })
              : '—'
            }
          </p>
          <span className="num" style={{
            fontSize: 11, fontWeight: 500, color: clr,
          }}>
            {(item.change ?? 0) >= 0 ? '+' : ''}{(item.change ?? 0).toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Sparkline */}
      {item.sparkline?.length > 1 && (
        <div style={{ marginTop: 12, height: 36 }}>
          <MarketOverview
            data={item.sparkline}
            color={hex}
            height={36}
          />
        </div>
      )}
    </div>
  );
};