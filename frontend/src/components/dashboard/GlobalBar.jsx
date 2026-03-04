import React from 'react';

export const GlobalBar = ({ indices }) => {
  if (!indices?.length) return null;

  return (
    <div style={{
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      height: 38,
      overflow: 'hidden',
      position: 'relative',
    }}>
      {/* Left fade */}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0, width: 60,
        background: 'linear-gradient(90deg, var(--surface), transparent)',
        zIndex: 2, pointerEvents: 'none',
      }} />
      {/* Right fade */}
      <div style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: 60,
        background: 'linear-gradient(-90deg, var(--surface), transparent)',
        zIndex: 2, pointerEvents: 'none',
      }} />

      <div className="ticker-track" style={{ height: '100%', alignItems: 'center' }}>
        {[...indices, ...indices].map((idx, i) => {
          const up    = (idx.change ?? 0) >= 0;
          const clr   = up ? 'var(--pos)' : 'var(--neg)';
          const sign  = up ? '+' : '';
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
              <span style={{
                fontSize: 11, fontWeight: 600,
                color: 'var(--ink)', letterSpacing: '0.01em',
              }}>
                {idx.name}
              </span>
              <span className="num" style={{ fontSize: 11, color: 'var(--ink2)' }}>
                {idx.price?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="num" style={{ fontSize: 10, color: clr, fontWeight: 500 }}>
                {sign}{(idx.change ?? 0).toFixed(2)}%
              </span>
              <span style={{ opacity: 0.18, fontSize: 10 }}>·</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};