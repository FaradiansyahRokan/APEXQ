import React from 'react';

export const Label = ({ children, style: sx, className = '', size = 'sm' }) => {
  const sizes = {
    xs: { fontSize: 8,  letterSpacing: '0.14em' },
    sm: { fontSize: 9,  letterSpacing: '0.12em' },
    md: { fontSize: 10, letterSpacing: '0.10em' },
  };
  const s = sizes[size] || sizes.sm;
  return (
    <p
      className={className}
      style={{
        fontFamily: 'var(--mono)',
        fontWeight: 400,
        textTransform: 'uppercase',
        color: 'var(--ink4)',
        lineHeight: 1,
        ...s,
        ...sx,
      }}
    >
      {children}
    </p>
  );
};