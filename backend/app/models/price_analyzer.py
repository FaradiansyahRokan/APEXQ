"""
╔══════════════════════════════════════════════════════════════════╗
║          SATIN AI — UPGRADED REASONING ENGINE v2.0              ║
║   Chain-of-Thought · Grounded Data · Mandatory "Why/How"        ║
╚══════════════════════════════════════════════════════════════════╝

Perbedaan vs versi lama:
  - Prompt menggunakan teknik Chain-of-Thought (CoT) agar model
    tidak loncat ke kesimpulan tanpa alasan
  - Data diinjeksi dengan INTERPRETASI konteks (bukan angka buta)
  - Model WAJIB jelaskan: KENAPA, BAGAIMANA, dan KARENA APA
  - Temperature 0.1 untuk output deterministic dan tidak halu
  - Fallback handling yang informatif
"""

import json
import requests
from typing import Optional


# ─────────────────────────────────────────────────────────────────
#  HELPER: Interpretasi Angka → Konteks (agar AI tidak buta angka)
# ─────────────────────────────────────────────────────────────────

def _interpret_zscore(z: float) -> str:
    az = abs(z)
    direction = "DI ATAS" if z > 0 else "DI BAWAH"
    if az > 3.0:
        return f"EKSTREM ({z:.2f}σ {direction} rata-rata). Ini terjadi <0.3% secara statistik — area reversal probabilitas sangat tinggi."
    elif az > 2.0:
        return f"SIGNIFIKAN ({z:.2f}σ {direction} rata-rata). Ini terjadi <5% secara statistik — harga sudah jauh dari equilibrium."
    elif az > 1.0:
        return f"ELEVATED ({z:.2f}σ {direction} rata-rata). Harga mulai menjauhi mean, tapi belum zona ekstrem."
    else:
        return f"NORMAL ({z:.2f}σ). Harga masih dalam distribusi wajar, belum ada sinyal statistik yang kuat."


def _interpret_var(var: float) -> str:
    if var > 5.0:
        return f"{var:.2f}% — RISIKO SANGAT TINGGI. Dalam skenario 5% terburuk, loss bisa melampaui angka ini dalam 1 hari."
    elif var > 3.0:
        return f"{var:.2f}% — RISIKO TINGGI. Volatilitas aset ini signifikan, position sizing harus dikurangi drastis."
    elif var > 1.5:
        return f"{var:.2f}% — RISIKO MODERAT. Masih dalam batas wajar untuk futures dengan leverage rendah."
    else:
        return f"{var:.2f}% — RISIKO RENDAH. Aset relatif stabil, sizing bisa lebih agresif (sesuai Kelly)."


def _interpret_monte_carlo(prob: float, worst_dd: float) -> str:
    return (
        f"Dari 5.000 simulasi path harga ke depan 30 hari: "
        f"Probabilitas profit = {prob:.1f}%. "
        f"Skenario drawdown terburuk (5% worst case) = {worst_dd:.2f}%. "
        f"{'Bias bullish dominan dalam simulasi.' if prob > 55 else 'Bias bearish dominan — lebih banyak path berakhir merugi.' if prob < 45 else 'Peluang hampir 50-50, tidak ada edge statistik yang jelas.'}"
    )


def _interpret_hurst(regime: str, hurst: float) -> str:
    h = f"H={hurst:.3f}"
    if regime == "STRONG_TREND":
        return f"STRONG TREND ({h}). Market memiliki momentum kuat — strategi trend-following paling efektif. Entry pullback lebih aman dari breakout."
    elif regime == "TRENDING":
        return f"TRENDING ({h}). Ada persistensi arah, tapi tidak sekuat STRONG TREND. Gunakan retracement ke EMA/POC untuk entry."
    elif regime == "MEAN_REVERTING":
        return f"MEAN-REVERTING ({h}). Market cenderung balik ke rata-rata setelah bergerak jauh. Strategi counter-trend/range lebih efektif daripada breakout."
    elif regime == "RANDOM_WALK":
        return f"RANDOM WALK ({h}). Tidak ada persistensi arah. Edge strategi apapun sangat rendah di kondisi ini — probabilitas success mendekati 50%."
    return f"UNDEFINED ({h})"


def _interpret_kelly(edge: str, kelly_pct: float, dollar_risk: float) -> str:
    if edge == "NO_EDGE":
        return f"NO EDGE — Expected Value NEGATIF. Setiap trade di setup ini secara matematis menggerus modal. STOP."
    elif edge == "WEAK":
        return f"EDGE LEMAH (Kelly={kelly_pct:.2f}%). Margin keuntungan sangat tipis. Dollar risk yang diizinkan: ${dollar_risk:.0f}. Tidak worthit untuk risiko yang diambil."
    elif edge == "MODERATE":
        return f"EDGE SOLID (Kelly={kelly_pct:.2f}%). Setup ini memiliki positive expected value. Dollar risk yang diizinkan sistem: ${dollar_risk:.0f}."
    elif edge == "STRONG":
        return f"EDGE KUAT (Kelly={kelly_pct:.2f}%). Setup matematis bagus. Dollar risk yang diizinkan sistem: ${dollar_risk:.0f}. Tetap gunakan Quarter Kelly."
    return "EDGE TIDAK TERIDENTIFIKASI"


def _interpret_ict(
    bias: str, structure: str,
    nearest_ob: Optional[dict],
    nearest_fvg: Optional[dict],
    poc: float, vah: float, val: float,
    price_position: str,
    ssl: Optional[float], bsl: Optional[float],
    current_price: float
) -> str:
    lines = []

    # Market Structure
    lines.append(f"Market Structure: {structure}. Smart Money bias saat ini = {bias}.")

    # Value Area
    if price_position == "ABOVE_VALUE_AREA":
        lines.append(f"Harga ({current_price}) di atas Value Area (VAH={vah:.4f}). Ini zona PREMIUM — institusi cenderung jual di sini, retail cenderung beli (trap).")
    elif price_position == "BELOW_VALUE_AREA":
        lines.append(f"Harga ({current_price}) di bawah Value Area (VAL={val:.4f}). Ini zona DISCOUNT — potensi area akumulasi institusi.")
    else:
        lines.append(f"Harga ({current_price}) di dalam Value Area (VAL={val:.4f} – VAH={vah:.4f}). Area equilibrium — arah breakout menentukan bias selanjutnya.")
    lines.append(f"Point of Control (POC) = {poc:.4f}. Level ini adalah area paling banyak diperdagangkan — magnet harga kuat.")

    # Order Block
    if nearest_ob:
        ob_type = nearest_ob.get("type", "")
        ob_top  = nearest_ob.get("ob_top",  0)
        ob_bot  = nearest_ob.get("ob_bottom", 0)
        inst    = "Terkonfirmasi institutional" if nearest_ob.get("institutional_confirmed") else "Volume rata-rata"
        lines.append(f"Order Block terdekat: {ob_type} di zona {ob_bot:.4f}–{ob_top:.4f}. {inst}. Area ini adalah calon titik minat institusi.")

    # FVG
    if nearest_fvg:
        fvg_type = nearest_fvg.get("type", "")
        fvg_bot  = nearest_fvg.get("bottom", 0)
        fvg_top  = nearest_fvg.get("top", 0)
        lines.append(f"FVG (Imbalance) terdekat: {fvg_type} di {fvg_bot:.4f}–{fvg_top:.4f}. Harga secara statistik cenderung mengisi gap ini sebelum melanjutkan arah.")

    # Liquidity
    if ssl:
        lines.append(f"Sell-Side Liquidity (SSL) di {ssl:.4f} — stop-loss buyer terkumpul di atas level ini. Smart Money berpotensi menyapu area ini sebelum turun.")
    if bsl:
        lines.append(f"Buy-Side Liquidity (BSL) di {bsl:.4f} — stop-loss seller terkumpul di bawah level ini. Potensi hunt BSL sebelum reversal naik.")

    return "\n  ".join(lines)


# ─────────────────────────────────────────────────────────────────
#  MAIN: SATIN REASONING GENERATOR (STREAMING)
# ─────────────────────────────────────────────────────────────────

def get_satin_reasoning(ticker: str, apex_data: dict):
    """
    Generator yang melakukan streaming analisis Satin ke frontend.
    apex_data = hasil dari /api/apex-full/{ticker}
    """
    url = "http://localhost:11434/api/generate"

    # ── 1. EKSTRAK DATA ──────────────────────────────────────────
    price   = apex_data.get("price", 0)
    score_d = apex_data.get("apex_score", {})
    apex_score = score_d.get("score", 50)
    verdict    = score_d.get("verdict", "NEUTRAL")

    # Statistics
    stats      = apex_data.get("statistics", {})
    zscore_raw = stats.get("zscore", {}).get("current_zscore", 0)
    z_signal   = stats.get("zscore", {}).get("signal", "NEUTRAL")
    var_raw    = stats.get("var_cvar", {}).get("var_pct", 0)
    cvar_raw   = stats.get("var_cvar", {}).get("cvar_pct", 0)
    mc         = stats.get("monte_carlo", {})
    prob_profit = mc.get("probability_analysis", {}).get("prob_profit_pct", 50)
    worst_dd    = mc.get("drawdown_analysis", {}).get("worst_5pct_drawdown", 0)
    proj_worst  = mc.get("price_projections", {}).get("worst_5pct", price)
    proj_best   = mc.get("price_projections", {}).get("best_5pct", price)
    proj_median = mc.get("price_projections", {}).get("median_50pct", price)
    regime_d    = stats.get("regime", {})
    regime      = regime_d.get("market_regime", "UNKNOWN")
    hurst_val   = regime_d.get("hurst_exponent", 0.5)
    vol_30d     = regime_d.get("vol_30d_annualized", 0)

    # ICT
    ict        = apex_data.get("ict_analysis", {})
    smc_bias   = ict.get("composite_bias", "NEUTRAL")
    structure_d = ict.get("market_structure", {})
    structure  = structure_d.get("market_structure", "UNKNOWN")
    last_sh    = structure_d.get("last_swing_high", 0)
    last_sl_price = structure_d.get("last_swing_low", 0)
    ob_d       = ict.get("order_block", {})
    nearest_bull_ob = ob_d.get("nearest_bullish_ob")
    nearest_bear_ob = ob_d.get("nearest_bearish_ob")
    fvg_d      = ict.get("fvg_analysis", {})
    nearest_bull_fvg = fvg_d.get("nearest_bull_fvg")
    nearest_bear_fvg = fvg_d.get("nearest_bear_fvg")
    vp_d       = ict.get("volume_profile", {})
    poc        = vp_d.get("poc_price", 0)
    vah        = vp_d.get("vah_price", 0)
    val        = vp_d.get("val_price", 0)
    price_pos  = vp_d.get("price_position", "UNKNOWN")
    liq_d      = ict.get("liquidity_zones", {})
    ssl        = liq_d.get("nearest_ssl_target")
    bsl        = liq_d.get("nearest_bsl_target")
    liq_bias   = liq_d.get("liquidity_bias", "UNKNOWN")

    # Kelly
    kelly_d      = apex_data.get("kelly", {})
    kelly_edge   = kelly_d.get("edge_quality", "UNKNOWN")
    kelly_pct    = kelly_d.get("safe_kelly_pct", 0)
    dollar_risk  = kelly_d.get("dollar_risk_safe", 0)
    ev_pct       = kelly_d.get("expected_value_pct", 0)
    ruin_prob    = kelly_d.get("ruin_probability_pct", 99)

    # Quant
    quant       = apex_data.get("quant", {})
    sortino     = quant.get("sortino", 0)
    max_dd_quant = quant.get("max_drawdown", 0)

    # ── 2. PRE-INTERPRET DATA (jangan biarkan AI tebak sendiri) ──
    z_interp     = _interpret_zscore(zscore_raw)
    var_interp   = _interpret_var(var_raw)
    mc_interp    = _interpret_monte_carlo(prob_profit, worst_dd)
    regime_interp = _interpret_hurst(regime, hurst_val)
    kelly_interp = _interpret_kelly(kelly_edge, kelly_pct, dollar_risk)
    macro = apex_data.get("macro", {})
    dxy = macro.get("DXY", {})
    nasdaq = macro.get("NASDAQ", {})
    
    dxy_trend = dxy.get("trend", "UNKNOWN")
    dxy_pct = dxy.get("change_pct", 0)
    nasdaq_trend = nasdaq.get("trend", "UNKNOWN")
    nasdaq_pct = nasdaq.get("change_pct", 0)
    
    hmm = apex_data.get("hmm_regime", {})
    hmm_regime_str = hmm.get("regime", "UNKNOWN")
    hmm_conf = hmm.get("confidence", 0)
    
    fac = apex_data.get("factor_lab", {})
    mom_accel = fac.get("momentum_acceleration", "UNKNOWN")
    beta = fac.get("market_beta_nasdaq", 0)
    risk_mode = fac.get("risk_mode", "UNKNOWN")

    # Pilih OB dan FVG paling relevan berdasarkan bias
    if smc_bias == "BULLISH":
        nearest_ob  = nearest_bull_ob
        nearest_fvg = nearest_bull_fvg
    else:
        nearest_ob  = nearest_bear_ob
        nearest_fvg = nearest_bear_fvg

    ict_interp = _interpret_ict(
        bias=smc_bias, structure=structure,
        nearest_ob=nearest_ob, nearest_fvg=nearest_fvg,
        poc=poc, vah=vah, val=val,
        price_position=price_pos,
        ssl=ssl, bsl=bsl,
        current_price=price
    )
    apex_action = score_d.get("action", "No specific action")



    # ── 3. SUSUN PROMPT CHAIN-OF-THOUGHT ─────────────────────────
    prompt = f"""
<|system|>
Kamu adalah SATIN, AI Quantitative Risk Manager untuk platform trading institusional APEX QUANTUM COMMAND.

IDENTITASMU:
- Kamu BUKAN chatbot umum. Kamu adalah modul AI yang membaca output kalkulasi matematis dan mengubahnya menjadi narasi analisis yang presisi.
- Kamu WAJIB selalu menjelaskan KENAPA angka tersebut penting, BAGAIMANA pengaruhnya ke setup trading, dan KARENA APA kesimpulan tersebut bisa ditarik.
- Gaya bahasa: Profesional, dingin, tegas, seperti laporan Risk Committee di hedge fund. Bahasa Indonesia formal.
- DILARANG KERAS: menebak harga tanpa dasar data, menyebut "Graham Number", "PE Ratio", atau fundamental klasik.
- Jika data menunjukkan risiko tinggi, kamu WAJIB rekomendasikan STAND CLEAR meskipun trader ingin entry.

ATURAN REASONING (WAJIB DIPATUHI):
1. Setiap kesimpulan HARUS disertai alasan berbasis angka yang sudah diberikan.
2. Gunakan pola: "[Fakta angka] → [Interpretasi] → [Implikasi ke trading]"
3. Jangan pernah bilang "mungkin" atau "bisa jadi" tanpa menyebut probabilitas numeriknya.
4. Jika ada kontradiksi antar sinyal (misal: ICT bullish tapi Kelly no-edge), WAJIB jelaskan konflik tersebut dan berikan bobot yang lebih besar ke Kelly/Statistik.
<|/system|>

<|user|>
Analisis komprehensif ticker: {ticker}
Harga saat ini: {price}

==========================================================
BLOK A: KUANTIFIKASI RISIKO (STATISTIK KERAS)
==========================================================
A1. Z-Score: {z_interp}
A2. Value at Risk 95%: {var_interp}
A3. CVaR (Expected Shortfall): {cvar_raw:.2f}% — Jika VaR terlampaui, rata-rata kerugian harian yang SESUNGGUHNYA adalah angka ini.
A4. Monte Carlo (5.000 simulasi, 30 hari): {mc_interp}
    - Proyeksi harga worst 5%: {proj_worst:.4f}
    - Proyeksi harga median:   {proj_median:.4f}
    - Proyeksi harga best 5%:  {proj_best:.4f}
A5. Market Regime (Hurst Exponent): {regime_interp}
A6. Volatilitas Tahunan (30D Realized): {vol_30d:.2f}%
A7. Sortino Ratio: {sortino:.3f} {'(Positif: return adjusted untuk downside risk layak)' if sortino > 0 else '(Negatif: downside risk tidak terkompensasi oleh return)'}
A8. Max Historical Drawdown: {max_dd_quant:.2f}%

==========================================================
BLOK B: POSITION SIZING & EDGE (KELLY CRITERION)
==========================================================
B1. Kelly Edge Quality: {kelly_interp}
B2. Expected Value per Trade: {ev_pct:.4f}% {'(POSITIF — setup memiliki ekspektasi profit)' if ev_pct > 0 else '(NEGATIF — setup ini secara matematis merugi dalam jangka panjang)'}
B3. Probabilitas Ruin dengan sizing ini: {ruin_prob:.2f}%
B4. Maximum Dollar Risk yang diizinkan per trade: ${dollar_risk:.2f}

==========================================================
BLOK C: SMART MONEY & ICT CONTEXT
==========================================================
C1. {ict_interp}
C2. Swing High terakhir: {last_sh:.4f} | Swing Low terakhir: {last_sl_price:.4f}
C3. Liquidity Hunt Direction: {liq_bias}
    SSL (Stop Hunt Target Atas): {ssl if ssl else 'Tidak teridentifikasi'}
    BSL (Stop Hunt Target Bawah): {bsl if bsl else 'Tidak teridentifikasi'}

==========================================================
BLOK D: KEPUTUSAN FINAL SISTEM (WAJIB PATUH)
==========================================================
D1. Skor Komposit APEX: {apex_score}/100
D2. Verdict Sistem: {verdict}
D3. Rekomendasi Aksi: {apex_action}

==========================================================
BLOK E: MACRO & CROSS-ASSET INTELLIGENCE (HEDGE FUND VIEW)
==========================================================
E1. Global Assets: DXY (USD Index) is {dxy_trend} ({dxy_pct:.2f}%). 
    NASDAQ is {nasdaq_trend} ({nasdaq_pct:.2f}%).
E2. HMM Regime Detection: {hmm_regime_str} (Confidence: {hmm_conf:.1f}%).
E3. Factor Lab: Momentum is {mom_accel}. 
    Correlation to Nasdaq (Beta): {float(beta):.2f}.
E4. Risk Environment: {risk_mode}.

==========================================================
INSTRUKSI REASONING TAMBAHAN:
- Jika DXY UP dan NASDAQ DOWN, kamu harus SANGAT WASPADA terhadap setup LONG (Risk-Off condition).
- Gunakan HMM Regime sebagai filter utama. Jika HMM mendeteksi HIGH_VOL_BEARISH, abaikan sinyal bullish ICT kecuali ada divergensi ekstrem.
- Jelaskan hubungan antara korelasi Nasdaq dengan pergerakan {ticker} saat ini.
...

==========================================================
INSTRUKSI REASONING (WAJIB IKUTI URUTAN INI):
==========================================================
1. Kamu DILARANG membuat skor sendiri. Gunakan skor {apex_score}/100 yang sudah dihitung sistem.
2. Jelaskan MENGAPA skor tersebut {apex_score} berdasarkan data di Blok A, B, dan C.
3. Jangan pernah menyebut angka skor yang berbeda dari {apex_score} di bagian mana pun dalam analisis.
==========================================================
INSTRUKSI REASONING (WAJIB IKUTI URUTAN INI):
==========================================================
Kamu HARUS menjawab dalam format di bawah ini, tanpa pengecualian:

[CHAIN OF THOUGHT — BERPIKIR DULU, JANGAN LONCAT KE KESIMPULAN]
Sebelum menyimpulkan, lakukan analisis bertahap:
LANGKAH 1 — Baca sinyal risiko (Z-Score, VaR, CVaR). Apakah kondisi statistik mendukung entry atau tidak? Kenapa?
LANGKAH 2 — Baca Kelly Edge dan Expected Value. Apakah ada edge matematis? Jika EV negatif, apa implikasinya?
LANGKAH 3 — Baca ICT Context. Apakah Smart Money positioning mendukung arah bias? Di mana area instituasional terdekat?
LANGKAH 4 — Apakah ada konflik antar sinyal? Resolusikan konflik dengan memberi bobot lebih ke data statistik.
LANGKAH 5 — Tentukan verdict akhir berdasarkan 4 langkah di atas.

[EXECUTIVE SUMMARY]
Tulis 3 kalimat ringkasan: (1) kondisi statistik aset, (2) kualitas edge matematis, (3) positioning Smart Money saat ini.

[ANALISIS RISIKO KUANTITATIF]
Jelaskan secara spesifik:
- Mengapa Z-Score {zscore_raw:.2f} relevan untuk keputusan entry saat ini
- Apa arti VaR {var_raw:.2f}% dalam konteks sizing untuk akun $30,000
- Bagaimana Monte Carlo menunjukkan distribusi kemungkinan outcome
- Mengapa market regime saat ini ({regime}) mempengaruhi pemilihan strategi

[ANALISIS SMART MONEY]
Jelaskan secara spesifik:
- Mengapa posisi harga terhadap Value Area (POC={poc:.4f}) memiliki implikasi ke arah institusi
- Bagaimana Order Block dan FVG terdekat menjadi area minat (dan kenapa institusi berminat di sana)
- Mengapa target likuiditas {ssl if ssl else 'N/A'} atau {bsl if bsl else 'N/A'} relevan untuk proyeksi pergerakan

[TRADE SETUP — JIKA DIEKSEKUSI]
Berikan setup konkret HANYA jika APEX Score ≥ 45 DAN Kelly Edge bukan NO_EDGE:
- Entry Zone: (area spesifik berdasarkan OB/FVG/POC, bukan angka acak)
- Stop Loss: (berdasarkan Swing High/Low atau batas OB, dengan alasan)
- Take Profit 1 (1R): (dengan alasan kenapa level ini)
- Take Profit 2 (2R): (dengan alasan kenapa level ini)  
- Maximum Position Size: ${dollar_risk:.2f} (sesuai Kelly Criterion)
- Risk/Reward: (hitungan aktual dari angka di atas)
Jika tidak qualified, tulis: "TRADE SETUP: TIDAK TERSEDIA — Setup tidak memenuhi threshold APEX."

[SATIN FINAL VERDICT]
Tulis satu dari tiga ini dalam HURUF KAPITAL, diikuti 1 kalimat alasan singkat yang menyebut angka:
  EXECUTE LONG — karena [alasan spesifik dengan angka]
  EXECUTE SHORT — karena [alasan spesifik dengan angka]
  STAND CLEAR — karena [alasan spesifik dengan angka]
<|/user|>
"PENTING: Jaga agar analisis tetap padat dan teknis. Fokus pada angka. Jangan mengulang instruksi. Langsung berikan verdict setelah analisis selesai."
<|assistant|>
"""

    # ── 4. KIRIM KE OLLAMA & STREAM ──────────────────────────────
    try:
        response = requests.post(
            url,
            json={
                "model"  : "deepseek-r1:8b",
                "prompt" : prompt,
                "stream" : True,
                "options": {
                    "num_predict"     : 8060,
                    "num_ctx": 10240,
                    "temperature"     : 0.1,   # Sangat rendah = deterministik, tidak halu
                    "top_p"           : 0.9,
                    "repeat_penalty"  : 1.1,   # Cegah pengulangan kata
                    "stop"            : ["<|user|>", "<|system|>"]  # Hard stop
                }
            },
            stream=True,
            timeout=300
        )

        if response.status_code != 200:
            yield f"\n⚠️ SATIN ERROR: Ollama mengembalikan status {response.status_code}. Pastikan Ollama aktif dan model 'deepseek-r1:8b' sudah di-pull.\n"
            return

        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                # Karena chunk berupa bytes, kita decode dan parse JSON-nya
                chunk_str = chunk.decode('utf-8')
                # Hati-hati, satu chunk bisa berisi beberapa baris JSON
                lines = chunk_str.strip().split('\n')
                for line in lines:
                    if line:
                        try:
                            decoded = json.loads(line)
                            token = decoded.get('response', '')
                            if token:
                                yield token
                            if decoded.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue

    except requests.exceptions.ConnectionError:
        yield "\n\n⛔ SATIN CONNECTION ERROR: Gagal terhubung ke Ollama.\n"
    except requests.exceptions.Timeout:
        yield "\n\n⛔ SATIN TIMEOUT: Model butuh waktu lebih dari 5 menit untuk berpikir.\n"
    except Exception as e:
        yield f"\n\n⛔ SATIN INTERNAL ERROR: {str(e)}\n"


# ─────────────────────────────────────────────────────────────────
#  BONUS: QUICK SANITY CHECK (tanpa streaming, untuk testing)
# ─────────────────────────────────────────────────────────────────

def quick_satin_check(apex_data: dict) -> dict:
    """
    Non-streaming version untuk validasi cepat.
    Return dict berisi sinyal-sinyal kunci yang sudah diinterpretasi.
    Berguna untuk dashboard tile atau alert system.
    """
    stats  = apex_data.get("statistics", {})
    kelly  = apex_data.get("kelly", {})
    ict    = apex_data.get("ict_analysis", {})
    score  = apex_data.get("apex_score", {}).get("score", 50)

    z      = stats.get("zscore", {}).get("current_zscore", 0)
    edge   = kelly.get("edge_quality", "UNKNOWN")
    ev     = kelly.get("expected_value_pct", 0)
    bias   = ict.get("composite_bias", "NEUTRAL")
    regime = stats.get("regime", {}).get("market_regime", "UNKNOWN")
    prob   = stats.get("monte_carlo", {}).get("probability_analysis", {}).get("prob_profit_pct", 50)
    var    = stats.get("var_cvar", {}).get("var_pct", 0)

    # Quick verdict logic
    if edge == "NO_EDGE" or ev < 0:
        verdict = "STAND CLEAR"
        reason  = f"Expected Value negatif ({ev:.4f}%). Trading setup ini merugi dalam jangka panjang secara matematis."
    elif score >= 70 and bias == "BULLISH" and edge in ("MODERATE", "STRONG"):
        verdict = "EXECUTE LONG"
        reason  = f"APEX Score {score}/100, ICT Bias BULLISH, Kelly Edge {edge}, EV={ev:.4f}%."
    elif score <= 30 and bias == "BEARISH" and edge in ("MODERATE", "STRONG"):
        verdict = "EXECUTE SHORT"
        reason  = f"APEX Score {score}/100, ICT Bias BEARISH, Kelly Edge {edge}, EV={ev:.4f}%."
    else:
        verdict = "STAND CLEAR"
        reason  = f"APEX Score {score}/100 — belum memenuhi threshold 70 (long) atau 30 (short). Tunggu konfirmasi."

    return {
        "ticker"         : apex_data.get("ticker", "?"),
        "price"          : apex_data.get("price", 0),
        "apex_score"     : score,
        "quick_verdict"  : verdict,
        "reason"         : reason,
        "key_signals"    : {
            "zscore"         : round(z, 3),
            "z_interpretation": _interpret_zscore(z),
            "kelly_edge"     : edge,
            "expected_value" : round(ev, 4),
            "ict_bias"       : bias,
            "market_regime"  : regime,
            "prob_profit_pct": round(prob, 2),
            "var_95_pct"     : round(var, 4),
        }
    }