import React, { createContext, useContext, useState, useEffect } from 'react';

export const ThemeContext = createContext({ theme: 'dark', toggle: () => {} });
export const useTheme = () => useContext(ThemeContext);

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() =>
    typeof window !== 'undefined' ? localStorage.getItem('sb-theme') || 'dark' : 'dark'
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('sb-theme', theme);
  }, [theme]);
  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark');
  return <ThemeContext.Provider value={{ theme, toggle }}>{children}</ThemeContext.Provider>;
};

export const ThemeToggle = () => {
  const { theme, toggle } = useTheme();
  const isDark = theme === 'dark';
  return (
    <button onClick={toggle} title={isDark ? 'Light mode' : 'Dark mode'} style={{
      width:32,height:32,display:'flex',alignItems:'center',justifyContent:'center',
      background:'transparent',border:'1px solid var(--border2)',borderRadius:'var(--radius-sm)',
      cursor:'pointer',color:'var(--ink4)',transition:'border-color .15s, color .15s',flexShrink:0,
    }}
    onMouseEnter={e=>{e.currentTarget.style.borderColor='var(--ink4)';e.currentTarget.style.color='var(--ink2)';}}
    onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--border2)';e.currentTarget.style.color='var(--ink4)';}}>
      {isDark
        ? <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
        : <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      }
    </button>
  );
};

export const FontInjector = () => {
  useEffect(() => {
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }, []);
  return null;
};

export const GlobalStyles = () => (
  <style>{`
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
    ::-webkit-scrollbar{width:3px;height:3px;}
    ::-webkit-scrollbar-track{background:transparent;}
    ::-webkit-scrollbar-thumb{background:var(--border3);border-radius:2px;}
    ::-webkit-scrollbar-thumb:hover{background:var(--ink5);}

    :root,[data-theme="dark"]{
      color-scheme:dark;
      --bg:#060606;--bg2:#0a0a0a;
      --surface:#0f0f0f;--surface2:#161616;--surface3:#1e1e1e;--surface4:#282828;
      --border:rgba(255,255,255,0.055);--border2:rgba(255,255,255,0.095);
      --border3:rgba(255,255,255,0.14);--border4:rgba(255,255,255,0.22);
      --ink:#f2f2f2;--ink2:#9a9a9a;--ink3:#666666;--ink4:#444444;--ink5:#333333;
      --nav-bg:rgba(6,6,6,0.92);
      --shadow-sm:0 1px 2px rgba(0,0,0,0.8);--shadow-md:0 4px 12px rgba(0,0,0,0.7);
      --shadow-lg:0 12px 40px rgba(0,0,0,0.75);--shadow-xl:0 24px 64px rgba(0,0,0,0.8);
      --radius:8px;--radius-sm:4px;--radius-lg:12px;--radius-xl:16px;
      --display:'Cormorant Garamond','Georgia',serif;
      --sans:'DM Sans',-apple-system,sans-serif;
      --mono:'DM Mono','Fira Code',monospace;
      --pos:#22c55e;--pos-soft:#4ade80;--pos-dim:rgba(34,197,94,0.07);--pos-b:rgba(34,197,94,0.14);
      --neg:#ef4444;--neg-soft:#f87171;--neg-dim:rgba(239,68,68,0.07);--neg-b:rgba(239,68,68,0.14);
      --green:var(--pos);--green-dim:var(--pos-dim);--green-b:var(--pos-b);
      --red:var(--neg);--red-dim:var(--neg-dim);--red-b:var(--neg-b);
      --accent:var(--ink2);--accent-soft:var(--ink);
      --accent-dim:rgba(255,255,255,0.04);--accent-border:rgba(255,255,255,0.08);
      --accent-glow:rgba(255,255,255,0.06);
      --blue:var(--ink2);--blue-dim:rgba(255,255,255,0.04);--blue-b:rgba(255,255,255,0.08);
      --purple:var(--ink2);
      --amber:var(--ink);--amber-dim:rgba(255,255,255,0.06);
      --gold:var(--ink);--gold-bg:rgba(255,255,255,0.05);--gold3:var(--border3);
    }

    [data-theme="light"]{
      color-scheme:light;
      --bg:#f8f8f6;--bg2:#f2f2f0;
      --surface:#ffffff;--surface2:#f5f5f3;--surface3:#eeeeec;--surface4:#e5e5e3;
      --border:rgba(0,0,0,0.065);--border2:rgba(0,0,0,0.11);
      --border3:rgba(0,0,0,0.16);--border4:rgba(0,0,0,0.24);
      --ink:#0a0a0a;--ink2:#4a4a4a;--ink3:#6a6a6a;--ink4:#9a9a9a;--ink5:#c8c8c8;
      --nav-bg:rgba(248,248,246,0.94);
      --shadow-sm:0 1px 2px rgba(0,0,0,0.07);--shadow-md:0 4px 12px rgba(0,0,0,0.09);
      --shadow-lg:0 12px 40px rgba(0,0,0,0.11);--shadow-xl:0 24px 64px rgba(0,0,0,0.13);
      --radius:8px;--radius-sm:4px;--radius-lg:12px;--radius-xl:16px;
      --display:'Cormorant Garamond','Georgia',serif;
      --sans:'DM Sans',-apple-system,sans-serif;
      --mono:'DM Mono','Fira Code',monospace;
      --pos:#15803d;--pos-soft:#16a34a;--pos-dim:rgba(21,128,61,0.07);--pos-b:rgba(21,128,61,0.14);
      --neg:#dc2626;--neg-soft:#ef4444;--neg-dim:rgba(220,38,38,0.07);--neg-b:rgba(220,38,38,0.14);
      --green:var(--pos);--green-dim:var(--pos-dim);--green-b:var(--pos-b);
      --red:var(--neg);--red-dim:var(--neg-dim);--red-b:var(--neg-b);
      --accent:var(--ink2);--accent-soft:var(--ink);
      --accent-dim:rgba(0,0,0,0.04);--accent-border:rgba(0,0,0,0.08);--accent-glow:rgba(0,0,0,0.05);
      --blue:var(--ink2);--blue-dim:rgba(0,0,0,0.04);--blue-b:rgba(0,0,0,0.08);
      --purple:var(--ink2);
      --amber:var(--ink);--amber-dim:rgba(0,0,0,0.05);
      --gold:var(--ink);--gold-bg:rgba(0,0,0,0.04);--gold3:var(--border3);
    }

    html{font-size:14px;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility;}
    body{font-family:var(--sans);background:var(--bg);color:var(--ink);min-height:100vh;line-height:1.5;letter-spacing:-0.005em;}

    .num{font-family:var(--mono);font-variant-numeric:tabular-nums;letter-spacing:-0.02em;}
    .display{font-family:var(--display);letter-spacing:-0.02em;line-height:1.1;}

    /* BADGES */
    .badge{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:3px;font-family:var(--mono);font-size:9px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;white-space:nowrap;line-height:1.6;}
    .badge-green{color:var(--pos);background:var(--pos-dim);border:1px solid var(--pos-b);}
    .badge-red{color:var(--neg);background:var(--neg-dim);border:1px solid var(--neg-b);}
    .badge-muted{color:var(--ink4);background:transparent;border:1px solid var(--border2);}
    .badge-accent{color:var(--ink2);background:var(--surface3);border:1px solid var(--border2);}
    .badge-solid{color:var(--bg);background:var(--ink);border:1px solid var(--ink);}
    .badge-amber{color:var(--ink2);background:var(--surface3);border:1px solid var(--border2);}

    /* NAV */
    .nav-bar{position:fixed;top:0;left:0;right:0;z-index:100;height:48px;background:var(--nav-bg);border-bottom:1px solid var(--border2);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);display:flex;align-items:center;padding:0 20px;gap:16px;}
    .nav-bar::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:var(--border3);}

    /* TABS */
    .tab-btn{font-family:var(--mono);font-size:10px;font-weight:400;letter-spacing:0.1em;text-transform:uppercase;color:var(--ink4);padding:5px 10px;border-radius:var(--radius-sm);border:1px solid transparent;cursor:pointer;background:transparent;transition:color .15s,background .15s,border-color .15s;white-space:nowrap;}
    .tab-btn:hover{color:var(--ink2);border-color:var(--border2);}
    .tab-btn.active{color:var(--ink);background:var(--surface3);border-color:var(--border2);}

    /* SECTION TITLE */
    .section-title{font-family:var(--mono);font-size:9px;font-weight:400;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink4);padding-bottom:12px;border-bottom:1px solid var(--border);margin-bottom:16px;}

    /* DATA ROW */
    .data-row{display:flex;justify-content:space-between;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--border);}
    .data-row:last-child{border-bottom:none;}
    .data-label{font-family:var(--mono);font-size:10px;letter-spacing:0.06em;text-transform:uppercase;color:var(--ink4);}
    .data-value{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--ink);text-align:right;font-variant-numeric:tabular-nums;}

    /* DIVIDER */
    .divider{height:1px;background:var(--border);margin:16px 0;border:none;flex-shrink:0;}

    /* INPUT */
    .search-input{width:100%;padding:0 12px;height:36px;background:transparent;border:none;font-size:13px;color:var(--ink);font-family:var(--mono);letter-spacing:0.04em;outline:none;}
    .search-input::placeholder{color:var(--ink5);font-family:var(--mono);}

    /* SEGMENTED CONTROL */
    .seg-control{display:flex;gap:2px;background:var(--surface2);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:2px;}
    .seg-btn{font-family:var(--mono);font-size:9px;font-weight:400;letter-spacing:0.1em;text-transform:uppercase;padding:4px 10px;border-radius:3px;border:none;cursor:pointer;background:transparent;color:var(--ink4);transition:color .12s,background .12s;}
    .seg-btn.active{background:var(--surface4);color:var(--ink);box-shadow:var(--shadow-sm);}
    .seg-btn:hover:not(.active){color:var(--ink2);}

    /* PROGRESS BAR */
    .prog-bar{height:2px;background:var(--surface4);border-radius:1px;overflow:hidden;}
    .prog-fill{height:100%;border-radius:1px;transition:width .8s cubic-bezier(.22,1,.36,1);}

    /* TABLE */
    .aq-table{width:100%;border-collapse:collapse;}
    .aq-table th{font-family:var(--mono);font-size:9px;font-weight:400;letter-spacing:0.14em;text-transform:uppercase;color:var(--ink4);padding:0 12px 10px;border-bottom:1px solid var(--border2);text-align:left;}
    .aq-table td{font-size:12px;font-family:var(--mono);padding:9px 12px;border-bottom:1px solid var(--border);color:var(--ink2);}
    .aq-table tr:last-child td{border-bottom:none;}
    .aq-table tr:hover td{background:var(--surface2);color:var(--ink);}

    /* CHIP */
    .chip{display:inline-flex;align-items:center;gap:5px;padding:3px 8px;border-radius:3px;font-family:var(--mono);font-size:10px;font-weight:400;letter-spacing:0.06em;background:var(--surface3);border:1px solid var(--border2);color:var(--ink3);cursor:default;}

    /* MODAL */
    .modal-backdrop{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;}

    /* STONEBRIDGE PANEL */
    .sb-panel{background:var(--surface);border:1px solid var(--border2);border-radius:var(--radius);overflow:hidden;position:relative;}
    .sb-panel::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:var(--border3);pointer-events:none;}
    .sb-panel-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
    .sb-panel-label{font-family:var(--mono);font-size:8px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink4);margin-bottom:5px;}
    .sb-panel-title{font-family:var(--display);font-size:18px;font-weight:500;color:var(--ink);letter-spacing:-0.01em;line-height:1.2;}

    /* METRIC DISPLAY */
    .sb-metric-value{font-family:var(--display);font-size:32px;font-weight:300;letter-spacing:-0.03em;line-height:1;color:var(--ink);}
    .sb-metric-label{font-family:var(--mono);font-size:8px;letter-spacing:0.16em;text-transform:uppercase;color:var(--ink4);margin-top:6px;}

    /* VERDICT */
    .sb-verdict{font-family:var(--display);font-size:28px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;}
    .sb-verdict.neutral{color:var(--ink2);}
    .sb-verdict.bullish{color:var(--pos);}
    .sb-verdict.bearish{color:var(--neg);}

    /* WORDMARK */
    .sb-wordmark{display:flex;flex-direction:column;gap:0;line-height:1;}
    .sb-wordmark-name{font-family:var(--display);font-size:15px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;color:var(--ink);}
    .sb-wordmark-product{font-family:var(--mono);font-size:7px;letter-spacing:0.22em;text-transform:uppercase;color:var(--ink4);}

    /* SB RULE */
    .sb-rule{display:flex;align-items:center;gap:12px;margin:20px 0;}
    .sb-rule::before{content:'';width:24px;height:1px;background:var(--ink);flex-shrink:0;}
    .sb-rule::after{content:'';flex:1;height:1px;background:var(--border);}
    .sb-rule-label{font-family:var(--mono);font-size:8px;letter-spacing:0.18em;text-transform:uppercase;color:var(--ink4);flex-shrink:0;}

    /* STATUS */
    .sb-status{display:inline-flex;align-items:center;gap:6px;}
    .sb-status-dot{width:5px;height:5px;border-radius:50%;background:var(--pos);flex-shrink:0;}
    .sb-status-dot.live{animation:pulse-live 2s ease infinite;}
    .sb-status-dot.idle{background:var(--ink4);animation:none;}
    .sb-status-text{font-family:var(--mono);font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:var(--ink4);}

    /* BUTTONS */
    .sb-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:8px 18px;border-radius:var(--radius-sm);border:1px solid var(--ink);background:var(--ink);color:var(--bg);font-family:var(--mono);font-size:10px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;transition:opacity .15s,background .15s;white-space:nowrap;}
    .sb-btn:hover{opacity:0.88;}
    .sb-btn:disabled{opacity:0.35;cursor:not-allowed;}
    .sb-btn-ghost{background:transparent;color:var(--ink2);border-color:var(--border2);}
    .sb-btn-ghost:hover{opacity:1;border-color:var(--ink4);color:var(--ink);}

    /* SIGNAL COLORS — ONLY for financial numbers */
    .sig-pos{color:var(--pos)!important;}
    .sig-neg{color:var(--neg)!important;}
    .sig-neu{color:var(--ink2);}

    /* LAYOUT */
    .flex-between{display:flex;justify-content:space-between;align-items:center;}
    .flex-center{display:flex;align-items:center;justify-content:center;}
    .flex-gap-sm{display:flex;align-items:center;gap:8px;}
    .flex-gap-md{display:flex;align-items:center;gap:16px;}

    /* EMPTY STATE */
    .sb-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 24px;text-align:center;gap:10px;}
    .sb-empty-label{font-family:var(--mono);font-size:9px;letter-spacing:0.16em;text-transform:uppercase;color:var(--ink5);}

    /* FOOTNOTE */
    .sb-footnote{font-family:var(--mono);font-size:9px;letter-spacing:0.06em;color:var(--ink5);line-height:1.6;}

    /* ANIMATIONS */
    @keyframes spin{to{transform:rotate(360deg);}}
    .spin-icon{animation:spin 0.8s linear infinite;}

    @keyframes fadeUp{from{opacity:0;transform:translateY(6px);}to{opacity:1;transform:translateY(0);}}
    .fade-up{animation:fadeUp .3s ease forwards;}
    .fade-up-1{animation:fadeUp .3s .05s ease both;}
    .fade-up-2{animation:fadeUp .3s .10s ease both;}
    .fade-up-3{animation:fadeUp .3s .15s ease both;}
    .fade-up-4{animation:fadeUp .3s .20s ease both;}

    @keyframes pulse-live{0%,100%{opacity:1;transform:scale(1);}50%{opacity:0.5;transform:scale(0.85);}}
    .pulse{animation:pulse-live 1.8s ease infinite;}
    .pulse-dot{animation:pulse-live 2s ease infinite;}

    @keyframes shimmer{0%{background-position:-600px 0;}100%{background-position:600px 0;}}
    .skeleton{background:linear-gradient(90deg,var(--surface2) 25%,var(--surface3) 50%,var(--surface2) 75%);background-size:1200px 100%;animation:shimmer 1.6s infinite;border-radius:3px;}

    @keyframes tickerScroll{0%{transform:translateX(0);}100%{transform:translateX(-50%);}}
    .ticker-track{display:flex;gap:36px;white-space:nowrap;will-change:transform;animation:tickerScroll 42s linear infinite;}
    .ticker-track:hover{animation-play-state:paused;}
  `}</style>
);

export const Divider = ({ style } = {}) => <div className="divider" style={style} />;

export const SBRule = ({ label }) => (
  <div className="sb-rule">{label && <span className="sb-rule-label">{label}</span>}</div>
);

export const SBStatus = ({ live = true, label }) => (
  <div className="sb-status">
    <div className={`sb-status-dot ${live ? 'live' : 'idle'}`} />
    {label && <span className="sb-status-text">{label}</span>}
  </div>
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