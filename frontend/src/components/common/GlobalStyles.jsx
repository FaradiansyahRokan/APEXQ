import React, { createContext, useContext, useState, useEffect } from 'react';

// ─────────────────────────────────────────────────────────────────
//  Theme Context
// ─────────────────────────────────────────────────────────────────
export const ThemeContext = createContext({ theme: 'dark', toggle: () => {} });
export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() =>
    typeof window !== 'undefined'
      ? localStorage.getItem('aq-theme') || 'dark'
      : 'dark'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('aq-theme', theme);
  }, [theme]);

  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
};

// ─────────────────────────────────────────────────────────────────
//  Theme Toggle
// ─────────────────────────────────────────────────────────────────
export const ThemeToggle = () => {
  const { theme, toggle } = useTheme();
  const isDark = theme === 'dark';
  return (
    <button
      onClick={toggle}
      title={isDark ? 'Light mode' : 'Dark mode'}
      style={{
        width: 34, height: 34,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'transparent',
        border: '1px solid var(--border)',
        borderRadius: 8,
        cursor: 'pointer',
        color: 'var(--ink3)',
        transition: 'border-color .2s, color .2s',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = 'var(--ink3)';
        e.currentTarget.style.color = 'var(--ink)';
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.color = 'var(--ink3)';
      }}
    >
      {isDark ? (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      ) : (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
    </button>
  );
};

// ─────────────────────────────────────────────────────────────────
//  Font Injector
// ─────────────────────────────────────────────────────────────────
export const FontInjector = () => {
  useEffect(() => {
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@300;400;500&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }, []);
  return null;
};

// ─────────────────────────────────────────────────────────────────
//  Global Styles — Premium B&W with pos/neg financial signals
// ─────────────────────────────────────────────────────────────────
export const GlobalStyles = () => (
  <style>{`
    /* ── Reset ─────────────────────────────────────────────── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    /* Remove scrollbar */
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--ink4); }

    /* ══════════════════════════════════════════════════════
       DARK THEME
    ══════════════════════════════════════════════════════ */
    :root, [data-theme="dark"] {
      color-scheme: dark;

      /* ── Backgrounds — deep obsidian scale */
      --bg:       #080808;
      --bg2:      #0c0c0c;
      --surface:  #111111;
      --surface2: #181818;
      --surface3: #222222;
      --surface4: #2e2e2e;

      /* ── Borders — pure white at low opacity */
      --border:  rgba(255,255,255,0.06);
      --border2: rgba(255,255,255,0.10);
      --border3: rgba(255,255,255,0.16);

      /* ── Ink — pure white hierarchy */
      --ink:  #f5f5f5;
      --ink2: #a3a3a3;
      --ink3: #737373;
      --ink4: #525252;
      --ink5: #3d3d3d;

      /* ── Nav */
      --nav-bg: rgba(8,8,8,0.88);

      /* ── Shadows */
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.6);
      --shadow-md: 0 4px 16px rgba(0,0,0,0.6);
      --shadow-lg: 0 8px 32px rgba(0,0,0,0.65);

      /* ── Tokens */
      --radius:    10px;
      --radius-sm: 6px;
      --radius-lg: 14px;
      --sans: 'Inter', -apple-system, sans-serif;
      --mono: 'JetBrains Mono', 'Fira Code', monospace;

      /* ── Financial signals — fixed (never change with theme) */
      --pos:      #22c55e;
      --pos-soft: #4ade80;
      --pos-dim:  rgba(34,197,94,0.08);
      --pos-b:    rgba(34,197,94,0.16);
      --neg:      #ef4444;
      --neg-soft: #f87171;
      --neg-dim:  rgba(239,68,68,0.08);
      --neg-b:    rgba(239,68,68,0.16);

      /* ── Legacy aliases (so old components don't break) */
      --green:     var(--pos); --green-dim: var(--pos-dim); --green-b: var(--pos-b);
      --red:       var(--neg); --red-dim:   var(--neg-dim); --red-b:   var(--neg-b);
      --accent:        var(--ink2);
      --accent-soft:   var(--ink);
      --accent-dim:    rgba(255,255,255,0.05);
      --accent-border: rgba(255,255,255,0.09);
      --accent-glow:   rgba(255,255,255,0.08);
      --blue:   var(--ink2); --blue-dim: rgba(255,255,255,0.05); --blue-b: rgba(255,255,255,0.09);
      --purple: var(--ink2);
      --amber:  #d4a843;
      --amber-dim: rgba(212,168,67,0.10);
      --gold:   var(--amber); --gold-bg: var(--amber-dim);
    }

    /* ══════════════════════════════════════════════════════
       LIGHT THEME
    ══════════════════════════════════════════════════════ */
    [data-theme="light"] {
      color-scheme: light;

      --bg:       #fafafa;
      --bg2:      #f5f5f5;
      --surface:  #ffffff;
      --surface2: #f5f5f5;
      --surface3: #ebebeb;
      --surface4: #e0e0e0;

      --border:  rgba(0,0,0,0.07);
      --border2: rgba(0,0,0,0.12);
      --border3: rgba(0,0,0,0.18);

      --ink:  #0a0a0a;
      --ink2: #525252;
      --ink3: #737373;
      --ink4: #a3a3a3;
      --ink5: #d4d4d4;

      --nav-bg: rgba(250,250,250,0.88);

      --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
      --shadow-md: 0 4px 16px rgba(0,0,0,0.10);
      --shadow-lg: 0 8px 32px rgba(0,0,0,0.12);

      --radius:    10px; --radius-sm: 6px; --radius-lg: 14px;
      --sans: 'Inter', -apple-system, sans-serif;
      --mono: 'JetBrains Mono', 'Fira Code', monospace;

      --pos:      #16a34a; --pos-soft: #22c55e;
      --pos-dim:  rgba(22,163,74,0.08); --pos-b: rgba(22,163,74,0.15);
      --neg:      #dc2626; --neg-soft: #ef4444;
      --neg-dim:  rgba(220,38,38,0.08); --neg-b: rgba(220,38,38,0.15);

      --green:  var(--pos); --green-dim: var(--pos-dim); --green-b: var(--pos-b);
      --red:    var(--neg); --red-dim:   var(--neg-dim); --red-b:   var(--neg-b);
      --accent:        var(--ink2);
      --accent-soft:   var(--ink);
      --accent-dim:    rgba(0,0,0,0.04);
      --accent-border: rgba(0,0,0,0.09);
      --accent-glow:   rgba(0,0,0,0.06);
      --blue:   var(--ink2); --blue-dim: rgba(0,0,0,0.04); --blue-b: rgba(0,0,0,0.09);
      --purple: var(--ink2);
      --amber:  #b45309;
      --amber-dim: rgba(180,83,9,0.10);
      --gold:   var(--amber); --gold-bg: var(--amber-dim);
    }

    /* ── Base ──────────────────────────────────────────────── */
    html { font-size: 14px; -webkit-font-smoothing: antialiased; }
    body {
      font-family: var(--sans);
      font-weight: 400;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
      overflow-x: hidden;
    }
    a { color: inherit; text-decoration: none; }
    button { font-family: var(--sans); background: none; border: none; cursor: pointer; }
    input, textarea { font-family: var(--sans); }

    /* ── Mono numbers ─────────────────────────────────────── */
    .num { font-family: var(--mono); font-variant-numeric: tabular-nums; }

    /* ── Card ─────────────────────────────────────────────── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      transition: border-color .2s;
    }
    .card:hover { border-color: var(--border2); }

    /* ── Badges ───────────────────────────────────────────── */
    .badge {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 2px 7px;
      font-family: var(--mono); font-size: 10px; font-weight: 500;
      letter-spacing: 0.08em; text-transform: uppercase;
      border-radius: 4px; white-space: nowrap;
    }
    .badge-green  { color: var(--pos);  background: var(--pos-dim);  border: 1px solid var(--pos-b); }
    .badge-red    { color: var(--neg);  background: var(--neg-dim);  border: 1px solid var(--neg-b); }
    .badge-muted  { color: var(--ink3); background: var(--surface3); border: 1px solid var(--border); }
    .badge-accent { color: var(--ink);  background: var(--surface2); border: 1px solid var(--border2); }
    .badge-amber  { color: var(--amber); background: var(--amber-dim); border: 1px solid rgba(212,168,67,0.2); }

    /* ── Divider ──────────────────────────────────────────── */
    .divider {
      height: 1px; background: var(--border);
      margin: 16px 0; border: none; flex-shrink: 0;
    }

    /* ── Spin animation ───────────────────────────────────── */
    @keyframes spin { to { transform: rotate(360deg); } }
    .spin-icon { animation: spin 0.9s linear infinite; }

    /* ── Fade-in ──────────────────────────────────────────── */
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .fade-up { animation: fadeUp .35s ease forwards; }

    /* ── Pulse ───────────────────────────────────────────── */
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
    .pulse { animation: pulse 2s ease infinite; }

    /* ── Ticker scroll ────────────────────────────────────── */
    @keyframes tickerScroll {
      0%   { transform: translateX(0); }
      100% { transform: translateX(-50%); }
    }
    .ticker-track {
      display: flex; gap: 32px;
      white-space: nowrap; will-change: transform;
      animation: tickerScroll 38s linear infinite;
    }
    .ticker-track:hover { animation-play-state: paused; }

    /* ── Sidebar section ──────────────────────────────────── */
    .section-title {
      font-family: var(--mono);
      font-size: 9px; font-weight: 500;
      letter-spacing: 0.14em; text-transform: uppercase;
      color: var(--ink4);
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 14px;
    }

    /* ── Data row ─────────────────────────────────────────── */
    .data-row {
      display: flex; justify-content: space-between; align-items: flex-start;
      padding: 7px 0;
      border-bottom: 1px solid var(--border);
    }
    .data-row:last-child { border-bottom: none; }
    .data-label {
      font-size: 11px; color: var(--ink3); flex: 1;
    }
    .data-value {
      font-family: var(--mono); font-size: 11px; font-weight: 500;
      color: var(--ink); text-align: right;
    }

    /* ── Nav bar ─────────────────────────────────────────── */
    .nav-bar {
      position: fixed; top: 0; left: 0; right: 0; z-index: 100;
      height: 52px;
      background: var(--nav-bg);
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      display: flex; align-items: center;
      padding: 0 20px; gap: 16px;
    }

    /* ── Tab button ──────────────────────────────────────── */
    .tab-btn {
      font-size: 12px; font-weight: 500;
      color: var(--ink3);
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      cursor: pointer; background: transparent;
      transition: color .2s, background .2s, border-color .2s;
      white-space: nowrap;
    }
    .tab-btn:hover { color: var(--ink); background: var(--surface2); }
    .tab-btn.active {
      color: var(--ink);
      background: var(--surface2);
      border-color: var(--border2);
    }

    /* ── Input ───────────────────────────────────────────── */
    .search-input {
      width: 100%; padding: 0 12px;
      height: 34px;
      background: transparent;
      border: none;
      font-size: 13px; color: var(--ink);
      font-family: var(--sans);
      outline: none;
    }
    .search-input::placeholder { color: var(--ink4); }

    /* ── Segmented control ───────────────────────────────── */
    .seg-control {
      display: flex; gap: 3px;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 3px;
    }
    .seg-btn {
      font-family: var(--mono); font-size: 10px; font-weight: 500;
      letter-spacing: 0.06em; text-transform: uppercase;
      padding: 4px 10px; border-radius: 4px;
      border: none; cursor: pointer; background: transparent;
      color: var(--ink3);
      transition: color .15s, background .15s;
    }
    .seg-btn.active {
      background: var(--surface);
      color: var(--ink);
      box-shadow: var(--shadow-sm);
    }
    .seg-btn:hover:not(.active) { color: var(--ink2); }

    /* ── Progress bar ─────────────────────────────────────── */
    .prog-bar {
      height: 2px; background: var(--surface3); border-radius: 2px; overflow: hidden;
    }
    .prog-fill {
      height: 100%; border-radius: 2px; transition: width .8s cubic-bezier(.22,1,.36,1);
    }

    /* ── Table ───────────────────────────────────────────── */
    .aq-table { width: 100%; border-collapse: collapse; }
    .aq-table th {
      font-family: var(--mono); font-size: 9px; font-weight: 500;
      letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--ink4); padding: 0 12px 10px;
      border-bottom: 1px solid var(--border); text-align: left;
    }
    .aq-table td {
      font-size: 12px; padding: 10px 12px;
      border-bottom: 1px solid var(--border);
    }
    .aq-table tr:last-child td { border-bottom: none; }
    .aq-table tr:hover td { background: var(--surface2); }

    /* ── Backdrop for modals ─────────────────────────────── */
    .modal-backdrop {
      position: fixed; inset: 0; z-index: 200;
      background: rgba(0,0,0,0.6);
      backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
    }

    /* ── Chip ─────────────────────────────────────────────── */
    .chip {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 3px 9px; border-radius: 20px;
      font-size: 11px; font-weight: 500;
      background: var(--surface3);
      border: 1px solid var(--border);
      color: var(--ink2);
      cursor: default;
    }

    /* ── Skeleton loading ─────────────────────────────────── */
    @keyframes shimmer {
      0%   { background-position: -400px 0; }
      100% { background-position:  400px 0; }
    }
    .skeleton {
      background: linear-gradient(90deg,
        var(--surface2) 25%, var(--surface3) 50%, var(--surface2) 75%
      );
      background-size: 800px 100%;
      animation: shimmer 1.4s infinite;
      border-radius: 4px;
    }
  `}</style>
);

// ─────────────────────────────────────────────────────────────────
//  Utility Helpers
// ─────────────────────────────────────────────────────────────────
export const Divider = ({ style } = {}) => (
  <div className="divider" style={style} />
);

export const formatPrice = (price, currency = 'USD') => {
  if (price === null || price === undefined || isNaN(price)) return '—';
  const absPrice = Math.abs(price);
  const sym = currency === 'IDR' ? 'Rp ' : currency === 'USD' ? '$' : '';
  if (absPrice >= 1000) return `${sym}${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (absPrice >= 1)    return `${sym}${price.toFixed(2)}`;
  if (absPrice >= 0.01) return `${sym}${price.toFixed(4)}`;
  return `${sym}${price.toFixed(6)}`;
};

export const formatChange = (change) => {
  if (change === null || change === undefined || isNaN(change)) return { text: '—', color: 'var(--ink3)' };
  const text  = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
  const color = change > 0 ? 'var(--pos)' : change < 0 ? 'var(--neg)' : 'var(--ink3)';
  return { text, color };
};