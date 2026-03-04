import React from 'react';

const relTime = (ts) => {
  if (!ts) return '';
  const t = typeof ts === 'string' ? ts : null;
  if (t && isNaN(Number(t))) return t;
  const diff = (Date.now() / 1000) - Number(ts);
  if (diff < 3600)  return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
};

export const NewsItem = ({ title, publisher, time, link }) => (
  <a
    href={link || '#'}
    target="_blank"
    rel="noopener noreferrer"
    style={{
      display: 'block',
      padding: '11px 0',
      borderBottom: '1px solid var(--border)',
      textDecoration: 'none',
      color: 'inherit',
      cursor: link ? 'pointer' : 'default',
    }}
    onMouseEnter={e => {
      e.currentTarget.querySelector('.news-title').style.color = 'var(--ink)';
    }}
    onMouseLeave={e => {
      e.currentTarget.querySelector('.news-title').style.color = 'var(--ink2)';
    }}
  >
    <p
      className="news-title"
      style={{
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1.45,
        color: 'var(--ink2)',
        marginBottom: 5,
        transition: 'color .15s',
        display: '-webkit-box',
        WebkitLineClamp: 2,
        WebkitBoxOrient: 'vertical',
        overflow: 'hidden',
      }}
    >
      {title}
    </p>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      {publisher && (
        <span style={{
          fontSize: 10, fontFamily: 'var(--mono)',
          color: 'var(--ink4)', fontWeight: 400,
        }}>{publisher}</span>
      )}
      {publisher && time && (
        <span style={{ width: 2, height: 2, borderRadius: '50%', background: 'var(--ink5)', flexShrink: 0 }} />
      )}
      {time && (
        <span style={{
          fontSize: 10, fontFamily: 'var(--mono)',
          color: 'var(--ink4)',
        }}>{relTime(time)}</span>
      )}
    </div>
  </a>
);