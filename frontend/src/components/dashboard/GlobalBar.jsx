import React from 'react';

export const GlobalBar = ({ indices }) => {
  if (!indices?.length) return null;
  return (
    <div style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)', height: 40, overflow: 'hidden', position: 'relative' }}>
      <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 90, background: 'linear-gradient(90deg, var(--surface), transparent)', zIndex: 2, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: 90, background: 'linear-gradient(-90deg, var(--surface), transparent)', zIndex: 2, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', left: 20, top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: 6, zIndex: 3 }}>
        <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 8px var(--green)' }} className="pulse-dot" />
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ink3)' }}>LIVE</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', height: '100%', paddingLeft: 80, animation: 'ticker 35s linear infinite', width: 'max-content' }}>
        {[...indices, ...indices].map((idx, i) => {
          const up = (idx.change ?? 0) >= 0;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 28px', height: '100%', borderRight: '1px solid var(--border)', whiteSpace: 'nowrap' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.1em', color: 'var(--ink3)', textTransform: 'uppercase' }}>{idx.name}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600, color: 'var(--ink)', letterSpacing: '-0.01em' }}>{idx.price?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10, fontWeight: 500, color: up ? 'var(--green)' : 'var(--red)' }}>{up ? '▲' : '▼'} {Math.abs(idx.change ?? 0).toFixed(2)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};