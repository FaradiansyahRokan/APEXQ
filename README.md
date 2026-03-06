#  APEX Quantum — Institutional-Grade Quantitative Trading Intelligence

<div align="center">

![APEX Banner](https://img.shields.io/badge/APEX-Quantum%20Command-1A56DB?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMyAyLjA1djIuMDJjMy45NS41MSA3IDMuODUgNyA3LjkzIDAgMy4yMS0xLjgxIDYtNC41IDcuNThMMTMgMTcudjIuMDVjNC42LS41NCA4LTQuMzYgOC04Ljk3IDAtNC42My0zLjQtOC40My04LTguOTN6TTExIDE3bC0yLjUgMS45OUw3IDE3LjA0QzQuODEgMTUuNDYgMyAxMi42MyAzIDkuOTggMyA1LjkxIDYuMDUgMi41NyAxMCAyLjA1VjRDNy4wNSA0LjUgNSA2Ljk2IDUgOS45OGMwIDIuMDUgMS4wNCA0LjEzIDIuNjUgNS41bDEuMzUgMS4yVjE3eiIvPjwvc3ZnPg==)
![Live](https://img.shields.io/badge/🟢%20LIVE-apexq.vercel.app-00C851?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=for-the-badge&logo=react&logoColor=black)

** Live Demo: [apexq.vercel.app](https://apexq.vercel.app)**

*Built solo. No team. No corporate budget. Just math, code, and conviction.*

</div>

---

##  What Is APEX?

APEX is a **full-stack quantitative trading intelligence platform** that I built from scratch — combining institutional-grade mathematical models, real-time market data pipelines, AI-powered analysis, and a live HFT simulation engine into a single, deployable web application.

This is not a tutorial project. This is not a wrapper around an existing library.

Every model was implemented from mathematical first principles. Every architectural decision was made intentionally. The result is a system that thinks about markets the way a **quantitative hedge fund** does — not the way a retail trader does.

> *"Most retail traders are exit liquidity. APEX was built to be on the other side of that trade."*

---

##  Live Platform Walkthrough

### 1.  Dashboard — Deep Quantitative Analysis

The main dashboard analyzes any ticker (IDX stocks, US equities, or crypto) and outputs a **complete institutional-grade verdict** in seconds.

**What you see:**
- **Real-time candlestick chart** with EMA overlays and volume profile
- **APEX Score (0–100)** — composite signal quality rating
- **SATIN AI Engine** — 5-step Chain of Thought reasoning that works through conflicting signals like a senior portfolio manager would
- **Smart Money Bias (ICT)** — detects institutional order blocks, Fair Value Gaps, and liquidity zones
- **Neural Synthesis** — LLM-powered executive summary of the overall trade thesis
- **Intelligence Wire** — live news feed contextualizing macro events to the specific ticker

**Sample output on BBCA.JK:**
```
APEX Score    : 43.8 / 100
Verdict       : NEUTRAL
Win Prob (MC) : 36.64%
Kelly Edge    : NO_EDGE  (EV = -0.1923%)
Market Regime : RANDOM WALK
SATIN Verdict : STAND CLEAR
```

The system correctly identified that despite bullish Smart Money signals, the statistical edge was negative — and recommended standing clear. **Math overrides narrative. Always.**

---

### 2.  Macro Intelligence & Factor Decomposition

Below the chart, APEX runs a full **multi-layer factor decomposition**:

| Layer | What It Measures |
|-------|-----------------|
| **Cross-Asset** | DXY, NASDAQ, GOLD correlation context |
| **Market Regime** | Hurst Exponent, persistence, volatility — classifies as TREND / RANDOM WALK / MEAN REVERT |
| **Factor Alpha** | Momentum, VRP level, vol premium, Sortino |
| **Smart Money (ICT)** | FVG, POC, price position, liquidity, structure |
| **Monte Carlo (5K sim)** | Win probability distribution, best/worst 5%, CVaR |
| **Kelly Criterion** | Safe Kelly fraction, dollar risk, ruin probability, reward/risk |
| **Fundamental Stats** | Market cap, P/E, P/B, 24h volume |
| **Ownership (Bandarmologi)** | Institutional whale %, insider %, retail float |

**This is not a technical indicator dashboard. This is a complete decision intelligence system.**

---

### 3. 🔬 Institutional Audit — Statistical Validity & Risk Report

The Audit module validates any return series against **institutional deployment criteria** — the same checks a hedge fund compliance team would run before allocating capital.

**Five audit dimensions:**

**① Lo-Adjusted Sharpe Ratio (Lo 2002)**
Standard Sharpe overstates performance due to autocorrelation. APEX corrects for this using Lo's (2002) autocorrelation adjustment — the same method used by institutional quant desks.

```
Raw Sharpe    : 0.417  (uncorrected — would mislead)
Lo Adj. SR    : 0.485  (η = 0.742 correction applied)
```

**② Deflated Sharpe Ratio (Bailey-López de Prado 2016)**
When you test 25 strategies, some will backtest well by pure chance. DSR penalizes for multiple testing — a strategy must prove it would survive even after adjusting for all the strategies you *didn't* show.

```
DSR Probability : 98.2%    PASS
Threshold SR*   : 0.134
Strategies N    : 25 tested
```

**③ Bootstrap Confidence Intervals (5,000 samples)**
Non-parametric Sharpe distribution. No normality assumption.

```
P(SR > 0) : 61.4%
P(SR > 1) : 19.9%
```

**④ CVaR / Tail Risk (Cornish-Fisher corrected)**
Standard Gaussian VaR understates risk when returns have fat tails. APEX detects fat-tail distributions and automatically switches to Cornish-Fisher correction.

```
Excess Kurtosis : 3.37 (fat-tail detected)
Note: Gaussian VaR understates risk 30-50% — Cornish-Fisher used
VaR 95% (C-F)   : -3.40%
CVaR 95% (C-F)  : -5.20%
```

**⑤ Return Distribution Diagnostics**
Full skewness, kurtosis, annualized return, and volatility breakdown.

---

### 4.  Demo Trading — HFT Engine & Live Orderbook

The Demo Trading module runs **two live algorithmic strategies** simultaneously, with real-time Hyperliquid L1 orderbook data.

**Strategy: Jackal HFT** *(Micro-momentum burst)*
- Detects consecutive tick momentum: entry fires on 3+ ticks in one direction with minimum 0.02% total move
- OFI (Order Flow Imbalance) gate prevents entries against extreme opposing flow
- Monitors BTC, ETH, SOL, BNB, XRP, AVAX simultaneously
- Real-time spread monitoring, streak tracking per asset

**Live Orderbook Integration (Hyperliquid L1)**
- Sub-100ms order depth updates
- Live bid/ask visualization with quantity at each price level
- Spread monitoring with OK/ALERT status

**Milestone Ladder (Equity Armor)**
- High-watermark protection: floor locks at previous milestone
- Risk auto-reduces as equity approaches the floor
- Visualized in real-time as equity grows

---

### 5.  Simulator — Backtest Engine v2.0

The Simulator runs walk-forward backtests across **US Markets, IDX (Indonesia), Crypto, and Universal** universes with full institutional-grade analytics.

**Sample result — US Markets backtest:**

```
Initial Capital    : $100
Final Value        : $122.719   (+22.72%)
Kelly Avg Frac     : 11.3%
Max Leverage       : 0.84x (institutional cap: 1.0x)
Trades Filtered    : 25 (by 3-layer quality gate)
```

**Core Performance Metrics:**

| Metric | Value | Benchmark |
|--------|-------|-----------|
| Sharpe Ratio | **1.896** | > 1.0 = good |
| Sortino Ratio | **4.061** | > 1.0 = good |
| Calmar Ratio | **6.906** | > 0.5 = good |
| Max Drawdown | **-3.29%** | < -15% = dangerous |
| Profit Factor | **3.029** | > 1.5 = good |
| Win Rate | **40.38%** | — |
| Avg Win | **+1.4874%** | — |
| Avg Loss | **-0.4483%** | — |

**Key insight:** Win rate of 40% is *intentionally low*. The system wins on asymmetry — average win is **3.3× larger than average loss**. This is how professional quant systems actually work: not by being right more often, but by extracting more when right and losing less when wrong.

**Gate Analysis — 3-Layer Quality Gate:**

The system assigns every trade a quality score (0–100) based on regime, ICT signal strength, and technical confirmation. Low-quality trades get smaller position size — not blocked — because data shows even B-grade setups contribute positive expectancy.

```
Gate Filter Rate         : 32.5% of trades reduced/blocked
Avg Regime Confidence    : 81.8%
Strong ICT Entries       : 52 (VERY_STRONG signals)
```

**Equity Curve:** Structurally upward-trending with minimal drawdown periods — the hallmark of a system with genuine statistical edge rather than curve-fitted luck.

---

##  Mathematical Engine — What's Under the Hood

APEX implements **25+ institutional quantitative models** from scratch:

### Regime Detection
- **Hurst Exponent** — measures long-range dependence (H > 0.5 = trending, H ≈ 0.5 = random walk, H < 0.5 = mean-reverting)
- **Hidden Markov Model (HMM)** — probabilistic regime classification
- **Bayesian Regime Tracker** — online posterior updating with Dirichlet-Multinomial conjugate

### Risk & Portfolio Theory
- **Kelly Criterion** — optimal position sizing with Quarter-Kelly safety margin
- **Hierarchical Risk Parity (HRP)** — López de Prado (2016), correlation-distance seriation + recursive bisection
- **Black-Litterman Model** — equilibrium + views portfolio construction, τ from cross-sectional vol
- **VaR / CVaR** — both Gaussian and Cornish-Fisher (fat-tail corrected)
- **Monte Carlo Simulation** — 5,000 path simulation, no normality assumption

### Statistical Validation
- **Lo-Adjusted Sharpe** — autocorrelation correction (Lo 2002)
- **Deflated Sharpe Ratio** — multiple testing correction (Bailey-López de Prado 2016)
- **Block Bootstrap** — Politis & Romano (1994), preserves serial dependence
- **Jarque-Bera normality test** — distribution diagnostic

### Signal Generation
- **Kalman Filter** — Joseph-form covariance update (numerically stable), adaptive price tracking
- **Ornstein-Uhlenbeck Process** — mean reversion half-life estimation via MLE (Vasicek 1977)
- **Kyle's Lambda** — adverse selection measurement: λ = Cov(ΔPrice, SignedVolume) / Var(SignedVolume)
- **Hawkes Process** — self-exciting order flow intensity (microstructure)
- **PCA Factor Model** — systematic vs idiosyncratic risk decomposition, Ledoit-Wolf shrinkage

### ICT / Smart Money Analysis
- Fair Value Gap (FVG) detection
- Order Block identification
- Premium / Discount zone analysis
- Liquidity pool mapping (SSL/BSL)
- Structure Break (CHoCH / BOS)

---

##  Technical Stack

```
Frontend      : React.js + Next.js + Tailwind CSS
Backend       : Python + FastAPI
Quant Engine  : NumPy + Pandas + SciPy (from scratch — no QuantLib)
AI Layer      : Local LLM via Ollama (DeepSeek-R1 8B) — 100% private
Data Sources  : yFinance · Binance REST API · Hyperliquid L1 WebSocket · Google News RSS
Database      : Redis (real-time state) · PostgreSQL (historical)
Deployment    : Vercel (frontend) · Railway (backend)
```

---

##  System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   APEX FRONTEND                      │
│         React + Next.js (apexq.vercel.app)          │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────┐
│                  APEX BACKEND                        │
│              FastAPI · Python 3.11                   │
├─────────────┬────────────────┬───────────────────────┤
│  APEX       │  SATIN AI      │  RISK MANAGER         │
│  ENGINE v7  │  ENGINE        │  (Equity Armor)       │
│  25+ models │  LLM + CV      │  HWM + Kelly          │
├─────────────┴────────────────┴───────────────────────┤
│                  DATA PIPELINE                       │
│   yFinance · Binance · Hyperliquid L1 · News RSS     │
└─────────────────────────────────────────────────────┘
```

---

##  Why This Is Different From Typical "Trading Bot" Projects

| Feature | Typical GitHub Project | APEX |
|---------|----------------------|------|
| Models | RSI, MACD, Bollinger | Kalman, HRP, Black-Litterman, Hawkes |
| Backtesting | Simple P&L calculation | Walk-forward, DSR, Bootstrap CI, Lo-Sharpe |
| Risk | Fixed stop loss % | Kelly Criterion + Equity Armor + CVaR |
| Regime | None | HMM + Hurst + Bayesian |
| Validation | "It made profit in backtest" | Institutional audit: DSR, Bootstrap, Fat-tail detection |
| Live Data | Yahoo Finance | Binance + Hyperliquid L1 WebSocket |
| AI Layer | None or ChatGPT API | Local LLM (privacy-first) |
| Deployment | Jupyter Notebook | Full web app, live at apexq.vercel.app |

---

##  Key Numbers

```
Lines of Code        : ~23,000+
Mathematical Models  : 25+
Data Sources         : 4 live feeds
Modules              : 18 specialized engines
Backtest Win Rate    : 40.38% (profitable via asymmetry, not frequency)
Sortino Ratio        : 4.061
Max Drawdown         : -3.29%
DSR Pass             : 98.2%
Deployment           : Live (apexq.vercel.app)
Built by             : 1 person
```

---

## 👨‍💻 About the Builder

**Faradiansyah Rokan** — Quantitative Software Engineer & Blockchain Developer

Currently studying Software Engineering at Telkom University, Bandung. Built APEX and APEX HUMANITY (a Web3 impact protocol on Avalanche) independently, without a team or corporate budget.

-  [LinkedIn](https://linkedin.com/in/faradiansyah-rokan-a18480248)
-  rokansubhi.f@gmail.com
-  [apexq.vercel.app](https://apexq.vercel.app)

---

> *"In a market dominated by HFT algorithms and institutional capital, intuition is the fastest way to become exit liquidity. APEX was built to extract alpha through mathematical verification — not hope."*

---

<div align="center">

** If this project gave you value, a star means a lot.**

*Built with obsession. Deployed with conviction.*

</div>
