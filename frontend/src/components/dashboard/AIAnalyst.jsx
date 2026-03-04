import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

const MetricTile = ({ label, value, color = 'var(--ink)' }) => (
  <div style={{ padding: '14px 16px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, textAlign: 'center' }}>
    <p style={{ fontFamily: 'var(--mono)', fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink3)', marginBottom: 8 }}>{label}</p>
    <p style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.015em', color, fontVariantNumeric: 'tabular-nums' }}>{value}</p>
  </div>
);

export default function AIAnalyst({ ticker, apexData, tf = '1D' }) {
  const [analysis, setAnalysis] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [loading, setLoading] = useState(false);

  const verdict   = apexData?.apex_score?.verdict || 'NEUTRAL';
  const isBull    = verdict === 'BULLISH';
  const isBear    = verdict === 'BEARISH';
  const verdictColor = isBull ? 'var(--green)' : isBear ? 'var(--red)' : 'var(--ink2)';

  const rr   = apexData?.kelly?.reward_risk_ratio;
  const prob = apexData?.statistics?.monte_carlo?.prob_profit_pct;
  const score = apexData?.apex_score?.score;

  const runAnalysis = async () => {
    setLoading(true);
    setAnalysis('');
    setIsThinking(true);
    try {
      const res = await fetch(`http://localhost:8001/api/satin/stream/${ticker}?tf=${tf}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        full += dec.decode(value, { stream: true });
        const clean = full.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
        if (full.includes('</think>')) setIsThinking(false);
        setAnalysis(clean);
      }
    } catch (e) {
      setAnalysis('⛔ Connection failed. Ensure Ollama is running (ollama serve).');
    } finally {
      setLoading(false);
      setIsThinking(false);
    }
  };

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14,
      overflow: 'hidden', position: 'relative',
    }}>
      {/* Gold accent top line */}
      <div style={{ height: 1, background: 'linear-gradient(90deg, transparent, var(--gold), transparent)' }} />

      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--gold)', marginBottom: 6 }}>Satin AI Engine</p>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', letterSpacing: '-0.01em' }}>Deep Quantitative Analysis</h3>
        </div>
        <button onClick={runAnalysis} disabled={loading} style={{
          background: loading ? 'var(--surface2)' : 'var(--gold)',
          color: loading ? 'var(--ink3)' : '#000',
          border: 'none', padding: '10px 22px', borderRadius: 8,
          fontSize: 12, fontWeight: 700, letterSpacing: '0.02em',
          transition: 'all .2s ease',
          opacity: loading ? 0.6 : 1,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          {loading ? (
            <>
              <div style={{ width: 12, height: 12, border: '1.5px solid var(--ink3)', borderTopColor: 'var(--ink2)', borderRadius: '50%' }} className="spin-icon" />
              Synthesizing…
            </>
          ) : 'Run Satin'}
        </button>
      </div>

      {/* Key Metrics Row — always visible */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 1, background: 'var(--border)', borderBottom: '1px solid var(--border)' }}>
        <MetricTile label="APEX Score"    value={score != null ? `${score}/100` : '—'} color={score >= 70 ? 'var(--green)' : score <= 30 ? 'var(--red)' : 'var(--ink)'} />
        <MetricTile label="Verdict"       value={verdict}   color={verdictColor} />
        <MetricTile label="Win Prob (MC)" value={prob != null ? `${prob}%` : '—'} color={(prob ?? 50) > 50 ? 'var(--green)' : 'var(--red)'} />
        <MetricTile label="Risk/Reward"   value={rr != null ? `1:${rr.toFixed(2)}` : '—'} color="var(--gold)" />
      </div>

      {/* Thinking state */}
      {isThinking && (
        <div style={{ margin: 20, padding: '14px 16px', background: 'var(--surface2)', border: '1px dashed var(--border2)', borderRadius: 10, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 14, height: 14, border: '1.5px solid var(--border3)', borderTopColor: 'var(--gold)', borderRadius: '50%' }} className="spin-icon" />
          <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink3)', fontStyle: 'italic' }}>Satin is reasoning through quantitative models…</span>
        </div>
      )}

      {/* Analysis Output */}
      {analysis && (
        <div style={{ padding: 24 }}>
          <div style={{
            fontSize: 13, lineHeight: 1.85, color: 'var(--ink2)',
            borderLeft: '2px solid var(--gold3)', paddingLeft: 18,
          }}>
            <ReactMarkdown
              components={{
                h1: ({children}) => <h1 style={{ fontSize: 15, fontWeight: 700, color: 'var(--gold)', marginBottom: 10, marginTop: 20 }}>{children}</h1>,
                h2: ({children}) => <h2 style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', marginBottom: 8, marginTop: 16, fontFamily: 'var(--mono)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>{children}</h2>,
                h3: ({children}) => <h3 style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', marginBottom: 6, marginTop: 14 }}>{children}</h3>,
                p:  ({children}) => <p style={{ marginBottom: 12 }}>{children}</p>,
                strong: ({children}) => <strong style={{ color: 'var(--ink)', fontWeight: 600 }}>{children}</strong>,
                code: ({children}) => <code style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--gold)', background: 'var(--gold-bg)', padding: '1px 6px', borderRadius: 3 }}>{children}</code>,
                ul: ({children}) => <ul style={{ paddingLeft: 18, marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>{children}</ul>,
                li: ({children}) => <li style={{ fontSize: 13, color: 'var(--ink2)' }}>{children}</li>,
              }}
            >{analysis}</ReactMarkdown>
          </div>
        </div>
      )}

      {!analysis && !loading && (
        <div style={{ padding: 28, textAlign: 'center' }}>
          <p style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink3)', letterSpacing: '0.08em' }}>Click "Run Satin" to generate institutional-grade analysis</p>
        </div>
      )}
    </div>
  );
}