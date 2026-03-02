"""
╔══════════════════════════════════════════════════════════════════╗
║              APEX ICT / SMC INTELLIGENCE ENGINE                  ║
║   Volume Profile · FVG · Order Block · Liquidity · BoS · CHoCH  ║
╚══════════════════════════════════════════════════════════════════╝

Implementasi matematis konsep Smart Money Concept (SMC) dan
Inner Circle Trader (ICT) untuk identifikasi Point of Interest (POI)
secara otomatis tanpa bias interpretasi manual.

Referensi:
  - ICT Mentorship 2022 (Michael Huddleston)
  - Volume Profile (TPO/VAH/VAL/POC)
  - Order Flow: Delta Volume Analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')


# ─────────────────────────────────────────────────────────────────
#  1. FAIR VALUE GAP (FVG) DETECTOR — Matematis
# ─────────────────────────────────────────────────────────────────

def detect_fvg(df: pd.DataFrame, min_gap_pct: float = 0.1) -> Dict:
    """
    Deteksi Fair Value Gap (Imbalance) secara matematis.

    Definisi Matematis:
      Bullish FVG: High[i-2] < Low[i]   → Gap di bawah candle 3
      Bearish FVG: Low[i-2]  > High[i]  → Gap di atas candle 3

    Validasi kekuatan: Gap harus ≥ min_gap_pct% dari harga untuk dianggap signifikan.

    Args:
        df          : OHLCV DataFrame
        min_gap_pct : Minimum gap size (% dari harga) agar FVG valid
    """
    required = {'Open', 'High', 'Low', 'Close'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data OHLCV tidak valid"}

    bullish_fvgs = []
    bearish_fvgs = []

    for i in range(2, len(df)):
        h_prev2  = float(df['High'].iloc[i-2])
        l_prev2  = float(df['Low'].iloc[i-2])
        h_curr   = float(df['High'].iloc[i])
        l_curr   = float(df['Low'].iloc[i])
        c_curr   = float(df['Close'].iloc[i])
        mid_close = float(df['Close'].iloc[i-1])
        ts       = df.index[i].strftime('%Y-%m-%d') if hasattr(df.index[i], 'strftime') else str(df.index[i])

        # ── Bullish FVG ──
        if l_curr > h_prev2:
            gap_size    = l_curr - h_prev2
            gap_pct     = (gap_size / h_prev2) * 100
            equilibrium = (l_curr + h_prev2) / 2
            if gap_pct >= min_gap_pct:
                bullish_fvgs.append({
                    "type"       : "BULLISH_FVG",
                    "date"       : ts,
                    "top"        : round(l_curr, 6),
                    "bottom"     : round(h_prev2, 6),
                    "equilibrium": round(equilibrium, 6),
                    "gap_size"   : round(gap_size, 6),
                    "gap_pct"    : round(gap_pct, 4),
                    "strength"   : "STRONG" if gap_pct > 0.5 else "MODERATE",
                    "filled"     : bool(c_curr < h_prev2)
                })

        # ── Bearish FVG ──
        elif h_curr < l_prev2:
            gap_size    = l_prev2 - h_curr
            gap_pct     = (gap_size / l_prev2) * 100
            equilibrium = (l_prev2 + h_curr) / 2
            if gap_pct >= min_gap_pct:
                bearish_fvgs.append({
                    "type"       : "BEARISH_FVG",
                    "date"       : ts,
                    "top"        : round(l_prev2, 6),
                    "bottom"     : round(h_curr, 6),
                    "equilibrium": round(equilibrium, 6),
                    "gap_size"   : round(gap_size, 6),
                    "gap_pct"    : round(gap_pct, 4),
                    "strength"   : "STRONG" if gap_pct > 0.5 else "MODERATE",
                    "filled"     : bool(c_curr > l_prev2)
                })

    # Ambil yang paling recent & belum terfill
    unfilled_bull = [f for f in bullish_fvgs if not f['filled']][-5:]
    unfilled_bear = [f for f in bearish_fvgs if not f['filled']][-5:]

    return {
        "total_bullish_fvg"  : len(bullish_fvgs),
        "total_bearish_fvg"  : len(bearish_fvgs),
        "unfilled_bullish"   : unfilled_bull,
        "unfilled_bearish"   : unfilled_bear,
        "nearest_bull_fvg"   : unfilled_bull[-1] if unfilled_bull else None,
        "nearest_bear_fvg"   : unfilled_bear[-1] if unfilled_bear else None,
        "fvg_bias"           : "BULLISH" if len(unfilled_bull) > len(unfilled_bear) else "BEARISH" if len(unfilled_bear) > len(unfilled_bull) else "NEUTRAL"
    }


# ─────────────────────────────────────────────────────────────────
#  2. ORDER BLOCK DETECTOR
# ─────────────────────────────────────────────────────────────────

def detect_order_blocks(df: pd.DataFrame, lookback: int = 50) -> Dict:
    """
    Deteksi Order Block (OB) — area di mana institusi meninggalkan order besar.

    Logika Matematis:
      Bullish OB = Candle bearish (Close < Open) yang segera diikuti oleh
                   impulse naik yang lebih besar (Break of Structure ke atas)
      Bearish OB = Candle bullish (Close > Open) yang diikuti impulse turun

    Validasi: OB dikonfirmasi hanya jika body candle > 1.5× average body size.
    """
    required = {'Open', 'High', 'Low', 'Close', 'Volume'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data OHLCV+Volume diperlukan"}

    df_slice  = df.tail(lookback).copy()
    bodies    = np.abs(df_slice['Close'] - df_slice['Open'])
    avg_body  = float(bodies.mean())
    
    bullish_obs = []
    bearish_obs = []
    current_price = float(df['Close'].iloc[-1])

    for i in range(1, len(df_slice) - 1):
        o, h, l, c = (
            float(df_slice['Open'].iloc[i]),
            float(df_slice['High'].iloc[i]),
            float(df_slice['Low'].iloc[i]),
            float(df_slice['Close'].iloc[i])
        )
        vol = float(df_slice['Volume'].iloc[i])
        avg_vol = float(df_slice['Volume'].mean())
        ts  = df_slice.index[i].strftime('%Y-%m-%d') if hasattr(df_slice.index[i], 'strftime') else str(df_slice.index[i])

        body_size   = abs(c - o)
        is_large_body = body_size > avg_body * 1.5
        is_high_vol   = vol > avg_vol * 1.2  # Volume validasi institusional

        next_close = float(df_slice['Close'].iloc[i+1])
        next_high  = float(df_slice['High'].iloc[i+1])
        next_low   = float(df_slice['Low'].iloc[i+1])

        # ── Bullish OB (Bearish candle before bullish impulse) ──
        if c < o and is_large_body and next_close > h:
            distance_pct = abs(current_price - l) / l * 100
            bullish_obs.append({
                "type"           : "BULLISH_OB",
                "date"           : ts,
                "ob_top"         : round(o, 6),   # Top of bearish candle body
                "ob_bottom"      : round(c, 6),   # Bottom of bearish candle body
                "ob_high"        : round(h, 6),
                "ob_low"         : round(l, 6),
                "volume"         : round(vol, 2),
                "vol_vs_avg_pct" : round((vol / avg_vol - 1) * 100, 2),
                "institutional_confirmed": is_high_vol,
                "distance_from_price_pct": round(distance_pct, 2),
                "is_above_price" : bool(l > current_price),
                "is_below_price" : bool(o < current_price)
            })

        # ── Bearish OB (Bullish candle before bearish impulse) ──
        elif c > o and is_large_body and next_close < l:
            distance_pct = abs(current_price - h) / h * 100
            bearish_obs.append({
                "type"           : "BEARISH_OB",
                "date"           : ts,
                "ob_top"         : round(c, 6),   # Top of bullish candle body
                "ob_bottom"      : round(o, 6),   # Bottom of bullish candle body
                "ob_high"        : round(h, 6),
                "ob_low"         : round(l, 6),
                "volume"         : round(vol, 2),
                "vol_vs_avg_pct" : round((vol / avg_vol - 1) * 100, 2),
                "institutional_confirmed": is_high_vol,
                "distance_from_price_pct": round(distance_pct, 2),
                "is_above_price" : bool(o > current_price),
                "is_below_price" : bool(c < current_price)
            })

    # Sort by proximity to current price
    bullish_obs.sort(key=lambda x: x['distance_from_price_pct'])
    bearish_obs.sort(key=lambda x: x['distance_from_price_pct'])

    return {
        "current_price"      : current_price,
        "total_bullish_ob"   : len(bullish_obs),
        "total_bearish_ob"   : len(bearish_obs),
        "nearest_bullish_ob" : bullish_obs[0] if bullish_obs else None,
        "nearest_bearish_ob" : bearish_obs[0] if bearish_obs else None,
        "all_bullish_obs"    : bullish_obs[:5],
        "all_bearish_obs"    : bearish_obs[:5],
        "ob_bias"            : "BULLISH" if len(bullish_obs) > len(bearish_obs) else "BEARISH" if len(bearish_obs) > len(bullish_obs) else "NEUTRAL"
    }


# ─────────────────────────────────────────────────────────────────
#  3. VOLUME PROFILE (POC, VAH, VAL)
# ─────────────────────────────────────────────────────────────────

def calculate_volume_profile(df: pd.DataFrame, bins: int = 50) -> Dict:
    """
    Hitung Volume Profile untuk identifikasi area nilai (Value Area).

    Konsep:
      POC  = Price of Control (harga dengan volume terbesar)
      VAH  = Value Area High (70% volume di bawah ini)
      VAL  = Value Area Low  (70% volume di atas ini)

    Institusi cenderung defend POC sebagai support/resistance kuat.
    """
    required = {'High', 'Low', 'Close', 'Volume'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data diperlukan"}

    # Buat bins harga dari Low hingga High keseluruhan
    price_min = float(df['Low'].min())
    price_max = float(df['High'].max())
    price_bins = np.linspace(price_min, price_max, bins + 1)
    bin_labels = [(price_bins[i] + price_bins[i+1]) / 2 for i in range(bins)]

    # Alokasikan volume ke setiap price bin
    volume_at_price = np.zeros(bins)
    for idx, row in df.iterrows():
        h, l, vol = float(row['High']), float(row['Low']), float(row['Volume'])
        if h == l:
            bin_idx = np.searchsorted(price_bins, l, side='right') - 1
            bin_idx = min(max(bin_idx, 0), bins - 1)
            volume_at_price[bin_idx] += vol
        else:
            vol_per_unit = vol / (h - l)
            for b_idx in range(bins):
                bl, bh = price_bins[b_idx], price_bins[b_idx + 1]
                overlap = max(0, min(h, bh) - max(l, bl))
                volume_at_price[b_idx] += vol_per_unit * overlap

    # POC = bin dengan volume terbesar
    poc_idx   = int(np.argmax(volume_at_price))
    poc_price = float(bin_labels[poc_idx])

    # Value Area (70% volume)
    total_vol  = float(np.sum(volume_at_price))
    target_vol = total_vol * 0.70
    va_vol     = float(volume_at_price[poc_idx])

    # Expand dari POC ke atas dan bawah sampai 70% terpenuhi
    vah_idx = poc_idx
    val_idx = poc_idx
    while va_vol < target_vol:
        up_gain   = volume_at_price[vah_idx + 1] if vah_idx + 1 < bins else 0
        down_gain = volume_at_price[val_idx - 1] if val_idx - 1 >= 0 else 0
        if up_gain >= down_gain and vah_idx + 1 < bins:
            vah_idx += 1
            va_vol  += up_gain
        elif val_idx - 1 >= 0:
            val_idx -= 1
            va_vol  += down_gain
        else:
            break

    vah_price     = float(bin_labels[vah_idx])
    val_price     = float(bin_labels[val_idx])
    current_price = float(df['Close'].iloc[-1])

    # Interpretasi posisi harga vs Value Area
    if current_price > vah_price:
        position = "ABOVE_VALUE_AREA"
        interpretation = "Harga di atas Value Area — Premium zone, potensi pullback ke VAH."
    elif current_price < val_price:
        position = "BELOW_VALUE_AREA"
        interpretation = "Harga di bawah Value Area — Discount zone, potensi bounce ke VAL."
    else:
        position = "INSIDE_VALUE_AREA"
        interpretation = "Harga dalam Value Area — Area equilbrium, bias netral."

    return {
        "poc_price"      : round(poc_price, 4),
        "vah_price"      : round(vah_price, 4),
        "val_price"      : round(val_price, 4),
        "current_price"  : round(current_price, 4),
        "price_position" : position,
        "interpretation" : interpretation,
        "value_area_width_pct": round(((vah_price - val_price) / poc_price) * 100, 2),
        "dist_to_poc_pct"     : round(abs(current_price - poc_price) / poc_price * 100, 4),
        "dist_to_vah_pct"     : round(abs(current_price - vah_price) / vah_price * 100, 4),
        "dist_to_val_pct"     : round(abs(current_price - val_price) / val_price * 100, 4),
        "volume_profile"      : [
            {"price": round(float(bin_labels[i]), 4), "volume": round(float(volume_at_price[i]), 2)}
            for i in range(bins)
        ]
    }


# ─────────────────────────────────────────────────────────────────
#  4. LIQUIDITY ZONES (Equal Highs/Lows)
# ─────────────────────────────────────────────────────────────────

def detect_liquidity_zones(df: pd.DataFrame, tolerance_pct: float = 0.1) -> Dict:
    """
    Deteksi zona likuiditas (Equal Highs & Equal Lows).

    Logic: Jika dua atau lebih candle memiliki High/Low yang hampir sama
    (dalam tolerance %), ini adalah liquidity pool — area di mana stop-loss
    banyak trader berkumpul (target Smart Money).

    Args:
        tolerance_pct: Persentase toleransi untuk menganggap dua harga "equal" (default 0.1%)
    """
    required = {'High', 'Low', 'Close'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data tidak valid"}

    current_price = float(df['Close'].iloc[-1])
    highs = df['High'].values.astype(float)
    lows  = df['Low'].values.astype(float)
    dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in df.index]

    equal_highs = []
    equal_lows  = []

    # Scan Equal Highs (Sell-Side Liquidity)
    for i in range(len(highs)):
        cluster = [i]
        for j in range(i + 1, len(highs)):
            if abs(highs[i] - highs[j]) / highs[i] * 100 <= tolerance_pct:
                cluster.append(j)
        if len(cluster) >= 2:
            avg_price = float(np.mean([highs[k] for k in cluster]))
            equal_highs.append({
                "type"         : "SELL_SIDE_LIQUIDITY",
                "price_level"  : round(avg_price, 6),
                "touches"      : len(cluster),
                "dates"        : [dates[k] for k in cluster],
                "above_price"  : bool(avg_price > current_price),
                "distance_pct" : round(abs(avg_price - current_price) / current_price * 100, 4),
                "strength"     : "STRONG" if len(cluster) >= 3 else "MODERATE"
            })

    # Scan Equal Lows (Buy-Side Liquidity)
    for i in range(len(lows)):
        cluster = [i]
        for j in range(i + 1, len(lows)):
            if abs(lows[i] - lows[j]) / lows[i] * 100 <= tolerance_pct:
                cluster.append(j)
        if len(cluster) >= 2:
            avg_price = float(np.mean([lows[k] for k in cluster]))
            equal_lows.append({
                "type"         : "BUY_SIDE_LIQUIDITY",
                "price_level"  : round(avg_price, 6),
                "touches"      : len(cluster),
                "dates"        : [dates[k] for k in cluster],
                "below_price"  : bool(avg_price < current_price),
                "distance_pct" : round(abs(avg_price - current_price) / current_price * 100, 4),
                "strength"     : "STRONG" if len(cluster) >= 3 else "MODERATE"
            })

    # Dedup & sort by proximity
    eq_highs_deduped = _dedup_zones(equal_highs, 'price_level')
    eq_lows_deduped  = _dedup_zones(equal_lows, 'price_level')

    eq_highs_sorted  = sorted(eq_highs_deduped, key=lambda x: x['distance_pct'])[:5]
    eq_lows_sorted   = sorted(eq_lows_deduped,  key=lambda x: x['distance_pct'])[:5]

    # Nearest targets for Smart Money hunt
    nearest_ssl = min([z['price_level'] for z in eq_highs_sorted if z['above_price']], default=None) if eq_highs_sorted else None
    nearest_bsl = max([z['price_level'] for z in eq_lows_sorted if z['below_price']], default=None) if eq_lows_sorted else None

    return {
        "current_price"         : current_price,
        "sell_side_liquidity"   : eq_highs_sorted,
        "buy_side_liquidity"    : eq_lows_sorted,
        "nearest_ssl_target"    : round(nearest_ssl, 6) if nearest_ssl else None,
        "nearest_bsl_target"    : round(nearest_bsl, 6) if nearest_bsl else None,
        "liquidity_bias"        : "HUNT_ABOVE" if nearest_ssl and (not nearest_bsl or nearest_ssl - current_price < current_price - nearest_bsl) else "HUNT_BELOW",
        "description"           : "SSL = Stop-loss sell orders terkumpul (target Long squeeze). BSL = Stop-loss buy orders (target Short squeeze)."
    }


# ─────────────────────────────────────────────────────────────────
#  5. BREAK OF STRUCTURE (BoS) & CHANGE OF CHARACTER (CHoCH)
# ─────────────────────────────────────────────────────────────────

def detect_market_structure(df: pd.DataFrame, swing_lookback: int = 5) -> Dict:
    """
    Deteksi Break of Structure (BoS) dan Change of Character (CHoCH).

    BoS   = Market meneruskan tren (Higher High / Lower Low)
    CHoCH = Market membalik tren (Higher Low patah ke bawah / Lower High patah ke atas)
    """
    required = {'High', 'Low', 'Close'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {"error": "Data tidak valid"}

    df_s      = df.tail(100).copy()
    highs     = df_s['High'].values.astype(float)
    lows      = df_s['Low'].values.astype(float)
    closes    = df_s['Close'].values.astype(float)

    swing_highs = []
    swing_lows  = []
    lb = swing_lookback

    for i in range(lb, len(highs) - lb):
        if highs[i] == max(highs[i-lb:i+lb+1]):
            swing_highs.append((i, highs[i]))
        if lows[i] == min(lows[i-lb:i+lb+1]):
            swing_lows.append((i, lows[i]))

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"error": "Tidak cukup swing point untuk analisis struktur"}

    # Trend Analysis berdasarkan swing
    sh_trend = "BULLISH" if swing_highs[-1][1] > swing_highs[-2][1] else "BEARISH"
    sl_trend = "BULLISH" if swing_lows[-1][1]  > swing_lows[-2][1]  else "BEARISH"

    current_price = float(closes[-1])
    last_sh       = swing_highs[-1][1]
    last_sl       = swing_lows[-1][1]
    prev_sh       = swing_highs[-2][1]
    prev_sl       = swing_lows[-2][1]

    events = []
    # BoS Bullish: Current close > last swing high
    if current_price > last_sh:
        events.append({"type": "BOS_BULLISH",  "level": round(last_sh, 6), "description": f"Break of Structure Bullish — Harga menembus SH terakhir di {last_sh:.2f}"})
    # BoS Bearish: Current close < last swing low
    if current_price < last_sl:
        events.append({"type": "BOS_BEARISH",  "level": round(last_sl, 6), "description": f"Break of Structure Bearish — Harga menembus SL terakhir di {last_sl:.2f}"})
    # CHoCH Bullish: Dari downtrend, SH baru lebih tinggi
    if sh_trend == "BULLISH" and sl_trend == "BULLISH" and swing_highs[-2][1] < swing_lows[-1][1]:
        events.append({"type": "CHOCH_BULLISH", "level": round(prev_sl, 6), "description": "Change of Character Bullish — Potensi pembalikan tren ke atas."})
    # CHoCH Bearish
    if sh_trend == "BEARISH" and sl_trend == "BEARISH":
        events.append({"type": "CHOCH_BEARISH", "level": round(prev_sh, 6), "description": "Change of Character Bearish — Potensi pembalikan tren ke bawah."})

    # Overall Market Structure
    if sh_trend == "BULLISH" and sl_trend == "BULLISH":
        structure = "UPTREND"
        bias = "BULLISH"
    elif sh_trend == "BEARISH" and sl_trend == "BEARISH":
        structure = "DOWNTREND"
        bias = "BEARISH"
    else:
        structure = "TRANSITION"
        bias = "NEUTRAL"

    return {
        "current_price"    : current_price,
        "market_structure" : structure,
        "bias"             : bias,
        "last_swing_high"  : round(last_sh, 6),
        "last_swing_low"   : round(last_sl, 6),
        "prev_swing_high"  : round(prev_sh, 6),
        "prev_swing_low"   : round(prev_sl, 6),
        "sh_trend"         : sh_trend,
        "sl_trend"         : sl_trend,
        "events"           : events,
        "total_swing_highs": len(swing_highs),
        "total_swing_lows" : len(swing_lows),
    }


# ─────────────────────────────────────────────────────────────────
#  6. ICT FULL ANALYSIS — ONE-CALL COMPOSITE
# ─────────────────────────────────────────────────────────────────

def get_ict_full_analysis(df: pd.DataFrame) -> Dict:
    """
    Jalankan semua analisis ICT/SMC sekaligus dan hasilkan sinyal komposit.
    """
    fvg       = detect_fvg(df)
    ob        = detect_order_blocks(df)
    vp        = calculate_volume_profile(df)
    liq       = detect_liquidity_zones(df)
    structure = detect_market_structure(df)

    # ── Composite Bias Scoring ──
    bullish_score = 0
    bearish_score = 0

    if isinstance(fvg, dict) and fvg.get('fvg_bias') == 'BULLISH':    bullish_score += 1
    if isinstance(fvg, dict) and fvg.get('fvg_bias') == 'BEARISH':    bearish_score += 1
    if isinstance(ob,  dict) and ob.get('ob_bias')  == 'BULLISH':     bullish_score += 1
    if isinstance(ob,  dict) and ob.get('ob_bias')  == 'BEARISH':     bearish_score += 1
    if isinstance(structure, dict) and structure.get('bias') == 'BULLISH': bullish_score += 2
    if isinstance(structure, dict) and structure.get('bias') == 'BEARISH': bearish_score += 2
    if isinstance(vp, dict) and vp.get('price_position') == 'BELOW_VALUE_AREA': bullish_score += 1
    if isinstance(vp, dict) and vp.get('price_position') == 'ABOVE_VALUE_AREA': bearish_score += 1

    if bullish_score > bearish_score:
        composite_bias = "BULLISH"
        bias_strength  = f"{bullish_score}/{bullish_score + bearish_score}"
    elif bearish_score > bullish_score:
        composite_bias = "BEARISH"
        bias_strength  = f"{bearish_score}/{bullish_score + bearish_score}"
    else:
        composite_bias = "NEUTRAL"
        bias_strength  = "Contested"

    return {
        "composite_bias"   : composite_bias,
        "bias_strength"    : bias_strength,
        "bullish_factors"  : bullish_score,
        "bearish_factors"  : bearish_score,
        "fvg_analysis"     : fvg,
        "order_block"      : ob,
        "volume_profile"   : vp,
        "liquidity_zones"  : liq,
        "market_structure" : structure
    }


# ─────────────────────────────────────────────────────────────────
#  PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────

def _dedup_zones(zones: List[Dict], key: str, tolerance_pct: float = 0.2) -> List[Dict]:
    """Hapus duplikat zona yang terlalu dekat satu sama lain."""
    if not zones:
        return []
    deduped = [zones[0]]
    for zone in zones[1:]:
        is_dup = any(
            abs(zone[key] - d[key]) / max(d[key], 1e-10) * 100 < tolerance_pct
            for d in deduped
        )
        if not is_dup:
            deduped.append(zone)
    return deduped