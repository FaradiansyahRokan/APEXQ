import React, { useEffect } from 'react';

export const FontInjector = () => {
  useEffect(() => {
    const link = document.createElement('link');
    link.href = 'https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@300;400;500;600&display=swap';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }, []);
  return null;
};

export const GlobalStyles = () => (
  <style>{`
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    :root{
      --bg:#04040A;--surface:#08080F;--surface2:#0D0D18;--surface3:#131322;
      --glass:rgba(255,255,255,0.02);--glass2:rgba(255,255,255,0.035);
      --border:rgba(255,255,255,0.05);--border2:rgba(255,255,255,0.09);--border3:rgba(255,255,255,0.15);
      --gold:#C9A96E;--gold2:#E4CE9E;--gold3:#7A5A28;
      --gold-bg:rgba(201,169,110,0.07);--gold-glow:rgba(201,169,110,0.2);
      --ink:#EDEEF5;--ink2:#9595A8;--ink3:#52526A;--ink4:#222235;
      --green:#24D26D;--green-dim:rgba(36,210,109,0.08);--green-b:rgba(36,210,109,0.22);
      --red:#F03D5F;--red-dim:rgba(240,61,95,0.08);--red-b:rgba(240,61,95,0.22);
      --blue:#5EA0F5;--blue-dim:rgba(94,160,245,0.08);
      --purple:#9B7FF5;--amber:#F0A030;
      --font:'Syne',-apple-system,sans-serif;
      --mono:'IBM Plex Mono','SF Mono',monospace;
    }
    html,body{background:var(--bg);color:var(--ink);font-family:var(--font);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
    ::selection{background:var(--gold);color:#000}
    ::-webkit-scrollbar{width:2px;height:2px}
    ::-webkit-scrollbar-track{background:transparent}
    ::-webkit-scrollbar-thumb{background:var(--border3);border-radius:2px}
    @keyframes fadeUp{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:translateY(0)}}
    @keyframes fadeIn{from{opacity:0}to{opacity:1}}
    @keyframes spin{to{transform:rotate(360deg)}}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.28}}
    @keyframes ticker{from{transform:translateX(0)}to{transform:translateX(-50%)}}
    @keyframes shimmer{0%{background-position:-400px 0}100%{background-position:400px 0}}
    .anim{animation:fadeUp .5s cubic-bezier(.22,1,.36,1) both}
    .anim-f{animation:fadeIn .35s ease both}
    .d1{animation-delay:.07s}.d2{animation-delay:.15s}.d3{animation-delay:.23s}.d4{animation-delay:.31s}.d5{animation-delay:.40s}
    .spin-icon{animation:spin .8s linear infinite}
    .pulse-dot{animation:pulse 2.2s ease-in-out infinite}
    .pulse-anim{animation:pulse 1.8s ease-in-out infinite}
    .scrollbar-hide{scrollbar-width:none}
    .scrollbar-hide::-webkit-scrollbar{display:none}
    .card{background:var(--surface);border:1px solid var(--border);border-radius:14px;position:relative;overflow:hidden;transition:border-color .2s ease}
    .card::before{content:'';position:absolute;inset:0;background:linear-gradient(145deg,rgba(255,255,255,.012) 0%,transparent 55%);pointer-events:none;border-radius:inherit}
    .card:hover{border-color:var(--border2)}
    .card-gold{border-color:rgba(201,169,110,.18);background:linear-gradient(145deg,rgba(201,169,110,.035) 0%,var(--surface) 50%)}
    .shimmer{background:linear-gradient(90deg,var(--surface2) 0%,var(--surface3) 40%,var(--surface2) 80%);background-size:400px 100%;animation:shimmer 2s infinite}
    .badge{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:4px;font-family:var(--mono);font-size:9px;font-weight:500;letter-spacing:.1em;text-transform:uppercase}
    .badge-green{background:var(--green-dim);color:var(--green);border:1px solid var(--green-b)}
    .badge-red{background:var(--red-dim);color:var(--red);border:1px solid var(--red-b)}
    .badge-gold{background:var(--gold-bg);color:var(--gold);border:1px solid rgba(201,169,110,.25)}
    .badge-blue{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(94,160,245,.22)}
    .badge-purple{background:rgba(155,127,245,.08);color:var(--purple);border:1px solid rgba(155,127,245,.22)}
    .badge-muted{background:var(--glass2);color:var(--ink3);border:1px solid var(--border)}
    .mono-label{font-family:var(--mono);font-size:9px;font-weight:400;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3)}
    button{cursor:pointer;font-family:var(--font)}
    a{text-decoration:none;color:inherit}
    input::placeholder{color:var(--ink4)}
    input:focus{outline:none}
    .gold-rule{height:1px;background:linear-gradient(90deg,transparent,var(--gold3),transparent)}
    .border-rule{height:1px;background:var(--border)}
    @keyframes countUp{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
    .num-anim{animation:countUp .28s ease}
  `}</style>
);

export const Divider = ({ style: sx }) => (
  <div style={{ height: 1, background: 'var(--border)', ...sx }} />
);

export const formatPrice = (v, c) =>
  new Intl.NumberFormat(
    c === 'IDR' || c === 'id-ID' ? 'id-ID' : 'en-US',
    { style: 'currency', currency: c || 'USD', minimumFractionDigits: c === 'IDR' ? 0 : 2 }
  ).format(v);