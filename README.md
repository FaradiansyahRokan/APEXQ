# ╔══════════════════════════════════════════════════════════════════╗
# ║                  APEXQ — QUANTUM MARKET OS v3.0                  ║
# ║      Next-Gen Institutional-Grade Quantitative Trading System    ║
# ╚══════════════════════════════════════════════════════════════════╝

**APEXQ** adalah platform sistem operasi pasar (Market OS) berbasis kuantitatif yang mengintegrasikan algoritma **HMM (Hidden Markov Model)**, **ICT/SMC (Inner Circle Trader/Smart Money Concepts)**, dan **Kelly Criterion** untuk memberikan keunggulan presisi (edge) dalam trading saham (IDX, US) dan Crypto.

Platform ini dibangun untuk trader profesional yang menginginkan data yang objektif, tanpa bias emosional, melalui pemrosesan data historis dan real-time menggunakan mesin scoring tingkat lanjut.

---

## Fitur Utama (Core Features)

### 1. Satin Screener Engine (Automated Ranking)
Mesin pencari peluang otomatis yang menscan ratusan ticker secara paralel dan menyaringnya berdasarkan skor kualitas kuantitatif.
- **Scoring 5 Dimensi (0-100 pts):**
  - **Sortino Ratio (30 pts):** Mengukur kualitas return dengan memprioritaskan "good volatility".
  - **Regime Score (25 pts):** Analisis kecocokan arah pasar saat ini.
  - **Trend Momentum (20 pts):** Menggunakan ROC (Rate of Change) 20-hari.
  - **Z-Score (15 pts):** Analisis statistik untuk memastikan harga tidak dalam kondisi *overbought*.
  - **Volatility Grade (10 pts):** Menilai tingkat risiko pergerakan harga.
- **Ranking System:** `SATIN_READY` (≥70), `MARGINAL` (50–69), and `REJECTED` (<50).

### 2. ICT/SMC Intelligence Engine
Deteksi matematis konsep perdagangan institusional secara otomatis.
- **Fair Value Gap (FVG):** Deteksi ketidakseimbangan (imbalance) harga di pasar secara otomatis.
- **Order Block (OB):** Identifikasi area akumulasi atau distribusi institusi.
- **Market Structure:** Melacak **BoS (Break of Structure)** dan **CHoCH (Change of Character)** untuk menentukan perubahan bias pasar.
- **Liquidity Detection:** Menemukan area *Buy Side* dan *Sell Side* liquidity.

### 3. Market Regime HMM (Hidden Markov Model)
Algoritma ini mendeteksi kondisi pasar "tersembunyi" (Hidden States) tanpa dependensi manual.
- **3 State Detection:**
  - `HIGH_VOL_BEARISH`: Kondisi krisis/panic selling.
  - `LOW_VOL_BULLISH`: Kondisi trending santai (Smart Money moving in).
  - `SIDEWAYS_CHOP`: Kondisi konsolidasi/noise.
- **Dynamic Transition:** Memberikan sinyal kapan harus agresif (Risk-On) dan kapan harus diam (Risk-Off).

### 4. Kelly Criterion & Risk Manager
Mesin penghitung posisi (Position Sizing) otomatis untuk meminimalkan probabilitas kebangkrutan (*Ruin Probability*).
- **Fractional Kelly (Quarter Kelly):** Menggunakan 25% dari formulasi Kelly asli untuk keamanan ekstra terhadap guncangan pasar.
- **Optimal Position Sizing:** Menghitung lot/unit berdasarkan jarak Stop Loss nyata dari harga entry.
- **Win Rate Persistence:** Menghitung probabilitas keuntungan berdasarkan histori trade secara statistik.

### 5. Quantum Portfolio Simulator (Backtester)
Mesin simulasi tingkat lanjut untuk menguji strategi sebelum digunakan secara live.
- **Weekly Rolling Scan:** Merefleksikan gaya trading mingguan yang realistis.
- **Circuit Breaker:** Fitur keamanan otomatis yang menghentikan simulasi jika *Drawdown* melebihi 15% untuk melatih disiplin manajemen risiko.
- **High-Fidelity Reporting:** Visualisasi kurva ekuitas menggunakan **Recharts** dengan detail performa (Sharpe, Sortino, Calmar, Profit Factor).

---

## 🧠 Logika & Perhitungan (Mathematical Logic)

### Formulasi Kelly Criterion
Platform ini menghitung ukuran posisi optimal menggunakan rumus:
```text
K% = W - [(1 - W) / R]
Di mana:
W = Win Rate (Probabilitas Menang)
R = Reward-to-Risk Ratio
```
*APEXQ secara default merekomendasikan **Safe Kelly (Quarter Kelly)** yaitu `K% * 0.25` untuk menjaga volatilitas ekuitas portfolio.*

### HMM Regime Scoring
Algoritma HMM diimplementasikan menggunakan pemrosesan NumPy murni (tanpa dependensi berat) untuk mendeteksi distribusi Gaussian dari return harga. Hal ini memungkinkan sistem untuk membedakan antara "koreksi sehat" dan "awal krisis".

### ICT Imbalance Detection
Sistem mencari gap harga antara Candle 1 dan Candle 3:
- **Bullish FVG:** `Low[i] > High[i-2]`
- **Bearish FVG:** `High[i] < Low[i-2]`
Identifikasi ini divalidasi dengan volume untuk memastikan FVG tersebut bukan sekadar noise pasar.

---

## 🛠️ Tech Stack

### Backend (Quantitative Core)
- **Python 3.10+**: Core programming.
- **Pandas & NumPy**: High-performance data processing.
- **SciPy**: Advanced statistical calculation.
- **YFinance & Hyperliquid API**: Market data provider (Crypto/Stock).

### Frontend (User Interface)
- **React.js**: Library utama UI.
- **Vite**: Build tool super cepat.
- **Tailwind CSS**: Modern styling system.
- **Recharts**: Data visualization untuk Equity Curve.
- **Lucide React**: Icon system.

---

## 🚀 Instalasi & Setup

### 1. Clone Repository
```bash
git clone https://github.com/FaradiansyahRokan/APEXQ.git
cd APEXQ
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 💎 Keunggulan APEXQ
- **Zero Bias:** Semua sinyal murni berdasarkan angka dan statistik, bukan emosi atau berita hoax.
- **Multi-Asset:** Mendukung Saham Indonesia (IDX), Saham US, dan Crypto d satu dashboard.
- **Professional Risk Management:** Fitur Kelly Criterion dan Circuit Breaker memastikan modal kamu terlindungi secara matematis.
- **High Fidelity Backtest:** Simulasi yang mendekati kondisi pasar nyata dengan batasan *Open Position* dan *Drawdown Limit*.

---

**DISCLAIMER:** *Trading instrumen keuangan melibatkan risiko tinggi. APEXQ adalah alat bantu kuantitatif. Gunakan dengan bijak dan gunakan risiko yang kamu sanggup tanggung.*

---
© 2026 APEXQ Development Team. Built for the modern quant.
