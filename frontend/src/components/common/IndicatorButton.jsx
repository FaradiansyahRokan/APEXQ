import React from 'react';

export const IndicatorButton = ({ label, active, onClick, color }) => (
  <button
    onClick={onClick}
    style={{
      padding: '5px 10px',
      borderRadius: 'var(--radius-sm)',
      border: `1px solid ${active ? 'var(--border2)' : 'var(--border)'}`,
      background: active ? 'var(--surface3)' : 'transparent',
      color: active ? 'var(--ink)' : 'var(--ink3)',
      fontFamily: 'var(--mono)',
      fontSize: 10,
      fontWeight: 500,
      letterSpacing: '0.07em',
      textTransform: 'uppercase',
      cursor: 'pointer',
      transition: 'all .15s',
    }}
    onMouseEnter={e => {
      if (!active) {
        e.currentTarget.style.borderColor = 'var(--border2)';
        e.currentTarget.style.color = 'var(--ink2)';
      }
    }}
    onMouseLeave={e => {
      if (!active) {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.color = 'var(--ink3)';
      }
    }}
  >
    {label}
  </button>
);