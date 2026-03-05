"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          APEX ALPHA SIGNALS ENGINE v1.0                                     ║
║   Funding Rate Carry · Open Interest Signal · Composite Alpha Scorer        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  WHY THIS IS FREE ALPHA:                                                     ║
║                                                                              ║
║  FUNDING RATE SIGNAL                                                         ║
║  ─────────────────────                                                       ║
║  Perpetual futures mempertahankan harga track dengan spot melalui           ║
║  funding mechanism:                                                           ║
║                                                                              ║
║    • Rate > 0: longs bayar shorts (market terlalu long/bullish)             ║
║    • Rate < 0: shorts bayar longs (market terlalu short/bearish)            ║
║    • Rate dibayar setiap 1 jam (Hyperliquid) atau 8 jam (Binance)          ║
║                                                                              ║
║  Dua jenis alpha:                                                            ║
║  (A) CARRY TRADE: Long perp saat rate negatif → dapat bayaran               ║
║                   Short perp saat rate positif → dapat bayaran              ║
║      Formula: Annual carry = rate × payments_per_year                       ║
║               HL: 0.01% × 24 × 365 = 87.6% APY jika rate konsisten!       ║
║                                                                              ║
║  (B) CONTRARIAN SIGNAL: Rate ekstrem → pasar terlalu crowded satu arah     ║
║      rate > +0.10% → too many longs → reversal risk → SHORT bias           ║
║      rate < −0.05% → too many shorts → short squeeze → LONG bias           ║
║                                                                              ║
║  OPEN INTEREST SIGNAL                                                        ║
║  ─────────────────────                                                       ║
║  OI = total contracts outstanding (proxy untuk "conviction" pasar)           ║
║                                                                              ║
║  Pattern 1 — Distribution:                                                   ║
║    OI rising + price rising → genuine buying (BULLISH confirmation)         ║
║    OI rising + price falling → bearish conviction (BEARISH confirmation)    ║
║                                                                              ║
║  Pattern 2 — Capitulation:                                                   ║
║    OI falling + price falling → shorts covering (LONG opportunity soon)     ║
║    OI falling + price rising → longs taking profit (weakening rally)        ║
║                                                                              ║
║  Pattern 3 — Compression:                                                    ║
║    OI spike → impending volatility (spread bets, reduce position)           ║
║    OI collapse → forced liquidation cascade (opportunity or danger)          ║
║                                                                              ║
║  COMPOSITE ALPHA SCORER                                                      ║
║  ─────────────────────────                                                   ║
║  Combines funding + OI + signal intelligence into one pre-trade score       ║
║  that integrates with apex_meta_allocator for final capital decision.       ║
║                                                                              ║
║  INTEGRATION:                                                                ║
║  ─────────────                                                               ║
║  This engine polls Hyperliquid /info endpoint (same as hft_engine.py)       ║
║  with async support. In sync contexts, use FundingRateCache which           ║
║  stores the last-fetched values and refreshes on a schedule.                ║
║                                                                              ║
║  DEPENDENCIES: numpy, aiohttp (already in stack)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE:
    import asyncio
    from apex_alpha_signals import AlphaSignalEngine

    engine = AlphaSignalEngine(coins=["BTC", "ETH", "SOL"])

    # Async (recommended — non-blocking)
    await engine.refresh_async()

    result = engine.get_alpha("BTC")
    # {
    #   "funding_rate_pct"    : 0.0082,    # annualized ~72% APY
    #   "funding_signal"      : "SHORT_BIAS",  # market too long
    #   "funding_carry_usd"   : 0.29,          # per $100 position per hour
    #   "oi_trend"            : "RISING",
    #   "oi_price_pattern"    : "BULLISH_CONFIRM",
    #   "oi_signal"           : "BULLISH",
    #   "composite_alpha"     : 0.71,          # 0-1
    #   "recommended_bias"    : "SHORT",
    #   "size_scalar"         : 0.85,          # adjust size for alpha
    # }
"""

from __future__ import annotations

import asyncio
import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Deque

import numpy as np

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

_EPS = 1e-12
HL_INFO_URL = "https://api.hyperliquid.xyz/info"


# ══════════════════════════════════════════════════════════════════════════════
#  DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FundingSnapshot:
    coin           : str
    funding_rate   : float      # per-payment rate (e.g. 0.0001 = 0.01%)
    payment_interval_h: float   # hours between payments (HL=1, Binance=8)
    timestamp      : float      # unix timestamp
    premium        : float = 0.0   # price premium vs index
    open_interest  : float = 0.0   # in USD
    mark_price     : float = 0.0
    index_price    : float = 0.0


@dataclass
class OISnapshot:
    coin         : str
    oi_usd       : float
    price        : float
    timestamp    : float
    oi_change_pct: float = 0.0   # vs previous snapshot
    price_change_pct: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
#  1. FUNDING RATE ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class FundingRateAnalyzer:
    """
    Analyzes perpetual funding rates for carry and contrarian signals.

    Two alpha modes:

    MODE A — CARRY (passive income):
      Enter direction that COLLECTS funding payment.
      Best when: rate stable AND consistent direction AND OI high (conviction).
      Min rate threshold: |rate| > CARRY_MIN to justify execution cost.

    MODE B — CONTRARIAN (crowding signal):
      When rate is extreme → market is too crowded on one side → reversion likely.
      Calibrated thresholds from Hyperliquid empirical distribution:
        BTC: extreme = |rate| > 0.05%
        Alts: extreme = |rate| > 0.08%

    Combined signal:
      Carry + Contrarian alignment = HIGH conviction
      Carry vs Contrarian conflict = skip carry, use contrarian only
    """

    CARRY_MIN_PCT     = 0.005    # min |rate| % for carry to justify fees
    EXTREME_LONG_PCT  = 0.070    # rate > this → market too long → SHORT bias
    EXTREME_SHORT_PCT = -0.035   # rate < this → market too short → LONG bias
    MODERATE_PCT      = 0.020    # rate > this → mild crowding signal

    # Hyperliquid pays every 1 hour → 8760 payments/year
    HL_PAYMENTS_PER_YEAR = 8_760

    def __init__(self, window: int = 48):   # 48 hourly observations = 2 days
        self.window   = window
        self._history : Dict[str, Deque[FundingSnapshot]] = {}

    def update(self, snap: FundingSnapshot):
        c = snap.coin
        if c not in self._history:
            self._history[c] = deque(maxlen=self.window)
        self._history[c].append(snap)

    def analyze(self, coin: str) -> Dict:
        hist = list(self._history.get(coin, []))
        if not hist:
            return self._empty(coin)

        latest     = hist[-1]
        rate       = latest.funding_rate           # per-payment, e.g. 0.0001
        rate_pct   = rate * 100                    # percentage display

        # ── Rolling rate stats ───────────────────────────────────────────────
        rates      = np.array([h.funding_rate for h in hist], float)
        rate_mean  = float(np.mean(rates))
        rate_std   = float(np.std(rates)) + _EPS
        rate_z     = (rate - rate_mean) / rate_std   # how extreme is current rate

        # ── Carry signal (MODE A) ────────────────────────────────────────────
        carry_direction = None
        carry_pct_per_h = 0.0
        carry_apy       = 0.0

        if abs(rate_pct) >= self.CARRY_MIN_PCT:
            # Collect funding by being SHORT when rate > 0 (longs pay shorts)
            carry_direction = "SHORT" if rate > 0 else "LONG"
            carry_pct_per_h = abs(rate_pct)
            carry_apy       = carry_pct_per_h * self.HL_PAYMENTS_PER_YEAR

        # ── Contrarian signal (MODE B) ───────────────────────────────────────
        contrarian_signal   = "NEUTRAL"
        contrarian_strength = 0.0

        if rate_pct >= self.EXTREME_LONG_PCT:
            contrarian_signal   = "SHORT"   # too many longs → reversion likely
            contrarian_strength = min((rate_pct - self.EXTREME_LONG_PCT) /
                                      (self.EXTREME_LONG_PCT * 2), 1.0)
        elif rate_pct <= self.EXTREME_SHORT_PCT:
            contrarian_signal   = "LONG"    # too many shorts → squeeze likely
            contrarian_strength = min((abs(rate_pct) - abs(self.EXTREME_SHORT_PCT)) /
                                      (abs(self.EXTREME_SHORT_PCT) * 2), 1.0)
        elif rate_pct >= self.MODERATE_PCT:
            contrarian_signal   = "MILD_SHORT"
            contrarian_strength = (rate_pct - self.MODERATE_PCT) / (self.EXTREME_LONG_PCT - self.MODERATE_PCT)

        # ── Consistency check: is the rate stable or oscillating? ────────────
        consistency = 1.0 - min(rate_std / (abs(rate_mean) + _EPS), 1.0)
        consistency = float(np.clip(consistency, 0.0, 1.0))

        # ── Carry quality: stable rate, consistent direction ─────────────────
        carry_quality = 0.0
        if carry_direction:
            signs_consistent = float(np.mean(np.sign(rates) == np.sign(rate_mean)))
            carry_quality = float(np.clip(signs_consistent * consistency, 0.0, 1.0))

        # ── Combined recommended bias ─────────────────────────────────────────
        # Carry and contrarian agreement = strongest signal
        if carry_direction and contrarian_signal not in ("NEUTRAL",) and \
           carry_direction == contrarian_signal.replace("MILD_", ""):
            recommended_bias  = carry_direction
            signal_type       = "CARRY_AND_CONTRARIAN"
            signal_strength   = min(carry_quality + contrarian_strength, 1.0)
        elif contrarian_strength > 0.3:
            recommended_bias  = contrarian_signal.replace("MILD_", "") if contrarian_signal != "NEUTRAL" else "NEUTRAL"
            signal_type       = "CONTRARIAN"
            signal_strength   = contrarian_strength
        elif carry_direction and carry_quality > 0.5:
            recommended_bias  = carry_direction
            signal_type       = "CARRY"
            signal_strength   = carry_quality * 0.7   # carry alone is less strong
        else:
            recommended_bias  = "NEUTRAL"
            signal_type       = "NONE"
            signal_strength   = 0.0

        # ── Carry USD amount per $100 notional per hour ───────────────────────
        carry_usd_per_100 = abs(rate) * 100.0   # dollar per $100

        return {
            "coin"                  : coin,
            "funding_rate_pct"      : round(rate_pct, 5),
            "funding_rate_z"        : round(rate_z, 3),
            "funding_apy_pct"       : round(carry_apy, 2),
            "carry_direction"       : carry_direction,
            "carry_quality"         : round(carry_quality, 4),
            "carry_usd_per_100_per_h": round(carry_usd_per_100, 5),
            "contrarian_signal"     : contrarian_signal,
            "contrarian_strength"   : round(contrarian_strength, 4),
            "recommended_bias"      : recommended_bias,
            "signal_type"           : signal_type,
            "signal_strength"       : round(float(signal_strength), 4),
            "rate_consistency"      : round(consistency, 4),
            "rate_mean_pct"         : round(rate_mean * 100, 5),
            "n_observations"        : len(hist),
            "last_updated"          : round(latest.timestamp, 1),
        }

    def _empty(self, coin: str) -> Dict:
        return {
            "coin": coin, "funding_rate_pct": 0.0, "funding_rate_z": 0.0,
            "funding_apy_pct": 0.0, "carry_direction": None,
            "carry_quality": 0.0, "carry_usd_per_100_per_h": 0.0,
            "contrarian_signal": "NEUTRAL", "contrarian_strength": 0.0,
            "recommended_bias": "NEUTRAL", "signal_type": "NONE",
            "signal_strength": 0.0, "rate_consistency": 0.0,
            "rate_mean_pct": 0.0, "n_observations": 0, "last_updated": 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  2. OPEN INTEREST ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class OpenInterestAnalyzer:
    """
    Interprets Open Interest changes for directional and volatility signals.

    OI interpretation matrix:
    ┌──────────────┬─────────────┬─────────────────────────────────────────┐
    │ OI Change    │ Price Change │ Interpretation                          │
    ├──────────────┼─────────────┼─────────────────────────────────────────┤
    │ RISING       │ RISING      │ New longs entering → BULLISH confirm    │
    │ RISING       │ FALLING     │ New shorts entering → BEARISH confirm   │
    │ FALLING      │ RISING      │ Short covering → weakening rally        │
    │ FALLING      │ FALLING     │ Long liquidation → possible bottom near │
    │ SPIKE (>2σ)  │ ANY         │ Volatility incoming — reduce size       │
    │ COLLAPSE(2σ) │ ANY         │ Liquidation cascade — max caution       │
    └──────────────┴─────────────┴─────────────────────────────────────────┘
    """

    OI_CHANGE_THRESHOLD = 0.02    # 2% OI change = meaningful
    OI_SPIKE_Z          = 2.0     # z-score threshold for OI spike
    PRICE_CHANGE_MIN    = 0.003   # 0.3% price change = meaningful

    def __init__(self, window: int = 60):
        self.window   = window
        self._history : Dict[str, Deque[OISnapshot]] = {}

    def update(self, snap: OISnapshot):
        c = snap.coin
        if c not in self._history:
            self._history[c] = deque(maxlen=self.window)

        # Compute changes vs previous
        hist = self._history[c]
        if hist:
            prev = hist[-1]
            snap.oi_change_pct    = (snap.oi_usd - prev.oi_usd) / max(prev.oi_usd, _EPS) * 100
            snap.price_change_pct = (snap.price  - prev.price)  / max(prev.price,  _EPS) * 100

        self._history[c].append(snap)

    def analyze(self, coin: str) -> Dict:
        hist = list(self._history.get(coin, []))
        if len(hist) < 3:
            return self._empty(coin)

        latest      = hist[-1]
        oi_chg      = latest.oi_change_pct
        price_chg   = latest.price_change_pct

        # ── OI trend (rolling) ───────────────────────────────────────────────
        oi_vals     = np.array([h.oi_usd for h in hist], float)
        oi_changes  = np.diff(oi_vals) / np.maximum(oi_vals[:-1], _EPS) * 100
        oi_trend    = "RISING"   if float(np.mean(oi_changes[-5:])) > self.OI_CHANGE_THRESHOLD else \
                      "FALLING"  if float(np.mean(oi_changes[-5:])) < -self.OI_CHANGE_THRESHOLD else \
                      "STABLE"

        # ── OI anomaly detection ─────────────────────────────────────────────
        oi_mean     = float(np.mean(abs(oi_changes)))
        oi_std      = float(np.std(oi_changes)) + _EPS
        oi_z        = abs(oi_chg - oi_mean) / oi_std if oi_std > 0 else 0.0
        is_spike    = oi_z > self.OI_SPIKE_Z and oi_chg > 0
        is_collapse = oi_z > self.OI_SPIKE_Z and oi_chg < 0

        # ── Pattern classification ───────────────────────────────────────────
        oi_up    = oi_chg >  self.OI_CHANGE_THRESHOLD
        oi_down  = oi_chg < -self.OI_CHANGE_THRESHOLD
        pr_up    = price_chg >  self.PRICE_CHANGE_MIN
        pr_down  = price_chg < -self.PRICE_CHANGE_MIN

        if is_spike:
            pattern = "OI_SPIKE"
            signal  = "VOLATILITY_WARNING"
        elif is_collapse:
            pattern = "OI_COLLAPSE"
            signal  = "LIQUIDATION_CASCADE"
        elif oi_up and pr_up:
            pattern = "BULLISH_CONFIRM"
            signal  = "LONG_BIAS"
        elif oi_up and pr_down:
            pattern = "BEARISH_CONFIRM"
            signal  = "SHORT_BIAS"
        elif oi_down and pr_up:
            pattern = "SHORT_COVER"
            signal  = "WEAKENING_RALLY"
        elif oi_down and pr_down:
            pattern = "LONG_LIQUIDATION"
            signal  = "POTENTIAL_BOTTOM"
        else:
            pattern = "NEUTRAL"
            signal  = "NEUTRAL"

        # ── Signal strength ──────────────────────────────────────────────────
        strength = min(abs(oi_chg) / (self.OI_CHANGE_THRESHOLD * 5), 1.0) * \
                   min(abs(price_chg) / (self.PRICE_CHANGE_MIN * 5), 1.0)

        # ── Size adjustment ──────────────────────────────────────────────────
        if signal in ("VOLATILITY_WARNING", "LIQUIDATION_CASCADE"):
            size_scalar = 0.3    # extreme caution
        elif signal in ("LONG_BIAS", "SHORT_BIAS"):
            size_scalar = 1.0 + min(strength * 0.3, 0.3)  # boost up to 1.3x
        elif signal in ("WEAKENING_RALLY", "POTENTIAL_BOTTOM"):
            size_scalar = 0.7    # reduce on weak signals
        else:
            size_scalar = 1.0

        # ── Recommended entry bias ───────────────────────────────────────────
        rec_direction = None
        if signal == "LONG_BIAS":       rec_direction = "LONG"
        elif signal == "SHORT_BIAS":    rec_direction = "SHORT"

        return {
            "coin"           : coin,
            "oi_usd"         : round(latest.oi_usd, 0),
            "oi_change_pct"  : round(oi_chg, 4),
            "oi_trend"       : oi_trend,
            "oi_z_score"     : round(oi_z, 3),
            "price_change_pct": round(price_chg, 4),
            "pattern"        : pattern,
            "signal"         : signal,
            "signal_strength": round(float(strength), 4),
            "is_spike"       : is_spike,
            "is_collapse"    : is_collapse,
            "recommended_dir": rec_direction,
            "size_scalar"    : round(float(np.clip(size_scalar, 0.0, 1.5)), 4),
            "n_observations" : len(hist),
        }

    def _empty(self, coin: str) -> Dict:
        return {
            "coin": coin, "oi_usd": 0.0, "oi_change_pct": 0.0,
            "oi_trend": "UNKNOWN", "oi_z_score": 0.0,
            "price_change_pct": 0.0, "pattern": "NEUTRAL",
            "signal": "NEUTRAL", "signal_strength": 0.0,
            "is_spike": False, "is_collapse": False,
            "recommended_dir": None, "size_scalar": 1.0, "n_observations": 0,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  3. HYPERLIQUID DATA FETCHER
# ══════════════════════════════════════════════════════════════════════════════

class HyperliquidAlphaFetcher:
    """
    Fetches funding rate and open interest from Hyperliquid /info endpoint.
    Caches results with configurable TTL to avoid rate limiting.

    Endpoints used:
      POST /info {"type": "metaAndAssetCtxs"} → funding rates, OI, mark price
      POST /info {"type": "allMids"}           → current prices (for OI calculation)
    """

    CACHE_TTL_S = 60.0   # refresh every 60 seconds

    def __init__(self):
        self._cache       : Dict[str, Dict] = {}     # coin → raw data
        self._last_fetch  : float            = 0.0
        self._coin_idx    : Dict[str, int]   = {}    # coin → index in metaAndAssetCtxs

    async def fetch_async(self, coins: List[str]) -> Dict[str, Tuple[FundingSnapshot, OISnapshot]]:
        """
        Fetch and return {coin: (FundingSnapshot, OISnapshot)} for all coins.
        Uses cache if data is fresh.
        """
        now = time.time()
        if now - self._last_fetch < self.CACHE_TTL_S and self._cache:
            return self._parse_cache(coins, now)

        if not HAS_AIOHTTP:
            return {}

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8)
            ) as session:
                # Fetch meta + asset contexts (funding, OI, mark price)
                async with session.post(
                    HL_INFO_URL,
                    json={"type": "metaAndAssetCtxs"},
                ) as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()

            meta_assets = data  # [meta, [assetCtx, ...]]
            if not isinstance(meta_assets, list) or len(meta_assets) < 2:
                return {}

            universe = meta_assets[0].get("universe", [])
            ctxs     = meta_assets[1]

            # Build index
            self._coin_idx = {
                asset["name"]: i for i, asset in enumerate(universe)
            }

            # Cache raw ctx per coin
            self._cache = {}
            for coin_name, idx in self._coin_idx.items():
                if idx < len(ctxs):
                    self._cache[coin_name] = ctxs[idx]

            self._last_fetch = time.time()
            return self._parse_cache(coins, self._last_fetch)

        except Exception:
            return {}

    def _parse_cache(self, coins: List[str],
                     ts: float) -> Dict[str, Tuple[FundingSnapshot, OISnapshot]]:
        result = {}
        for coin in coins:
            raw = self._cache.get(coin)
            if raw is None:
                continue
            try:
                funding_rate  = float(raw.get("funding", 0))
                oi_notional   = float(raw.get("openInterest", 0))
                mark_price    = float(raw.get("markPx", 0))
                oracle_price  = float(raw.get("oraclePx", mark_price))
                oi_usd        = oi_notional * mark_price if mark_price > 0 else 0.0
                premium       = (mark_price - oracle_price) / max(oracle_price, _EPS)

                fs = FundingSnapshot(
                    coin               = coin,
                    funding_rate       = funding_rate,
                    payment_interval_h = 1.0,   # Hyperliquid pays hourly
                    timestamp          = ts,
                    premium            = premium,
                    open_interest      = oi_usd,
                    mark_price         = mark_price,
                    index_price        = oracle_price,
                )
                oi = OISnapshot(
                    coin      = coin,
                    oi_usd    = oi_usd,
                    price     = mark_price,
                    timestamp = ts,
                )
                result[coin] = (fs, oi)
            except Exception:
                continue
        return result

    def get_cached(self, coin: str) -> Optional[Dict]:
        return self._cache.get(coin)


# ══════════════════════════════════════════════════════════════════════════════
#  4. COMPOSITE ALPHA SCORER
# ══════════════════════════════════════════════════════════════════════════════

class CompositeAlphaScorer:
    """
    Combines funding + OI + base signal into one unified alpha score.

    Score components (weights optimized for consistency):
      [40%] Funding signal (carry + contrarian)
      [35%] OI pattern signal
      [25%] Signal agreement (are funding and OI pointing same direction?)

    Output:
      composite_alpha : float 0-1 (higher = better alpha opportunity)
      directional_bias: "LONG" | "SHORT" | "NEUTRAL"
      size_scalar     : float 0-1.3 (multiply base position size)
      skip            : bool (True = do not trade this coin now)
    """

    def compute(
        self,
        funding_result : Dict,
        oi_result      : Dict,
        intended_dir   : Optional[str] = None,   # direction engine wants to enter
    ) -> Dict:
        coin = funding_result.get("coin", "UNKNOWN")

        f_bias    = funding_result.get("recommended_bias", "NEUTRAL")
        f_str     = float(funding_result.get("signal_strength", 0.0))
        f_type    = funding_result.get("signal_type", "NONE")

        oi_dir    = oi_result.get("recommended_dir")
        oi_str    = float(oi_result.get("signal_strength", 0.0))
        oi_sig    = oi_result.get("signal", "NEUTRAL")
        oi_scalar = float(oi_result.get("size_scalar", 1.0))
        oi_spike  = oi_result.get("is_spike", False)
        oi_coll   = oi_result.get("is_collapse", False)

        # ── Hard blocks ──────────────────────────────────────────────────────
        if oi_spike or oi_coll:
            return {
                "coin": coin, "composite_alpha": 0.0,
                "directional_bias": "NEUTRAL", "size_scalar": 0.3,
                "skip": True, "skip_reason": f"OI anomaly: {oi_result.get('pattern')}",
                "funding_contribution": 0.0, "oi_contribution": 0.0,
                "agreement_bonus": 0.0,
            }

        # ── Component 1: Funding (40%) ────────────────────────────────────────
        f_score = 0.0
        if f_type == "CARRY_AND_CONTRARIAN":
            f_score = min(f_str * 1.2, 1.0)   # best case — double alpha
        elif f_type in ("CONTRARIAN", "CARRY"):
            f_score = f_str * 0.85
        # Penalize if funding contradicts intended direction
        if intended_dir and f_bias not in ("NEUTRAL",) and \
           not f_bias.replace("MILD_", "").startswith(intended_dir[:5]):
            f_score *= 0.5

        # ── Component 2: OI (35%) ────────────────────────────────────────────
        oi_score = 0.0
        if oi_dir and oi_dir == intended_dir:
            oi_score = oi_str   # confirmed direction
        elif oi_dir and oi_dir != intended_dir:
            oi_score = -oi_str  # contradicts direction
        elif oi_sig in ("POTENTIAL_BOTTOM",) and intended_dir == "LONG":
            oi_score = oi_str * 0.6
        elif oi_sig in ("WEAKENING_RALLY",) and intended_dir == "SHORT":
            oi_score = oi_str * 0.5
        oi_score = float(np.clip(oi_score, -1.0, 1.0))

        # ── Component 3: Agreement bonus (25%) ──────────────────────────────
        agreement = 0.0
        f_final_dir = f_bias.replace("MILD_", "") if f_bias not in ("NEUTRAL", "NONE") else None
        if f_final_dir and oi_dir and f_final_dir == oi_dir:
            agreement = 0.8   # both agree
            if f_final_dir == intended_dir:
                agreement = 1.0   # triple agreement

        # ── Composite (normalize to 0-1) ─────────────────────────────────────
        raw = 0.40 * f_score + 0.35 * ((oi_score + 1) / 2) + 0.25 * agreement
        composite = float(np.clip(raw, 0.0, 1.0))

        # ── Directional bias ─────────────────────────────────────────────────
        if f_final_dir and oi_dir and f_final_dir == oi_dir:
            directional_bias = f_final_dir
        elif f_final_dir and f_type == "CARRY_AND_CONTRARIAN":
            directional_bias = f_final_dir
        elif oi_dir and oi_str > 0.4:
            directional_bias = oi_dir
        else:
            directional_bias = "NEUTRAL"

        # ── Size scalar (compound funding + OI adjustments) ──────────────────
        base_scalar  = oi_scalar
        if composite > 0.7 and directional_bias == intended_dir:
            base_scalar = min(base_scalar * 1.2, 1.4)   # boost on strong alpha
        elif composite < 0.35:
            base_scalar = min(base_scalar, 0.7)          # reduce on weak alpha

        # Skip if composite too low AND signals contradict
        skip = False
        skip_reason = None
        if composite < 0.2 and oi_score < -0.3:
            skip = True
            skip_reason = "Low alpha + OI contradiction"

        return {
            "coin"                : coin,
            "composite_alpha"     : round(composite, 4),
            "directional_bias"    : directional_bias,
            "size_scalar"         : round(float(np.clip(base_scalar, 0.0, 1.5)), 4),
            "skip"                : skip,
            "skip_reason"         : skip_reason,
            "funding_contribution": round(0.40 * f_score, 4),
            "oi_contribution"     : round(0.35 * ((oi_score + 1) / 2), 4),
            "agreement_bonus"     : round(0.25 * agreement, 4),
            "funding_type"        : f_type,
            "oi_pattern"          : oi_result.get("pattern", "NEUTRAL"),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  5. ALPHA SIGNAL ENGINE  (main facade)
# ══════════════════════════════════════════════════════════════════════════════

class AlphaSignalEngine:
    """
    Main facade. Combine funding, OI, and composite scoring.

    Designed for async use in hft_engine.py / hft_rapid_scalper.py:

        engine = AlphaSignalEngine(coins=config.watchlist)

        # In your async loop (every 60 seconds):
        await engine.refresh_async()

        # Before each entry:
        alpha = engine.get_alpha("BTC", intended_direction="LONG")
        if alpha["skip"]:
            continue
        position_size *= alpha["size_scalar"]

        # Or get the engine's directional bias to confirm signal:
        if alpha["directional_bias"] != "NEUTRAL" and alpha["directional_bias"] != direction:
            continue  # alpha signals opposite direction
    """

    def __init__(
        self,
        coins             : List[str],
        funding_window    : int   = 48,
        oi_window         : int   = 60,
        auto_refresh_s    : float = 60.0,
    ):
        self.coins           = [c.upper() for c in coins]
        self._funding        = FundingRateAnalyzer(window=funding_window)
        self._oi             = OpenInterestAnalyzer(window=oi_window)
        self._fetcher        = HyperliquidAlphaFetcher()
        self._scorer         = CompositeAlphaScorer()
        self.auto_refresh_s  = auto_refresh_s
        self._last_refresh   : float = 0.0
        self._last_results   : Dict[str, Dict] = {}

    async def refresh_async(self) -> bool:
        """
        Fetch latest funding + OI from Hyperliquid.
        Returns True if data was successfully refreshed.
        Call this in your async loop every ~60 seconds.
        """
        now = time.time()
        if now - self._last_refresh < self.auto_refresh_s:
            return False   # not time yet

        raw = await self._fetcher.fetch_async(self.coins)
        if not raw:
            return False

        for coin, (fs, ois) in raw.items():
            self._funding.update(fs)
            self._oi.update(ois)

        self._last_refresh = time.time()
        return True

    def inject_price(self, coin: str, price: float, oi_usd: Optional[float] = None):
        """
        Update price and optionally OI without API call.
        Use this when you already have prices from your existing WS feed.
        """
        coin = coin.upper()
        if oi_usd is not None:
            snap = OISnapshot(coin=coin, oi_usd=oi_usd, price=price, timestamp=time.time())
            self._oi.update(snap)

    def inject_funding(self, coin: str, funding_rate: float):
        """
        Inject funding rate directly (if already fetching from WS elsewhere).
        funding_rate: per-payment rate, e.g. 0.0001 = 0.01%
        """
        coin = coin.upper()
        snap = FundingSnapshot(
            coin=coin, funding_rate=funding_rate,
            payment_interval_h=1.0, timestamp=time.time(),
        )
        self._funding.update(snap)

    def get_alpha(
        self,
        coin           : str,
        intended_dir   : Optional[str] = None,
    ) -> Dict:
        """
        Get composite alpha signal for a coin.
        Returns dict with: composite_alpha, directional_bias, size_scalar, skip, etc.
        """
        coin = coin.upper()
        f_result  = self._funding.analyze(coin)
        oi_result = self._oi.analyze(coin)
        composite = self._scorer.compute(f_result, oi_result, intended_dir)
        return {
            **composite,
            "funding"  : f_result,
            "oi"       : oi_result,
            "coin"     : coin,
        }

    def get_carry_opportunities(
        self,
        min_apy        : float = 20.0,  # minimum APY % for carry trade
        min_quality    : float = 0.5,
    ) -> List[Dict]:
        """
        Return list of active carry trade opportunities sorted by APY.
        These are purely passive alpha — no price prediction needed.
        """
        opportunities = []
        for coin in self.coins:
            fr = self._funding.analyze(coin)
            apy       = fr.get("funding_apy_pct", 0.0)
            quality   = fr.get("carry_quality", 0.0)
            direction = fr.get("carry_direction")
            if apy >= min_apy and quality >= min_quality and direction:
                opportunities.append({
                    "coin"         : coin,
                    "direction"    : direction,
                    "apy_pct"      : apy,
                    "rate_pct"     : fr["funding_rate_pct"],
                    "carry_quality": quality,
                    "signal_type"  : fr["signal_type"],
                })
        return sorted(opportunities, key=lambda x: -x["apy_pct"])

    def get_all_alpha(self) -> Dict[str, Dict]:
        """Get alpha signals for all coins at once."""
        return {c: self.get_alpha(c) for c in self.coins}

    def get_funding_snapshot(self) -> List[Dict]:
        """Quick funding rate overview for all coins."""
        rows = []
        for coin in self.coins:
            fr = self._funding.analyze(coin)
            rows.append({
                "coin"           : coin,
                "rate_pct"       : fr["funding_rate_pct"],
                "apy_pct"        : fr["funding_apy_pct"],
                "bias"           : fr["recommended_bias"],
                "type"           : fr["signal_type"],
                "strength"       : fr["signal_strength"],
            })
        return sorted(rows, key=lambda x: abs(x["rate_pct"]), reverse=True)

    def get_oi_snapshot(self) -> List[Dict]:
        """Quick OI overview for all coins."""
        rows = []
        for coin in self.coins:
            oi = self._oi.analyze(coin)
            rows.append({
                "coin"    : coin,
                "oi_usd"  : oi["oi_usd"],
                "oi_chg"  : oi["oi_change_pct"],
                "pattern" : oi["pattern"],
                "signal"  : oi["signal"],
            })
        return sorted(rows, key=lambda x: abs(x["oi_chg"]), reverse=True)
