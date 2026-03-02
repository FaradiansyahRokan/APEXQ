import React from 'react';

const timeAgo = (ts) => {
  if (!ts) return '';
  const t = typeof ts === 'string' ? ts : null;
  if (t && isNaN(Number(t))) return t;
  const diff = (Date.now() / 1000) - Number(ts);
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};

export const NewsItem = ({ title, publisher, time, link }) => (
  <a href={link} target="_blank" rel="noopener noreferrer">
    <div style={{
      padding: '13px 0', borderBottom: '1px solid var(--border)',
      transition: 'padding-left .15s ease', cursor: 'pointer',
    }}
    onMouseEnter={e => {
      e.currentTarget.style.paddingLeft = '10px';
      e.currentTarget.style.borderLeft = '2px solid var(--gold)';
      e.currentTarget.style.marginLeft = '-2px';
    }}
    onMouseLeave={e => {
      e.currentTarget.style.paddingLeft = '0';
      e.currentTarget.style.borderLeft = 'none';
      e.currentTarget.style.marginLeft = '0';
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5, gap: 12 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 500, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--gold)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 140 }}>{publisher}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink3)', whiteSpace: 'nowrap' }}>{timeAgo(time)}</span>
      </div>
      <p style={{ fontSize: 12, fontWeight: 400, lineHeight: 1.6, color: 'var(--ink2)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{title}</p>
    </div>
  </a>
);