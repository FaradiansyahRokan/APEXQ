import React from 'react';
export const IndicatorButton = ({ label, active, color, onClick }) => {
  const c = color === 'blue' ? '#5EA0F5' : color === 'orange' ? '#F0A030' : color === 'gold' ? '#C9A96E' : 'var(--ink2)';
  return (
    <button onClick={onClick} style={{
      background: active ? `${c}12` : 'transparent',
      border: `1px solid ${active ? `${c}40` : 'transparent'}`,
      borderRadius: 5, padding: '4px 11px',
      fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 500 : 400,
      letterSpacing: '0.1em', textTransform: 'uppercase',
      color: active ? c : 'var(--ink3)',
      transition: 'all .15s ease', whiteSpace: 'nowrap',
    }}
    onMouseEnter={e => { if (!active) e.currentTarget.style.color = 'var(--ink2)'; }}
    onMouseLeave={e => { if (!active) e.currentTarget.style.color = 'var(--ink3)'; }}
    >{label}</button>
  );
};