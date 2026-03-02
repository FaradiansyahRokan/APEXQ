import React from 'react';
export const Label = ({ children, style: sx, className = '' }) => (
  <p style={{ fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 400, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', ...sx }} className={className}>
    {children}
  </p>
);