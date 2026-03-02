import React, { useState, useCallback } from 'react';

const API = "http://localhost:8001";

// ─────────────────────────────────────────────────────────────────
//  INTERNAL SUB-COMPONENTS
// ─────────────────────────────────────────────────────────────────

const Spinner = ({ size = 16, color = 'var(--gold)' }) => (
  <div style={{
    width: size, height: size, flexShrink: 0,
    border: `1.5px solid var(--border2)`,
    borderTopColor: color, borderRadius: '50%',
  }} className="spin-icon" />
);

/** Score bar visual — shows fill % with gradient */
const ScoreBar = ({ score }) => {
  const color = score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--gold)' : 'var(--red)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 110 }}>
      <div style={{
        flex: 1, height: 4, background: 'var(--surface3)',
        borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', width: `${score}%`,
          background: color, borderRadius: 4,
          transition: 'width 0.8s cubic-bezier(.22,1,.36,1)',
          boxShadow: `0 0 6px ${color}55`,
        }} />
      </div>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 700,
        color, letterSpacing: '-0.01em', minWidth: 30, textAlign: 'right',
        fontVariantNumeric: 'tabular-nums',
      }}>{score}</span>
    </div>
  );
};

/** One dimension chip (sortino / regime / momentum / zscore / vol) */
const DimChip = ({ label, pts, max }) => {
  const ratio = pts / max;
  const color = ratio >= 0.7 ? 'var(--green)' : ratio >= 0.4 ? 'var(--gold)' : 'var(--red)';
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
      padding: '6px 8px', background: 'var(--surface3)',
      borderRadius: 6, minWidth: 46,
    }}>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 7, letterSpacing: '0.1em',
        textTransform: 'uppercase', color: 'var(--ink3)',
      }}>{label}</span>
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 11, fontWeight: 600,
        color, lineHeight: 1,
      }}>{pts}/{max}</span>
    </div>
  );
};

/** Status badge pill */
const StatusBadge = ({ status }) => {
  const map = {
    SATIN_READY: { cls: 'badge-green', label: 'READY' },
    MARGINAL:    { cls: 'badge-gold',  label: 'MARGINAL' },
    REJECTED:    { cls: 'badge-red',   label: 'REJECT' },
  };
  const cfg = map[status] || { cls: 'badge-muted', label: status };
  return <span className={`badge ${cfg.cls}`}>{cfg.label}</span>;
};

/** Market tag */
const MktTag = ({ market }) => {
  const map = {
    IDX:    { cls: 'badge-blue',   label: 'IDX' },
    US:     { cls: 'badge-purple', label: 'US' },
    CRYPTO: { cls: 'badge-gold',   label: 'CRYPTO' },
    CUSTOM: { cls: 'badge-muted',  label: 'CUSTOM' },
  };
  const cfg = map[market] || { cls: 'badge-muted', label: market };
  return <span className={`badge ${cfg.cls}`}>{cfg.label}</span>;
};

/** Summary count pill */
const CountPill = ({ icon, count, label, color }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '14px 20px',
    background: 'var(--surface2)', border: '1px solid var(--border)',
    borderRadius: 10,
  }}>
    <span style={{ fontSize: 18 }}>{icon}</span>
    <div>
      <p style={{
        fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 800,
        color, letterSpacing: '-0.03em', lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
      }}>{count}</p>
      <p style={{
        fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em',
        textTransform: 'uppercase', color: 'var(--ink3)', marginTop: 3,
      }}>{label}</p>
    </div>
  </div>
);

/** Single row in the ranked table */
const TickerRow = ({ item, rank, onAnalyze, isTop }) => {
  const [hovered, setHovered] = useState(false);
  const change3d = item.change_3d;
  const priceUp  = (change3d ?? 0) >= 0;

  if (item.error && !item.score) return null; // Skip completely failed tickers silently

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'grid',
        gridTemplateColumns: '32px 1fr 70px 80px 130px auto auto auto',
        alignItems: 'center', gap: 16,
        padding: '14px 20px',
        borderBottom: '1px solid var(--border)',
        background: hovered ? 'var(--glass2)' : isTop ? 'rgba(201,169,110,0.03)' : 'transparent',
        transition: 'background .15s ease',
        position: 'relative',
      }}
    >
      {/* Gold left accent for top pick */}
      {isTop && (
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: 2, background: 'var(--gold)', borderRadius: '2px 0 0 2px',
        }} />
      )}

      {/* Rank */}
      <span style={{
        fontFamily: 'var(--mono)', fontSize: 10, color: isTop ? 'var(--gold)' : 'var(--ink4)',
        fontWeight: isTop ? 700 : 400, textAlign: 'center',
      }}>
        {isTop ? '★' : rank}
      </span>

      {/* Ticker + name */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 700,
            color: 'var(--ink)', letterSpacing: '0.02em',
          }}>{item.ticker}</span>
          <MktTag market={item.market} />
          {isTop && (
            <span className="badge badge-gold" style={{ fontSize: 7 }}>TOP PICK</span>
          )}
        </div>
        {item.error && (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)' }}>
            {item.error}
          </span>
        )}
      </div>

      {/* Score bar */}
      <ScoreBar score={item.score ?? 0} />

      {/* Status badge */}
      <StatusBadge status={item.status} />

      {/* 5 dimension chips */}
      <div style={{ display: 'flex', gap: 4 }}>
        <DimChip label="SRT" pts={item.sortino?.pts ?? 0} max={30} />
        <DimChip label="RGM" pts={item.regime?.pts ?? 0}  max={25} />
        <DimChip label="MOM" pts={item.momentum?.pts ?? 0} max={20} />
        <DimChip label="Z"   pts={item.zscore?.pts ?? 0}  max={15} />
        <DimChip label="VOL" pts={item.volatility?.pts ?? 0} max={10} />
      </div>

      {/* Price + 3D change */}
      <div style={{ textAlign: 'right', minWidth: 80 }}>
        {item.price != null ? (
          <>
            <p style={{
              fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600,
              color: 'var(--ink)', letterSpacing: '-0.01em',
              fontVariantNumeric: 'tabular-nums',
            }}>
              {item.price > 1000
                ? item.price.toLocaleString('en-US', { maximumFractionDigits: 2 })
                : item.price.toFixed(item.price < 1 ? 4 : 2)
              }
            </p>
            {change3d != null && (
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
                color: priceUp ? 'var(--green)' : 'var(--red)',
              }}>
                {priceUp ? '▲' : '▼'} {Math.abs(change3d).toFixed(2)}%
              </span>
            )}
          </>
        ) : (
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink4)' }}>—</span>
        )}
      </div>

      {/* Analyze button */}
      <button
        onClick={() => onAnalyze(item.ticker)}
        style={{
          background: hovered ? 'var(--gold)' : 'transparent',
          border: '1px solid',
          borderColor: hovered ? 'var(--gold)' : 'var(--border2)',
          borderRadius: 6,
          padding: '7px 16px',
          fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 600,
          letterSpacing: '0.1em', textTransform: 'uppercase',
          color: hovered ? '#000' : 'var(--ink3)',
          transition: 'all .15s ease', whiteSpace: 'nowrap',
          cursor: 'pointer',
        }}
      >
        Analyze →
      </button>
    </div>
  );
};

/** Table column header */
const ColHead = ({ children, style: sx }) => (
  <span style={{
    fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em',
    textTransform: 'uppercase', color: 'var(--ink4)', ...sx,
  }}>{children}</span>
);

// ─────────────────────────────────────────────────────────────────
//  MAIN SCREENER COMPONENT
// ─────────────────────────────────────────────────────────────────

export default function Screener({ onAnalyze }) {
  const [scanning,     setScanning]     = useState(false);
  const [result,       setResult]       = useState(null);
  const [error,        setError]        = useState(null);
  const [activeMarket, setActiveMarket] = useState('ALL');   // filter tab
  const [showRejected, setShowRejected] = useState(false);
  const [customInput,  setCustomInput]  = useState('');
  const [scanMode,     setScanMode]     = useState('watchlist'); // 'watchlist' | 'custom'

  // ── Run full watchlist scan ────────────────────────────────────
  const runScan = useCallback(async () => {
    setScanning(true);
    setError(null);
    setResult(null);
    try {
      const markets = activeMarket === 'ALL' ? 'IDX,US,CRYPTO' : activeMarket;
      const res = await fetch(`${API}/api/screener/run?markets=${markets}&workers=8`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  }, [activeMarket]);

  // ── Run custom ticker scan ─────────────────────────────────────
  const runCustomScan = useCallback(async () => {
    const tickers = customInput.trim();
    if (!tickers) return;
    setScanning(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API}/api/screener/custom?tickers=${encodeURIComponent(tickers)}`);
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  }, [customInput]);

  // ── Derive display list from results ──────────────────────────
  const displayList = (() => {
    if (!result) return [];
    let list = result.ranked_list || [];
    if (!showRejected) list = list.filter(r => r.status !== 'REJECTED');
    return list;
  })();

  const topPickTickers = new Set(
    Object.values(result?.top_picks || {}).map(p => p?.ticker)
  );

  // ─────────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────────
  return (
    <div style={{ paddingTop: 40, paddingBottom: 96 }}>

      {/* ── PAGE HEADER ── */}
      <div className="anim" style={{ marginBottom: 40 }}>
        <p style={{
          fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.2em',
          textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 12,
        }}>
          Satin Screener · Quantitative Opportunity Scanner
        </p>
        <h1 style={{
          fontSize: 38, fontWeight: 800, letterSpacing: '-0.03em',
          color: 'var(--ink)', lineHeight: 1.1, marginBottom: 14,
        }}>
          Find What's Worth Analyzing
        </h1>
        <p style={{
          fontSize: 14, color: 'var(--ink3)', lineHeight: 1.7, maxWidth: 560,
        }}>
          Screener otomatis menscan seluruh watchlist, menilai setiap ticker dari 5 dimensi
          kuantitatif, dan hanya merekomendasikan yang layak dianalisis lebih dalam.
        </p>
      </div>

      {/* ── CONTROLS PANEL ── */}
      <div className="anim d1 card" style={{ padding: 24, marginBottom: 32 }}>

        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          {[
            { id: 'watchlist', label: 'Scan Watchlist' },
            { id: 'custom',    label: 'Custom Tickers' },
          ].map(({ id, label }) => (
            <button key={id} onClick={() => setScanMode(id)} style={{
              background: scanMode === id ? 'var(--surface3)' : 'transparent',
              border: `1px solid ${scanMode === id ? 'var(--border3)' : 'transparent'}`,
              borderRadius: 6, padding: '7px 16px',
              fontFamily: 'var(--mono)', fontSize: 9, fontWeight: scanMode === id ? 600 : 400,
              letterSpacing: '0.1em', textTransform: 'uppercase',
              color: scanMode === id ? 'var(--ink)' : 'var(--ink3)',
              transition: 'all .15s', cursor: 'pointer',
            }}>{label}</button>
          ))}
        </div>

        {scanMode === 'watchlist' ? (
          /* ── Watchlist mode ─────────────────────────── */
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {/* Market filter tabs */}
            <div style={{ display: 'flex', gap: 6 }}>
              {['ALL', 'IDX', 'US', 'CRYPTO'].map(m => {
                const active = activeMarket === m;
                return (
                  <button key={m} onClick={() => setActiveMarket(m)} style={{
                    background: active ? 'var(--gold)' : 'var(--surface3)',
                    border: `1px solid ${active ? 'transparent' : 'var(--border)'}`,
                    borderRadius: 6, padding: '7px 18px',
                    fontFamily: 'var(--mono)', fontSize: 9, fontWeight: active ? 700 : 400,
                    letterSpacing: '0.1em', textTransform: 'uppercase',
                    color: active ? '#000' : 'var(--ink3)',
                    transition: 'all .15s', cursor: 'pointer',
                  }}>
                    {m === 'ALL' ? '⬡ All Markets' : m}
                  </button>
                );
              })}
            </div>

            {/* Scan button */}
            <button
              onClick={runScan}
              disabled={scanning}
              style={{
                background: scanning ? 'var(--surface3)' : 'var(--gold)',
                border: 'none', color: scanning ? 'var(--ink3)' : '#000',
                padding: '9px 28px', borderRadius: 8,
                fontSize: 12, fontWeight: 700, fontFamily: 'var(--mono)',
                letterSpacing: '0.06em', textTransform: 'uppercase',
                display: 'flex', alignItems: 'center', gap: 10,
                opacity: scanning ? 0.7 : 1,
                transition: 'all .2s', cursor: scanning ? 'not-allowed' : 'pointer',
              }}
            >
              {scanning ? <><Spinner size={13} /> Scanning…</> : '⬡ Run Screener'}
            </button>

            {/* Scan meta info */}
            {result && !scanning && (
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink3)',
                letterSpacing: '0.08em',
              }}>
                {result.scan_metadata?.total_scanned} tickers ·{' '}
                {result.scan_metadata?.scan_duration_s}s
              </span>
            )}
          </div>
        ) : (
          /* ── Custom mode ─────────────────────────────── */
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center',
              background: 'var(--surface3)', border: '1px solid var(--border2)',
              borderRadius: 8, overflow: 'hidden',
            }}>
              <span style={{
                fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)',
                padding: '0 14px', letterSpacing: '0.08em', whiteSpace: 'nowrap',
              }}>TICKERS:</span>
              <input
                value={customInput}
                onChange={e => setCustomInput(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && runCustomScan()}
                placeholder="NVDA, BBCA.JK, BTC-USD, ..."
                style={{
                  flex: 1, background: 'none', border: 'none',
                  fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '0.08em',
                  color: 'var(--ink)', padding: '10px 14px 10px 0',
                }}
              />
            </div>
            <button
              onClick={runCustomScan}
              disabled={scanning || !customInput.trim()}
              style={{
                background: (scanning || !customInput.trim()) ? 'var(--surface3)' : 'var(--gold)',
                border: 'none',
                color: (scanning || !customInput.trim()) ? 'var(--ink4)' : '#000',
                padding: '10px 24px', borderRadius: 8,
                fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 700,
                letterSpacing: '0.1em', textTransform: 'uppercase',
                display: 'flex', alignItems: 'center', gap: 8,
                opacity: (scanning || !customInput.trim()) ? 0.6 : 1,
                transition: 'all .2s', cursor: 'pointer',
              }}
            >
              {scanning ? <><Spinner size={13} /> Scanning…</> : 'Scan →'}
            </button>
          </div>
        )}
      </div>

      {/* ── ERROR STATE ── */}
      {error && (
        <div style={{
          padding: '16px 20px', marginBottom: 24,
          background: 'var(--red-dim)', border: '1px solid var(--red-b)',
          borderRadius: 10,
        }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--red)' }}>
            ⛔ {error}
          </span>
        </div>
      )}

      {/* ── LOADING STATE ── */}
      {scanning && (
        <div className="anim card" style={{ padding: 56, textAlign: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
            <div style={{ position: 'relative', width: 52, height: 52 }}>
              <div style={{
                width: 52, height: 52,
                border: '2px solid var(--border2)',
                borderTopColor: 'var(--gold)',
                borderRadius: '50%',
              }} className="spin-icon" />
              <div style={{
                position: 'absolute', inset: 10,
                border: '1.5px solid var(--border)',
                borderTopColor: 'var(--green)',
                borderRadius: '50%',
                animationDuration: '0.5s',
              }} className="spin-icon" />
            </div>
            <div>
              <p style={{
                fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink2)',
                letterSpacing: '0.08em', marginBottom: 8,
              }}>
                Scanning market universe…
              </p>
              <p style={{
                fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink4)',
                letterSpacing: '0.06em',
              }}>
                Running parallel quantitative analysis across all tickers
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── RESULTS ── */}
      {result && !scanning && (
        <>
          {/* Summary row */}
          <div className="anim" style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12, marginBottom: 28,
          }}>
            <CountPill
              icon="🟢"
              count={result.summary.satin_ready_count}
              label="Satin Ready"
              color="var(--green)"
            />
            <CountPill
              icon="🟡"
              count={result.summary.marginal_count}
              label="Marginal"
              color="var(--gold)"
            />
            <CountPill
              icon="🔴"
              count={result.summary.rejected_count}
              label="Rejected"
              color="var(--red)"
            />
            <CountPill
              icon="◎"
              count={result.summary.total_scanned ?? result.ranked_list.length}
              label={`Avg Score: ${result.summary.avg_score}`}
              color="var(--ink2)"
            />
          </div>

          {/* Top picks highlight strip */}
          {Object.keys(result.top_picks || {}).length > 0 && (
            <div className="anim d1" style={{ marginBottom: 20 }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 10,
                marginBottom: 12, padding: '0 2px',
              }}>
                <div style={{ width: 2, height: 14, background: 'var(--gold)', borderRadius: 2 }} />
                <span style={{
                  fontFamily: 'var(--mono)', fontSize: 9, fontWeight: 500,
                  letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--ink2)',
                }}>Best Pick Per Market</span>
              </div>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {Object.entries(result.top_picks).map(([market, pick]) => (
                  <div key={market} className="card card-gold" style={{
                    padding: '16px 20px',
                    display: 'flex', alignItems: 'center', gap: 16,
                    cursor: 'pointer', flex: '1 1 200px',
                    transition: 'transform .2s ease',
                  }}
                  onClick={() => onAnalyze(pick.ticker)}
                  onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                  onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
                  >
                    <div style={{
                      width: 40, height: 40, borderRadius: 8,
                      background: 'var(--gold-bg)',
                      border: '1px solid rgba(201,169,110,.25)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <span style={{
                        fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 700,
                        color: 'var(--gold)', letterSpacing: '0.08em',
                      }}>{market}</span>
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{
                        fontFamily: 'var(--mono)', fontSize: 14, fontWeight: 800,
                        color: 'var(--ink)', letterSpacing: '0.02em', marginBottom: 4,
                      }}>{pick.ticker}</p>
                      <ScoreBar score={pick.score} />
                    </div>
                    <button style={{
                      background: 'none', border: '1px solid var(--gold3)',
                      borderRadius: 5, padding: '5px 12px',
                      fontFamily: 'var(--mono)', fontSize: 8, fontWeight: 600,
                      letterSpacing: '0.1em', textTransform: 'uppercase',
                      color: 'var(--gold)', cursor: 'pointer',
                    }}>Analyze</button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Ranked table */}
          <div className="anim d2 card" style={{ overflow: 'hidden' }}>

            {/* Table header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '32px 1fr 70px 80px 130px auto auto auto',
              alignItems: 'center', gap: 16,
              padding: '12px 20px',
              background: 'var(--surface2)', borderBottom: '1px solid var(--border)',
            }}>
              <ColHead>#</ColHead>
              <ColHead>Ticker</ColHead>
              <ColHead>Score</ColHead>
              <ColHead>Status</ColHead>
              <ColHead>Dimensions</ColHead>
              <ColHead style={{ textAlign: 'right' }}>Price</ColHead>
              <ColHead style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={() => setShowRejected(s => !s)}
                  style={{
                    background: 'none', border: '1px solid var(--border)',
                    borderRadius: 4, padding: '3px 10px',
                    fontFamily: 'var(--mono)', fontSize: 7, letterSpacing: '0.1em',
                    textTransform: 'uppercase', color: 'var(--ink4)',
                    cursor: 'pointer', transition: 'all .15s',
                    whiteSpace: 'nowrap',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = 'var(--ink2)'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--ink4)'}
                >
                  {showRejected ? 'Hide Rejected' : 'Show Rejected'}
                </button>
              </ColHead>
              <ColHead />
            </div>

            {/* Table body */}
            <div>
              {displayList.length === 0 ? (
                <div style={{ padding: 48, textAlign: 'center' }}>
                  <p style={{
                    fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)',
                    letterSpacing: '0.08em',
                  }}>
                    No tickers match current filter. Try showing rejected tickers or expand market selection.
                  </p>
                </div>
              ) : (
                displayList.map((item, idx) => (
                  <TickerRow
                    key={`${item.ticker}-${idx}`}
                    item={item}
                    rank={idx + 1}
                    onAnalyze={onAnalyze}
                    isTop={topPickTickers.has(item.ticker)}
                  />
                ))
              )}
            </div>

            {/* Footer */}
            <div style={{
              padding: '12px 20px',
              background: 'var(--surface2)', borderTop: '1px solid var(--border)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 8, color: 'var(--ink4)', letterSpacing: '0.08em' }}>
                {displayList.length} tickers shown · scanned at {
                  result.scan_metadata?.timestamp
                    ? new Date(result.scan_metadata.timestamp).toLocaleTimeString()
                    : '—'
                }
              </span>
              <div style={{ display: 'flex', gap: 16 }}>
                {[
                  { label: 'SRT', desc: 'Sortino (30pts)' },
                  { label: 'RGM', desc: 'Regime (25pts)' },
                  { label: 'MOM', desc: 'Momentum (20pts)' },
                  { label: 'Z',   desc: 'Z-Score (15pts)' },
                  { label: 'VOL', desc: 'Volatility (10pts)' },
                ].map(({ label, desc }) => (
                  <span key={label} style={{
                    fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink4)',
                    letterSpacing: '0.08em',
                  }} title={desc}>{label}</span>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ── EMPTY STATE (before first scan) ── */}
      {!result && !scanning && !error && (
        <div className="anim d2 card" style={{ padding: 72, textAlign: 'center' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{
              width: 56, height: 56, margin: '0 auto 20px',
              border: '1px solid var(--border2)', borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 22, color: 'var(--ink4)' }}>⬡</span>
            </div>
            <p style={{
              fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)',
              letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10,
            }}>Screener Standby</p>
            <p style={{ fontSize: 13, color: 'var(--ink4)', lineHeight: 1.7 }}>
              Pilih market, lalu klik <strong style={{ color: 'var(--gold)' }}>Run Screener</strong> untuk<br />
              mendapatkan ranked list ticker terbaik secara otomatis.
            </p>
          </div>

          {/* Scoring legend */}
          <div style={{
            display: 'inline-grid', gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 8, padding: '20px 32px',
            background: 'var(--surface2)', border: '1px solid var(--border)',
            borderRadius: 10, marginTop: 8,
          }}>
            {[
              { label: 'Sortino', pts: 30, color: 'var(--green)' },
              { label: 'Regime',  pts: 25, color: 'var(--purple)' },
              { label: 'Momentum', pts: 20, color: 'var(--blue)' },
              { label: 'Z-Score', pts: 15, color: 'var(--amber)' },
              { label: 'Volatility', pts: 10, color: 'var(--red)' },
            ].map(({ label, pts, color }) => (
              <div key={label} style={{ textAlign: 'center' }}>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 800, color, marginBottom: 4 }}>{pts}</p>
                <p style={{ fontFamily: 'var(--mono)', fontSize: 7, color: 'var(--ink4)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>{label}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}