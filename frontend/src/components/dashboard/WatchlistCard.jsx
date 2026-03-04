import React, { useRef, useEffect, useState } from 'react';

// ── Sparkline — amplified range ado naik turun lebih kerasa ─────────────────
const Sparkline = ({ data, color, height = 52 }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data?.length) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const W   = canvas.offsetWidth;
    const H   = height;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    const vals   = data.map(d => typeof d === 'object' ? d.value : d);
    const rawMin = Math.min(...vals);
    const rawMax = Math.max(...vals);
    const mid    = (rawMin + rawMax) / 2;
    const range  = rawMax - rawMin || 1;

    // Amplify 1.6x around midpoint — lebih dramatis tapi tidak palsu
    const AMPLIFY = 1.6;
    const min  = mid - (range / 2) * AMPLIFY;
    const max  = mid + (range / 2) * AMPLIFY;
    const span = max - min;

    const padT = 5;
    const padB = 5;

    const x = i => (i / (vals.length - 1)) * W;
    const y = v => H - padB - ((v - min) / span) * (H - padT - padB);

    // Gradient fill
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0,   color + '50');
    grad.addColorStop(0.5, color + '20');
    grad.addColorStop(1,   color + '00');
    ctx.beginPath();
    ctx.moveTo(x(0), y(vals[0]));
    for (let i = 1; i < vals.length; i++) {
      const cpx = (x(i - 1) + x(i)) / 2;
      ctx.bezierCurveTo(cpx, y(vals[i - 1]), cpx, y(vals[i]), x(i), y(vals[i]));
    }
    ctx.lineTo(x(vals.length - 1), H);
    ctx.lineTo(x(0), H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Glow layer
    ctx.beginPath();
    ctx.moveTo(x(0), y(vals[0]));
    for (let i = 1; i < vals.length; i++) {
      const cpx = (x(i - 1) + x(i)) / 2;
      ctx.bezierCurveTo(cpx, y(vals[i - 1]), cpx, y(vals[i]), x(i), y(vals[i]));
    }
    ctx.strokeStyle = color + '35';
    ctx.lineWidth   = 5;
    ctx.stroke();

    // Main line
    ctx.beginPath();
    ctx.moveTo(x(0), y(vals[0]));
    for (let i = 1; i < vals.length; i++) {
      const cpx = (x(i - 1) + x(i)) / 2;
      ctx.bezierCurveTo(cpx, y(vals[i - 1]), cpx, y(vals[i]), x(i), y(vals[i]));
    }
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.75;
    ctx.stroke();

    // End dot
    const ex = x(vals.length - 1);
    const ey = y(vals[vals.length - 1]);
    ctx.beginPath();
    ctx.arc(ex, ey, 5, 0, Math.PI * 2);
    ctx.fillStyle = color + '28';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(ex, ey, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

  }, [data, color, height]);

  return <canvas ref={canvasRef} style={{ width: '100%', height, display: 'block' }} />;
};

// ── Volume bars ───────────────────────────────────────────────────────────────
const VolumeBar = ({ data, color }) => {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data?.length) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const W   = canvas.offsetWidth;
    const H   = canvas.offsetHeight;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);
    const vols = data.map(d => typeof d === 'object' ? (d.volume ?? 0) : 0);
    const maxV = Math.max(...vols, 1);
    const bw   = W / vols.length;
    vols.forEach((v, i) => {
      const bh = (v / maxV) * H;
      ctx.fillStyle = color + '45';
      ctx.fillRect(i * bw + 0.5, H - bh, bw - 1, bh);
    });
  }, [data, color]);
  return <canvas ref={canvasRef} style={{ width: '100%', height: 14, display: 'block' }} />;
};

// ── Momentum bar ──────────────────────────────────────────────────────────────
const MomentumBar = ({ change }) => {
  const abs = Math.abs(change ?? 0);
  const pct = Math.min(abs / 5 * 100, 100);
  const col = (change ?? 0) >= 0 ? '#22c55e' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 7.5, letterSpacing: '0.09em',
        textTransform: 'uppercase', color: 'var(--ink4)', flexShrink: 0,
      }}>MOM</span>
      <div style={{ flex: 1, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`, background: col, borderRadius: 2,
          transition: 'width 0.8s cubic-bezier(.22,1,.36,1)',
          boxShadow: `0 0 5px ${col}80`,
        }} />
      </div>
    </div>
  );
};

// ── Main Card ─────────────────────────────────────────────────────────────────
export const WatchlistCard = ({ item, onClick, isActive }) => {
  const [hovered, setHovered] = useState(false);

  const up     = (item.change ?? 0) >= 0;
  const hex    = up ? '#22c55e' : '#ef4444';
  const absChg = Math.abs(item.change ?? 0);

  const formatPrice = (p) => {
    if (typeof p !== 'number') return '—';
    if (p >= 1000) return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (p >= 1)    return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    return p.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 6 });
  };

  const ohlc = {
    open : item.open  ?? item.o ?? null,
    high : item.high  ?? item.h ?? null,
    low  : item.low   ?? item.l ?? null,
    close: item.close ?? item.c ?? item.price ?? null,
  };
  const hasOHLC     = ohlc.open !== null || ohlc.high !== null;
  const hasVolume   = item.sparkline?.some(d => d?.volume > 0);
  const hasSparkline = item.sparkline?.length > 1;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position    : 'relative',
        padding     : '12px 16px 0',
        cursor      : 'pointer',
        borderBottom: '1px solid var(--border)',
        background  : isActive
          ? 'linear-gradient(90deg, rgba(212,175,55,0.07) 0%, var(--surface2) 100%)'
          : hovered ? 'var(--surface2)' : 'transparent',
        transition  : 'background 0.15s ease',
        overflow    : 'hidden',
      }}
    >
      {/* Active left accent */}
      {isActive && (
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: 2, background: 'var(--gold)',
        }} />
      )}

      {/* ── Row 1: ticker + price ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{
              fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700,
              color: isActive ? 'var(--gold)' : 'var(--ink)', letterSpacing: '0.04em',
            }}>
              {item.ticker}
            </span>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 2,
              padding: '1px 5px', borderRadius: 4,
              fontSize: 9, fontWeight: 600, fontFamily: 'var(--mono)',
              color: hex, background: hex + '18', border: `1px solid ${hex}28`,
            }}>
              {up ? '▲' : '▼'} {absChg.toFixed(2)}%
            </span>
          </div>
          {item.name && (
            <p style={{ fontSize: 9, color: 'var(--ink4)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {item.name}
            </p>
          )}
        </div>

        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <p style={{
            fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600,
            color: 'var(--ink)', letterSpacing: '-0.01em',
          }}>
            {formatPrice(item.price)}
          </p>
        </div>
      </div>

      {/* ── Momentum bar ── */}
      <div style={{ marginBottom: 7 }}>
        <MomentumBar change={item.change} />
      </div>

      {/* ── Sparkline (edge to edge) ── */}
      {hasSparkline && (
        <div style={{
          marginLeft: -16, marginRight: -16,
          opacity: hovered ? 1 : 0.82,
          transition: 'opacity 0.2s',
        }}>
          <Sparkline data={item.sparkline} color={hex} height={52} />
          {hasVolume && <VolumeBar data={item.sparkline} color={hex} />}
        </div>
      )}

      {/* ── OHLC — below chart, flush to edges ── */}
      {hasOHLC && (
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 1, marginLeft: -16, marginRight: -16,
          background: 'var(--border)',
          borderTop: hasSparkline ? 'none' : '1px solid var(--border)',
        }}>
          {[
            { label: 'OPEN',  value: ohlc.open,  color: 'var(--ink2)'  },
            { label: 'HIGH',  value: ohlc.high,  color: '#22c55e'       },
            { label: 'LOW',   value: ohlc.low,   color: '#ef4444'       },
            { label: 'CLOSE', value: ohlc.close, color: 'var(--ink)'    },
          ].map(({ label, value, color }) => (
            <div key={label} style={{
              background: 'var(--surface)',
              padding: '6px 0',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
            }}>
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 7, letterSpacing: '0.12em',
                textTransform: 'uppercase', color: 'var(--ink4)',
              }}>
                {label}
              </span>
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 9.5, fontWeight: 600,
                color, letterSpacing: '-0.01em',
              }}>
                {typeof value === 'number'
                  ? value >= 1000
                    ? value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : value.toFixed(value >= 1 ? 2 : 4)
                  : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};