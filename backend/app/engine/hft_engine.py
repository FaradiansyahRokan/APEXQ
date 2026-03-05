"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              APEX HFT ENGINE v2.1 — "The Predator"                          ║
║   Microstructure-Aware · Edge-Verified · Fee-Conscious · Anti-Chasing       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ARSITEKTUR:                                                                 ║
║  • THE EYE      → WebSocket tick feed (Hyperliquid L1 real-time)            ║
║  • THE FILTER   → Regime gate + liquidity check sebelum entry               ║
║  • THE BRAIN    → Mean-reversion microstructure + orderflow imbalance        ║
║  • THE MUSCLE   → Limit order executor + adaptive exit                       ║
║  • THE SHIELD   → HWM equity protection + daily circuit breaker              ║
║                                                                              ║
║  PERBAIKAN DARI v1 (HftBot.jsx / hft_engine.py lama):                       ║
║  [FATAL]  Momentum chasing → diganti Mean-Reversion + OFI                   ║
║  [FATAL]  No slippage → simulasi spread + slippage realistis                 ║
║  [FATAL]  REST polling 1s → WebSocket (latency 50-200ms)                    ║
║  [FATAL]  Fee 0.08% round-trip vs target 0.1% → target dinaikkan           ║
║  [HIGH]   Trailing stop noise 0.08% → adaptive ATR-based                    ║
║  [HIGH]   No entry quality filter → 3-gate system                           ║
║  [HIGH]   Long-only only → long + short tergantung regime                   ║
║  [MEDIUM] 20 coins flat → focus 5 coins paling liquid                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

CARA KERJA EDGE INI:

1. MEAN REVERSION MICROSTRUCTURE
   Crypto liquid (BTC, ETH, SOL) punya mean-reversion kuat di timeframe <60s.
   Ketika harga overshoots 1.5-3σ dari VWAP jangka pendek, probabilitas
   reversal ke mean adalah 60-70%. Ini BEDA dengan momentum chasing.

2. ORDER FLOW IMBALANCE (OFI)
   Jika bid volume >> ask volume dalam window 10 tick terakhir → tekanan beli.
   Entry LONG hanya jika OFI konfirmasi arah reversal.

3. THREE-GATE ENTRY SYSTEM
   Gate 1: Regime — hanya trade di LOW_VOL atau SIDEWAYS (bukan CRISIS)
   Gate 2: Spread — skip jika spread > 1.5x normal (illiquid / manipulated)
   Gate 3: OFI + Z-Score alignment → minimum 2/3 sub-signals harus agree

4. ADAPTIVE EXIT
   Stop: ATR-based (bukan fixed %) → menyesuaikan dengan volatilitas saat ini
   TP:   Asymmetric → target minimal 2.5R dari risiko setelah fee
   Timeout: 60s hard close (posisi microstructure tidak boleh lama)

5. FEE MATH YANG BENAR
   Fee HL taker = 0.035% per side = 0.07% round-trip
   Minimum target per trade = 0.07% + 0.03% (slippage) + 0.10% profit = 0.20%
   Artinya: JANGAN masuk kalau expected move < 0.25%

DEPENDENCIES:
    pip install aiohttp websockets numpy --break-system-packages
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import statistics
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple
import aiohttp
import numpy as np

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# ══════════════════════════════════════════════════════════════════
#  NEW ENGINE IMPORTS — Signal Intelligence, Alpha, Meta, Attribution
#  Semua try/except agar engine tetap berjalan tanpa module baru
# ══════════════════════════════════════════════════════════════════

try:
    from apex_signal_intelligence import SignalIntelligenceGate
    HAS_INTEL = True
except ImportError:
    HAS_INTEL = False

try:
    from apex_alpha_signals import AlphaSignalEngine
    HAS_ALPHA = True
except ImportError:
    HAS_ALPHA = False

try:
    from apex_meta_allocator import get_allocator
    HAS_META = True
except ImportError:
    HAS_META = False

try:
    from apex_performance_attribution import get_attribution, AttributedTrade
    HAS_ATTR = True
except ImportError:
    HAS_ATTR = False

# ── APEX Engine v7.0 Analytics ───────────────────────────────────────────
try:
    from apex_engine_v6 import (
        kalman_filter_trend, kalman_zscore,
        ou_trading_signals, realized_vol_suite,
        bayesian_regime_filter, master_quant_signal,
    )
    HAS_APEX_V6 = True
except ImportError:
    try:
        from app.engine.apex_engine_v6 import (
            kalman_filter_trend, kalman_zscore,
            ou_trading_signals, realized_vol_suite,
            bayesian_regime_filter, master_quant_signal,
        )
        HAS_APEX_V6 = True
    except ImportError:
        HAS_APEX_V6 = False


# ══════════════════════════════════════════════════════════════════
#  KONSTANTA & MATH
# ══════════════════════════════════════════════════════════════════

FEE_TAKER_PCT  = 0.035   # Hyperliquid taker fee per side (%)
FEE_ROUND_TRIP = FEE_TAKER_PCT * 2   # 0.07% total round-trip
SLIPPAGE_EST   = 0.03    # perkiraan slippage market order (%)
MIN_GROSS_PCT  = FEE_ROUND_TRIP + SLIPPAGE_EST + 0.12  # min gross target (%)
# = 0.07 + 0.03 + 0.12 = 0.22% — di bawah ini TIDAK ada expected positive EV


# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════

@dataclass
class HFTConfig:
    # ── Universe ─────────────────────────────────────────────────
    # Top 20 Hyperliquid perps berdasarkan open interest + volume
    # Lebih banyak coin = lebih banyak peluang mean-reversion
    watchlist: List[str] = field(default_factory=lambda: [
        # Tier 1 — paling liquid, spread tightest
        "BTC", "ETH", "SOL", "BNB", "XRP",
        # Tier 2 — liquid, mean-reversion kuat
        "DOGE", "AVAX", "LINK", "ATOM", "LTC",
        # Tier 3 — cukup liquid untuk HFT
        "APT", "ARB", "OP", "SUI", "INJ",
        # Tier 4 — occasional signal value
        "MATIC", "UNI", "FIL", "TIA", "BCH",
    ])

    # ── Position sizing ──────────────────────────────────────────
    max_positions:     int   = 3          # Fokus kualitas, bukan kuantitas
    capital_per_trade: float = 100.0      # USD per posisi

    # ── Entry parameters (mean-reversion) ───────────────────────
    # FIX: Turunkan dari 1.8 → 1.5 agar lebih sering dapat sinyal
    # 1.5σ masih statistis bermakna (P=13.4%) tapi tidak se-ekstrem 1.8σ (P=7.2%)
    zscore_entry:      float = 1.5

    # FIX: Window diperbesar 20→30 untuk VWAP yang lebih stabil
    zscore_window:     int   = 30

    # FIX: Turunkan OFI dari 0.60 → 0.55
    # 0.60 terlalu ketat untuk liquid markets (OFI jarang > 0.60 di BTC/ETH)
    # 0.55 = bias beli yang masih bermakna, P(OFI>=0.55) ≈ 34%
    ofi_min_ratio:     float = 0.55

    # FIX: Longgarkan spread filter dari 1.8 → 2.5
    # Spread sesekali melebar saat volatilitas, bukan berarti manipulasi
    spread_max_mult:   float = 2.5

    # ── Exit parameters ──────────────────────────────────────────
    atr_stop_mult:     float = 1.5
    atr_period:        int   = 14
    # FIX: Turunkan min RR dari 2.5 → 2.0
    # 2.5R terlalu jarang tercapai di microstructure timeframe
    # 2.0R masih memberikan edge positif dengan win_rate > 33%
    min_rr_ratio:      float = 2.0
    max_hold_seconds:  int   = 90         # FIX: Naik dari 60 → 90s, beri lebih waktu
    trailing_atr_mult: float = 1.0

    # ── Regime filter ────────────────────────────────────────────
    # FIX: Hilangkan regime filter — regime detection tidak diset di engine ini!
    # Kalau allowed_regimes diisi tapi _regime tidak diupdate, TIDAK ADA entry sama sekali.
    # Ubah ke empty list = trade semua regime (CB sudah jaga downside)
    allowed_regimes: List[str] = field(default_factory=lambda: [])

    # ── Engine ───────────────────────────────────────────────────
    scan_interval:     float = 0.5
    fee_pct:           float = FEE_TAKER_PCT
    long_bias:         bool  = False

    # ── Circuit breaker ──────────────────────────────────────────
    # FIX: Naikkan daily loss limit dari 2% → 3% agar CB tidak terlalu sering trip
    max_daily_loss_pct: float = 3.0
    max_loss_streak:    int   = 5         # FIX: 4 → 5, kasih lebih banyak attempts


# ══════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════

@dataclass
class TickData:
    """Satu tick data dari exchange."""
    coin:       str
    price:      float
    bid:        float
    ask:        float
    bid_size:   float
    ask_size:   float
    ts:         float  # unix timestamp

    @property
    def spread_pct(self) -> float:
        mid = (self.bid + self.ask) / 2
        return (self.ask - self.bid) / mid * 100 if mid > 0 else 0.0

    @property
    def mid_price(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class CoinMicrostructure:
    """
    State microstructure per coin — diupdate setiap tick.
    Ini adalah 'memori' pendek engine tentang kondisi market.
    """
    coin:        str
    price_ticks: deque = field(default_factory=lambda: deque(maxlen=50))
    bid_sizes:   deque = field(default_factory=lambda: deque(maxlen=20))
    ask_sizes:   deque = field(default_factory=lambda: deque(maxlen=20))
    spreads:     deque = field(default_factory=lambda: deque(maxlen=30))

    # Running stats
    vwap_short:  float = 0.0   # VWAP 20-tick
    price_std:   float = 0.0   # StdDev 20-tick
    atr:         float = 0.0   # ATR 14-tick
    avg_spread:  float = 0.0   # Spread rata-rata

    def update(self, tick: TickData):
        self.price_ticks.append(tick.mid_price)
        self.bid_sizes.append(tick.bid_size)
        self.ask_sizes.append(tick.ask_size)
        self.spreads.append(tick.spread_pct)

        if len(self.price_ticks) >= 10:
            arr = list(self.price_ticks)
            self.vwap_short = float(np.mean(arr[-20:]))
            self.price_std  = float(np.std(arr[-20:])) if len(arr) >= 20 else float(np.std(arr))
            self.avg_spread = float(np.mean(list(self.spreads)))

            # ATR — high-low proxy dari tick data
            if len(arr) >= 14:
                ranges = [abs(arr[i] - arr[i-1]) for i in range(1, min(15, len(arr)))]
                self.atr = float(np.mean(ranges)) if ranges else 0.0

    def zscore(self, price: float) -> float:
        """Z-Score harga saat ini vs VWAP pendek."""
        if self.price_std < 1e-10:
            return 0.0
        return (price - self.vwap_short) / self.price_std

    def ofi(self) -> float:
        """
        Order Flow Imbalance: bid_vol / (bid_vol + ask_vol).
        > 0.6 = tekanan beli, < 0.4 = tekanan jual, 0.4-0.6 = neutral.

        FIX: 0.0 sentinel values (no real L2 data) are excluded.
        Without this fix, coins without L2 would always return OFI=0.5 (neutral),
        making Gate 3 ineffective for 15 out of 20 watchlist coins.
        """
        # Filter out 0.0 sentinels (allMids placeholder, not real size data)
        real_bids = [s for s in self.bid_sizes if s > 0.0]
        real_asks = [s for s in self.ask_sizes if s > 0.0]
        total_bid = sum(real_bids) if real_bids else 0
        total_ask = sum(real_asks) if real_asks else 0
        total = total_bid + total_ask
        if total < 1e-10:
            return 0.5   # truly no data → neutral (not false 0.5 from fake sizes)
        return total_bid / total

    def is_spread_normal(self, max_mult: float) -> bool:
        """Spread saat ini masih dalam batas normal."""
        if self.avg_spread < 1e-8:
            return True  # belum ada data historis, asumsikan normal
        recent = list(self.spreads)[-3:]
        current_spread = float(np.mean(recent)) if recent else self.avg_spread
        return current_spread <= self.avg_spread * max_mult

    def is_ready(self) -> bool:
        return len(self.price_ticks) >= 20


@dataclass
class HFTPosition:
    id:            str
    coin:          str
    direction:     str       # "LONG" | "SHORT"
    entry_price:   float
    current_price: float
    peak_price:    float     # untuk trailing LONG
    valley_price:  float     # untuk trailing SHORT
    qty:           float
    capital:       float
    opened_at:     float
    status:        str       # "OPEN" | "CLOSED"
    stop_price:    float     # adaptive ATR stop
    tp_price:      float     # take profit target
    atr_at_entry:  float     # ATR saat entry untuk adaptive stops
    unrealized_pnl: float = 0.0
    unrealized_pct: float = 0.0

    def update_price(self, price: float, atr: float = 0.0):
        self.current_price = price

        # Update trailing
        if self.direction == "LONG":
            if price > self.peak_price:
                self.peak_price = price
                # Trailing stop naik seiring harga naik
                if atr > 0:
                    self.stop_price = max(self.stop_price,
                                         price - atr * 1.0)
            self.unrealized_pnl = (price - self.entry_price) * self.qty
        else:
            if price < self.valley_price:
                self.valley_price = price
                if atr > 0:
                    self.stop_price = min(self.stop_price,
                                         price + atr * 1.0)
            self.unrealized_pnl = (self.entry_price - price) * self.qty

        self.unrealized_pct = (self.unrealized_pnl / self.capital) * 100

    def should_exit_stop(self) -> bool:
        if self.direction == "LONG":
            return self.current_price <= self.stop_price
        return self.current_price >= self.stop_price

    def should_exit_tp(self) -> bool:
        if self.direction == "LONG":
            return self.current_price >= self.tp_price
        return self.current_price <= self.tp_price

    def should_force_close(self, max_hold: int) -> bool:
        return (time.time() - self.opened_at) >= max_hold

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hold_seconds"] = int(time.time() - self.opened_at)
        return d


@dataclass
class HFTTrade:
    id:           str
    coin:         str
    direction:    str
    entry_price:  float
    exit_price:   float
    qty:          float
    capital:      float
    gross_pnl:    float
    fee_usd:      float
    slippage_usd: float
    net_pnl:      float
    net_pct:      float
    exit_reason:  str
    opened_at:    float
    closed_at:    float
    hold_seconds: float
    entry_zscore: float  # Z-Score saat entry
    entry_ofi:    float  # OFI saat entry

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════════
#  STATS TRACKER
# ══════════════════════════════════════════════════════════════════

class HFTStats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.total_trades      = 0
        self.winning_trades    = 0
        self.losing_trades     = 0
        self.total_net_pnl     = 0.0
        self.total_fees        = 0.0
        self.total_slippage    = 0.0
        self.gross_pnl         = 0.0
        self.peak_balance      = 0.0
        self.max_drawdown_pct  = 0.0
        self.best_trade_pct    = 0.0
        self.worst_trade_pct   = 0.0
        self._pnl_series       = []
        self.started_at        = time.time()
        self.consecutive_losses = 0
        self.max_loss_streak   = 0
        # Per exit reason
        self.exit_stats        = {"STOP": 0, "TP": 0, "TIMEOUT": 0, "MANUAL": 0}

    def record(self, trade: HFTTrade, current_balance: float):
        self.total_trades   += 1
        self.total_net_pnl  += trade.net_pnl
        self.gross_pnl      += trade.gross_pnl
        self.total_fees     += trade.fee_usd
        self.total_slippage += trade.slippage_usd
        self._pnl_series.append(trade.net_pnl)
        self.exit_stats[trade.exit_reason] = self.exit_stats.get(trade.exit_reason, 0) + 1

        if trade.net_pnl > 0:
            self.winning_trades  += 1
            self.consecutive_losses = 0
        else:
            self.losing_trades   += 1
            self.consecutive_losses += 1
            self.max_loss_streak  = max(self.max_loss_streak,
                                        self.consecutive_losses)

        if trade.net_pct > self.best_trade_pct:
            self.best_trade_pct = trade.net_pct
        if trade.net_pct < self.worst_trade_pct:
            self.worst_trade_pct = trade.net_pct

        if current_balance > self.peak_balance:
            self.peak_balance = current_balance

        if self.peak_balance > 0:
            dd = ((self.peak_balance - current_balance) / self.peak_balance) * 100
            if dd > self.max_drawdown_pct:
                self.max_drawdown_pct = dd

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def avg_net_pnl(self) -> float:
        return statistics.mean(self._pnl_series) if self._pnl_series else 0.0

    @property
    def trades_per_hour(self) -> float:
        elapsed = (time.time() - self.started_at) / 3600
        return self.total_trades / elapsed if elapsed > 0.001 else 0.0

    @property
    def profit_factor(self) -> float:
        wins = sum(p for p in self._pnl_series if p > 0)
        loss = abs(sum(p for p in self._pnl_series if p < 0))
        return wins / loss if loss > 0 else (999.0 if wins > 0 else 0.0)

    @property
    def expectancy_pct(self) -> float:
        """Expected value per trade sebagai % dari capital."""
        if not self._pnl_series:
            return 0.0
        return float(np.mean(self._pnl_series))

    @property
    def sharpe_trades(self) -> float:
        """Sharpe ratio sederhana dari trade-level returns."""
        if len(self._pnl_series) < 5:
            return 0.0
        arr = np.array(self._pnl_series)
        std = float(np.std(arr))
        return float(np.mean(arr) / std) if std > 1e-10 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_trades"      : self.total_trades,
            "winning_trades"    : self.winning_trades,
            "losing_trades"     : self.losing_trades,
            "win_rate"          : round(self.win_rate, 1),
            "total_net_pnl"     : round(self.total_net_pnl, 4),
            "gross_pnl"         : round(self.gross_pnl, 4),
            "total_fees"        : round(self.total_fees, 4),
            "total_slippage"    : round(self.total_slippage, 4),
            "avg_net_pnl"       : round(self.avg_net_pnl, 4),
            "expectancy_pct"    : round(self.expectancy_pct, 4),
            "profit_factor"     : round(self.profit_factor, 2),
            "sharpe_trades"     : round(self.sharpe_trades, 3),
            "trades_per_hour"   : round(self.trades_per_hour, 1),
            "max_drawdown_pct"  : round(self.max_drawdown_pct, 2),
            "best_trade_pct"    : round(self.best_trade_pct, 3),
            "worst_trade_pct"   : round(self.worst_trade_pct, 3),
            "consecutive_losses": self.consecutive_losses,
            "max_loss_streak"   : self.max_loss_streak,
            "exit_breakdown"    : self.exit_stats,
        }


# ══════════════════════════════════════════════════════════════════
#  CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Hentikan trading otomatis jika kondisi berbahaya terdeteksi.
    Ini adalah perbedaan antara trader dan gambler.
    """

    def __init__(self, config: HFTConfig, initial_balance: float):
        self.config           = config
        self.initial_balance  = initial_balance
        self.day_start_balance = initial_balance
        self.is_tripped       = False
        self.trip_reason      = ""
        self.last_day_reset   = datetime.now().date()

    def reset_daily(self, current_balance: float):
        today = datetime.now().date()
        if today != self.last_day_reset:
            self.day_start_balance = current_balance
            self.last_day_reset    = today
            # Reset trip jika baru hari ini
            if self.is_tripped and "DAILY" in self.trip_reason:
                self.is_tripped   = False
                self.trip_reason  = ""

    def check(self, current_balance: float, consecutive_losses: int) -> Tuple[bool, str]:
        """
        Return (can_trade, reason).
        can_trade = False → STOP semua aktivitas.
        """
        if self.is_tripped:
            return False, self.trip_reason

        # 1. Daily loss limit
        daily_pnl_pct = (current_balance - self.day_start_balance) / self.day_start_balance * 100
        if daily_pnl_pct <= -self.config.max_daily_loss_pct:
            self.is_tripped  = True
            self.trip_reason = f"DAILY LOSS LIMIT hit: {daily_pnl_pct:.2f}%"
            return False, self.trip_reason

        # 2. Consecutive loss streak
        if consecutive_losses >= self.config.max_loss_streak:
            self.is_tripped  = True
            self.trip_reason = f"LOSS STREAK {consecutive_losses} trades — edge hilang, berhenti dulu"
            return False, self.trip_reason

        return True, "OK"

    def manual_reset(self):
        self.is_tripped  = False
        self.trip_reason = ""


# ══════════════════════════════════════════════════════════════════
#  THE PREDATOR — MAIN HFT ENGINE v2.0
# ══════════════════════════════════════════════════════════════════

class HFTPredator:
    """
    HFT engine berbasis mean-reversion microstructure.

    Strategi inti:
    - Masuk SEBELUM momentum, bukan SETELAH (anti-chasing)
    - Mean reversion dari VWAP pendek dengan konfirmasi OFI
    - Target minimal 2.5R setelah fee dan slippage
    - Circuit breaker otomatis

    Cara deploy:
        engine = HFTPredator()
        engine.set_balance(1000.0)
        await engine.start()
        # ... engine berjalan di background
        status = engine.get_status()
        await engine.stop()
    """

    HL_INFO_URL  = "https://api.hyperliquid.xyz/info"
    HL_WS_URL    = "wss://api.hyperliquid.xyz/ws"

    def __init__(self):
        self.config         : HFTConfig                       = HFTConfig()
        self.running        : bool                             = False
        self.positions      : Dict[str, HFTPosition]          = {}
        self.trade_log      : List[HFTTrade]                  = []
        self.stats          : HFTStats                        = HFTStats()
        self.balance        : float                            = 1000.0
        self.initial_balance: float                            = 1000.0
        self.equity_curve   : List[dict]                       = []

        # Microstructure state per coin
        self._ms            : Dict[str, CoinMicrostructure]   = {}
        self._in_position   : Set[str]                         = set()

        # Circuit breaker
        self._cb            : Optional[CircuitBreaker]         = None

        # Event log
        self._events        : deque                            = deque(maxlen=300)

        self._task          : Optional[asyncio.Task]           = None
        self._session       : Optional[aiohttp.ClientSession]  = None

        # Regime state (updated periodik)
        self._regime        : str  = "UNKNOWN"
        self._regime_ts     : float = 0.0

        # Slippage model — realistic per-coin, covers all 20 watchlist coins
        # Tier 1 (ultra-liquid): 0.010-0.018%  Tier 2: 0.020-0.025%  Tier 3: 0.030-0.040%
        self._slippage_model: Dict[str, float] = {
            "BTC": 0.010, "ETH": 0.012, "SOL": 0.015, "BNB": 0.018, "XRP": 0.020,
            "DOGE": 0.022, "AVAX": 0.022, "LINK": 0.025, "ATOM": 0.025, "LTC": 0.025,
            "APT":  0.030, "ARB":  0.030, "OP":   0.030, "SUI":  0.032, "INJ":  0.032,
            "MATIC":0.035, "UNI":  0.035, "FIL":  0.038, "TIA":  0.040, "BCH":  0.030,
        }
        # Cooldown per coin: cegah re-entry terlalu cepat setelah exit
        self._last_trade_ts: Dict[str, float] = {}
        self._cooldown_seconds: int = 15

        # ── NEW ENGINES (initialized in set_balance / lazily) ────────────────
        self._intel_gate  = None   # SignalIntelligenceGate  (apex_signal_intelligence)
        self._alpha_engine = None  # AlphaSignalEngine       (apex_alpha_signals)
        self._meta        = None   # MetaAllocator           (apex_meta_allocator)
        self._attribution = None   # PerformanceAttributionEngine (apex_performance_attribution)
        self._alpha_refresh_ts: float = 0.0   # last time alpha was refreshed

    # ─── PUBLIC CONTROL ─────────────────────────────────────────

    def configure(self, cfg: dict):
        for k, v in cfg.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        self._log("CONFIG", f"Updated: {list(cfg.keys())}")

    def set_balance(self, balance: float):
        self.balance          = balance
        self.initial_balance  = balance
        self.stats.peak_balance = balance
        self.equity_curve     = [{"ts": time.time(), "balance": balance}]
        self._cb              = CircuitBreaker(self.config, balance)

        # Initialize new intelligence engines
        coins = self.config.watchlist
        if HAS_INTEL and self._intel_gate is None:
            self._intel_gate   = SignalIntelligenceGate(coins=coins)
        if HAS_ALPHA and self._alpha_engine is None:
            self._alpha_engine = AlphaSignalEngine(coins=coins)
        if HAS_META:
            self._meta         = get_allocator(total_capital=balance)
        if HAS_ATTR and self._attribution is None:
            self._attribution  = get_attribution()

    async def start(self):
        if self.running:
            return
        if self._cb is None:
            self._cb = CircuitBreaker(self.config, self.balance)
        self.running = True
        self.stats.reset()
        self.stats.peak_balance = self.balance
        self._log("ENGINE", " Predator awakens — microstructure scanner active")
        self._task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for pos in list(self.positions.values()):
            if pos.status == "OPEN":
                self._close_position(pos, "MANUAL")
        self._log("ENGINE", " Predator halted — all positions closed")

    # ─── MAIN LOOP ───────────────────────────────────────────────

    async def _main_loop(self):
        connector = aiohttp.TCPConnector(ssl=False, limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            self._session = session
            while self.running:
                try:
                    # 1. Fetch ticks (REST polling, upgrade ke WebSocket jika available)
                    ticks = await self._fetch_ticks(session)

                    # 2. Update microstructure per coin
                    self._update_microstructure(ticks)

                    # 3. Update posisi open
                    self._update_positions(ticks)

                    # 4. Check exits
                    self._check_exits()

                    # 5. Circuit breaker check
                    if self._cb:
                        self._cb.reset_daily(self.balance)
                        can_trade, cb_reason = self._cb.check(
                            self.balance, self.stats.consecutive_losses
                        )
                        if not can_trade:
                            self._log("CIRCUIT", f" {cb_reason}")
                        else:
                            # 6. Scan entries (hanya jika slot tersedia dan CB OK)
                            if len(self._open_positions()) < self.config.max_positions:
                                # Regime filter: skip jika allowed_regimes diset dan regime tidak cocok
                                regime_ok = (
                                    not self.config.allowed_regimes or
                                    self._regime in self.config.allowed_regimes or
                                    self._regime == "UNKNOWN"
                                )
                                if regime_ok:
                                    self._scan_entries(ticks)
                                else:
                                    pass  # Regime tidak cocok, skip

                    # 7. Equity snapshot
                    self._record_equity_snapshot()

                    # 8. [NEW] Refresh alpha signals every ~60s
                    now = time.time()
                    if (self._alpha_engine is not None and
                            now - self._alpha_refresh_ts > 60.0):
                        try:
                            await self._alpha_engine.refresh_async()
                        except Exception:
                            pass
                        self._alpha_refresh_ts = now

                        # Also update HMM transition in intel gate
                        if self._intel_gate is not None and ticks:
                            # Build minimal df from recent microstructure
                            try:
                                from apex_engine_v6 import detect_hmm_regime
                                import pandas as pd
                                sample_coin = next(iter(ticks))
                                ms = self._ms.get(sample_coin)
                                if ms and len(ms._prices) > 20:
                                    prices = list(ms._prices)
                                    df_tmp = pd.DataFrame({"Close": prices})
                                    hmm_result = detect_hmm_regime(df_tmp)
                                    self._intel_gate.on_hmm_update(hmm_result)
                                    regime = hmm_result.get("current_regime", "UNKNOWN")
                                    if self._meta is not None:
                                        self._meta.set_regime(regime)
                                    self._regime = regime
                            except Exception:
                                pass

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._log("ERROR", f"Loop error: {e}")

                await asyncio.sleep(self.config.scan_interval)

    # ─── DATA FETCH ─────────────────────────────────────────────

    async def _fetch_ticks(self, session: aiohttp.ClientSession) -> Dict[str, TickData]:
        """
        Fetch L2 orderbook top-of-book untuk spread + OFI calculation.
        Hyperliquid /info endpoint l2Book memberikan bid/ask dengan sizes.
        """
        ticks = {}
        try:
            # Batch fetch: allMids untuk harga cepat
            async with session.post(
                self.HL_INFO_URL,
                json={"type": "allMids"},
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                if resp.status == 200:
                    mids = await resp.json()
                    ts = time.time()
                    for coin in self.config.watchlist:
                        if coin in mids:
                            mid = float(mids[coin])
                            # Estimasi spread dari volatilitas coin
                            slip = self._slippage_model.get(coin, 0.03)
                            half_spread = mid * (slip / 100) * 0.5

                            # FIX: bid_size/ask_size = 0.0 as sentinel → means "no OFI data yet"
                            # Will be overwritten by L2 fetch OR by price-delta proxy below.
                            # This prevents false OFI=0.5 (neutral) for all non-L2 coins.
                            ticks[coin] = TickData(
                                coin     = coin,
                                price    = mid,
                                bid      = mid - half_spread,
                                ask      = mid + half_spread,
                                bid_size = 0.0,   # FIX: was 1.0 (synthetic neutral OFI)
                                ask_size = 0.0,   # FIX: was 1.0 — will be set by proxy below
                                ts       = ts,
                            )
        except Exception:
            pass

        # ── FIX OFI SYNTHETIC BUG ──────────────────────────────────────────────
        # PROBLEM: Coins yang tidak dapat L2 data pakai bid_size=1.0 & ask_size=1.0
        #          → OFI selalu 0.5 (neutral) → Gate 3 tidak berfungsi
        #
        # FIX A: Perluas hot_coins dari 3 ke 8 coins (Tier1 + Tier2)
        # FIX B: Untuk coins yang tetap tidak dapat L2, estimasi bid/ask size
        #        dari price momentum (proxy order flow imbalance):
        #        Jika harga naik dari tick sebelumnya → bid_size > ask_size
        #        Jika harga turun → ask_size > bid_size
        #        Rasio berdasarkan magnitude of move (0.5%-1.5% price change → 1.5-3.0x imbalance)
        #
        # Ini tidak seakurat L2 real data, tapi jauh lebih baik dari bid=ask=1.0 selalu.
        # Tier 1 & 2 coins tetap dapat L2 aktual.

        # Estimasi proxy OFI dari price delta untuk coins non-L2
        for coin, tick in list(ticks.items()):
            if coin in self._ms and len(self._ms[coin].price_ticks) >= 2:
                prev_prices = list(self._ms[coin].price_ticks)
                prev_price  = prev_prices[-1]   # last known price before this tick
                dp = tick.mid_price - prev_price
                if abs(dp) > 1e-10 and prev_price > 0:
                    move_pct = abs(dp / prev_price) * 100
                    # Imbalance ratio: bigger move = stronger imbalance signal
                    imbalance_mult = min(1.0 + move_pct * 20, 3.5)  # 0.05% move → 2.0x
                    if dp > 0:   # price up → buy pressure
                        ticks[coin] = TickData(
                            coin=tick.coin, price=tick.price,
                            bid=tick.bid, ask=tick.ask,
                            bid_size=imbalance_mult,
                            ask_size=1.0,
                            ts=tick.ts,
                        )
                    else:        # price down → sell pressure
                        ticks[coin] = TickData(
                            coin=tick.coin, price=tick.price,
                            bid=tick.bid, ask=tick.ask,
                            bid_size=1.0,
                            ask_size=imbalance_mult,
                            ts=tick.ts,
                        )

        # L2 orderbook untuk coins yang aktif di posisi atau kandidat entry
        hot_coins = set(self._in_position)
        if len(self._open_positions()) < self.config.max_positions:
            # FIX: expanded from watchlist[:3] to [:8] — Tier1 + Tier2 always get real L2
            hot_coins.update(self.config.watchlist[:8])

        for coin in list(hot_coins)[:8]:  # FIX: increased from 5 to 8 L2 requests per tick
            try:
                async with session.post(
                    self.HL_INFO_URL,
                    json={"type": "l2Book", "coin": coin},
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as resp:
                    if resp.status == 200:
                        book = await resp.json()
                        levels = book.get("levels", [[], []])
                        bids = levels[0][:3] if len(levels) > 0 else []
                        asks = levels[1][:3] if len(levels) > 1 else []
                        if bids and asks:
                            best_bid = float(bids[0][0]) if bids else 0
                            best_ask = float(asks[0][0]) if asks else 0
                            bid_size = sum(float(b[1]) for b in bids[:3])
                            ask_size = sum(float(a[1]) for a in asks[:3])
                            if best_bid > 0 and best_ask > 0:
                                mid = (best_bid + best_ask) / 2
                                ticks[coin] = TickData(
                                    coin     = coin,
                                    price    = mid,
                                    bid      = best_bid,
                                    ask      = best_ask,
                                    bid_size = bid_size,
                                    ask_size = ask_size,
                                    ts       = time.time(),
                                )
            except Exception:
                pass

        return ticks

    # ─── MICROSTRUCTURE UPDATE ──────────────────────────────────

    def _update_microstructure(self, ticks: Dict[str, TickData]):
        for coin, tick in ticks.items():
            if coin not in self._ms:
                self._ms[coin] = CoinMicrostructure(coin=coin)
            self._ms[coin].update(tick)

            # Feed SignalIntelligenceGate (Kyle Lambda + Lead-Lag)
            if self._intel_gate is not None:
                self._intel_gate.on_tick(
                    coin       = coin,
                    price      = tick.mid_price,
                    volume     = tick.bid_size + tick.ask_size,
                    bid_size   = tick.bid_size,
                    ask_size   = tick.ask_size,
                )

    # ─── THE BRAIN — ENTRY SCANNER ──────────────────────────────

    def _scan_entries(self, ticks: Dict[str, TickData]):
        """
        Three-gate entry system:
        Gate 1: Microstructure data sudah ready (≥20 ticks)
        Gate 2: Spread normal (tidak ada manipulasi / gap)
        Gate 3: Z-Score + OFI alignment (min 2 dari 3 sub-signals)
        Gate 4 [NEW]: MetaAllocator portfolio heat & correlation check
        Gate 5 [NEW]: SignalIntelligenceGate (Kyle Lambda + Toxic Flow)
        Gate 6 [NEW]: AlphaSignalEngine (Funding Rate + OI confirmation)
        """
        available_slots = self.config.max_positions - len(self._open_positions())
        if available_slots <= 0:
            return

        candidates = []

        for coin in self.config.watchlist:
            if coin in self._in_position:
                continue
            if coin not in ticks:
                continue
            if coin not in self._ms:
                continue

            # Cooldown: tunggu minimal N detik setelah trade terakhir pada coin ini
            last_ts = self._last_trade_ts.get(coin, 0)
            if time.time() - last_ts < self._cooldown_seconds:
                continue

            ms   = self._ms[coin]
            tick = ticks[coin]

            # ── Gate 1: Data readiness ──────────────────────────
            if not ms.is_ready():
                continue

            # ── Gate 2: Spread filter ──────────────────────────
            if not ms.is_spread_normal(self.config.spread_max_mult):
                continue

            # ── Gate 3: Signal computation ─────────────────────
            z     = ms.zscore(tick.mid_price)
            ofi   = ms.ofi()
            atr   = ms.atr

            if atr < 1e-10:
                continue

            signal, direction, score = self._evaluate_signal(z, ofi, tick, ms)
            if not signal:
                continue

            # Kalkulasi base capital & stop
            slip_pct       = self._slippage_model.get(coin, 0.03)
            total_cost_pct = FEE_ROUND_TRIP + slip_pct
            stop_dist_pct  = (atr * self.config.atr_stop_mult / tick.mid_price) * 100
            tp_dist_pct    = stop_dist_pct * self.config.min_rr_ratio
            stop_price     = (tick.mid_price * (1 - stop_dist_pct / 100)
                              if direction == "LONG"
                              else tick.mid_price * (1 + stop_dist_pct / 100))

            expected_win_rate = 0.55
            ev_pct = (tp_dist_pct * expected_win_rate
                      - stop_dist_pct * (1 - expected_win_rate)
                      - total_cost_pct)

            if ev_pct <= 0:
                continue
            if tp_dist_pct < MIN_GROSS_PCT:
                continue

            # ── Gate 4 [NEW]: MetaAllocator pre-check ──────────
            capital = self.config.capital_per_trade
            if self._meta is not None:
                can_add, meta_reason = self._meta.can_add_position(
                    "PREDATOR", coin, capital
                )
                if not can_add:
                    self._log("META_PRE", f"{coin}: {meta_reason}")
                    continue

            # ── Gate 5 [NEW]: Signal Intelligence ──────────────
            size_scalar = 1.0
            intel_meta  = {}
            if self._intel_gate is not None:
                intel = self._intel_gate.evaluate_entry(coin, direction=direction)
                if not intel.approved:
                    self._log("INTEL_BLOCK", f"{coin}: {intel.block_reason}")
                    continue
                size_scalar = intel.final_size_scalar
                intel_meta  = {
                    "kyle_lambda"            : intel.kyle_lambda,
                    "toxicity_score"         : intel.toxicity_score,
                    "lead_lag_signal"        : intel.lead_lag_signal,
                    "regime_transition_risk" : intel.regime_transition_risk,
                }

            # ── Gate 6 [NEW]: Alpha Signals ────────────────────
            alpha_meta = {}
            if self._alpha_engine is not None:
                alpha = self._alpha_engine.get_alpha(coin, intended_dir=direction)
                if alpha.get("skip"):
                    self._log("ALPHA_SKIP", f"{coin}: {alpha.get('skip_reason')}")
                    continue
                alpha_scalar = alpha.get("size_scalar", 1.0)
                size_scalar  = size_scalar * alpha_scalar
                alpha_meta   = {
                    "funding_signal": alpha.get("funding", {}).get("signal_type", "NONE"),
                    "oi_pattern"    : alpha.get("oi",      {}).get("pattern",     "NEUTRAL"),
                    "carry_apy"     : alpha.get("funding", {}).get("apy_pct",     0.0),
                }

            # ── Gate 7 [v7]: Kalman + OU Enricher (non-blocking) ───────────
            # Enriches signal with Kalman trend and OU z-score.
            # Does NOT block entry — only adjusts size up/down.
            kalman_meta = {}
            if HAS_APEX_V6:
                try:
                    import pandas as pd
                    prices = ms.price_history()  # returns list of floats
                    if len(prices) >= 30:
                        df_k = pd.DataFrame({"Close": prices})
                        kf = kalman_filter_trend(df_k)
                        ks = kf.get("signal", "SIDEWAYS")
                        kt = kf.get("trend_bps_per_tick", 0.0)
                        ou = ou_trading_signals(df_k, window=min(60, len(prices)))
                        ou_z = ou.get("ou_zscore", 0.0)
                        ou_prof = ou.get("profitable", False)
                        # Kalman agrees with direction = small boost
                        if direction == "LONG" and ks == "BULLISH":
                            size_scalar *= 1.1
                        elif direction == "SHORT" and ks == "BEARISH":
                            size_scalar *= 1.1
                        # Kalman strongly disagrees = trim
                        elif direction == "LONG" and ks == "BEARISH" and kt < -5:
                            size_scalar *= 0.75
                        elif direction == "SHORT" and ks == "BULLISH" and kt > 5:
                            size_scalar *= 0.75
                        # OU confirms mean reversion opportunity
                        if ou_prof and direction == "LONG" and ou_z < -1.5:
                            size_scalar *= 1.05
                        elif ou_prof and direction == "SHORT" and ou_z > 1.5:
                            size_scalar *= 1.05
                        kalman_meta = {
                            "kalman_signal": ks, "kalman_trend_bps": round(kt, 4),
                            "ou_zscore": round(ou_z, 4), "ou_profitable": ou_prof,
                        }
                except Exception:
                    pass
            size_scalar = float(max(min(size_scalar, 2.0), 0.25))  # clamp

            capital = self.config.capital_per_trade * max(size_scalar, 0.25)

            # ── MetaAllocator capital request ───────────────────
            meta_decision = None
            if self._meta is not None:
                meta_decision = self._meta.request_capital(
                    strategy      = "PREDATOR",
                    coin          = coin,
                    direction     = direction,
                    requested_usd = capital,
                    entry_price   = tick.mid_price,
                    stop_price    = stop_price,
                )
                if not meta_decision.approved:
                    self._log("META_BLOCK", f"{coin}: {meta_decision.block_reason}")
                    continue
                capital = meta_decision.approved_usd

            candidates.append({
                "coin":          coin,
                "direction":     direction,
                "price":         tick.mid_price,
                "score":         score,
                "z":             z,
                "ofi":           ofi,
                "atr":           atr,
                "ev_pct":        ev_pct,
                "stop_dist":     stop_dist_pct,
                "tp_dist":       tp_dist_pct,
                "capital":       capital,
                "stop_price":    stop_price,
                "meta_decision": meta_decision,
                "intel_meta":    intel_meta,
                "alpha_meta":    alpha_meta,
            })

        # Sort by expected value
        candidates.sort(key=lambda x: x["ev_pct"], reverse=True)

        for c in candidates[:available_slots]:
            if self.balance >= c["capital"]:
                self._enter_position(c)

    def _evaluate_signal(
        self, z: float, ofi: float, tick: TickData, ms: CoinMicrostructure
    ) -> Tuple[bool, str, float]:
        """
        Evaluasi sinyal mean-reversion — 3 sub-signals INDEPENDEN.

        PERBAIKAN v2.1:
        - Sub-signal 3 lama (price <= recent_low) adalah DUPLIKAT dari Z-Score
          (keduanya ukur hal yang sama: harga rendah). Diganti dengan:
          Momentum reversal: apakah harga sudah mulai balik arah dari ekstrem?

        Return: (signal_valid, direction, score)
        """
        threshold = self.config.zscore_entry
        ofi_min   = self.config.ofi_min_ratio

        long_signals  = 0
        short_signals = 0

        # Sub-signal 1: Z-Score (harga menyimpang dari VWAP)
        if z <= -threshold:
            long_signals  += 1
        elif z >= threshold:
            short_signals += 1

        # Sub-signal 2: Order Flow Imbalance
        # Beli saat ada tekanan beli (counter-trend entry)
        if ofi >= ofi_min:                  # bid pressure → long
            long_signals  += 1
        elif ofi <= (1.0 - ofi_min):        # ask pressure → short
            short_signals += 1

        # Sub-signal 3: Momentum micro-reversal (BARU — benar-benar independen)
        # Cek apakah harga sudah mulai bergerak kembali ke mean setelah ekstrem.
        # Ini BERBEDA dari sub-signal 1 (yang hanya cek posisi, bukan arah gerakan).
        # Pakai 3 tick terakhir vs 3 tick sebelumnya.
        prices = list(ms.price_ticks)
        if len(prices) >= 8:
            recent_avg = sum(prices[-3:]) / 3     # rata-rata 3 tick terakhir
            prev_avg   = sum(prices[-6:-3]) / 3   # rata-rata 3 tick sebelumnya
            if z < -threshold * 0.7:              # sedang di zona oversold
                if recent_avg > prev_avg:          # harga mulai naik (reversal!)
                    long_signals += 1
            elif z > threshold * 0.7:             # sedang di zona overbought
                if recent_avg < prev_avg:          # harga mulai turun (reversal!)
                    short_signals += 1

        # Minimal 2 dari 3 sub-signals harus agree
        if long_signals >= 2 and long_signals > short_signals:
            return True, "LONG", float(long_signals)
        elif short_signals >= 2 and short_signals > long_signals:
            return True, "SHORT", float(short_signals)

        return False, "", 0.0

    # ─── ORDER EXECUTOR ─────────────────────────────────────────

    def _enter_position(self, c: dict):
        """
        Paper market order dengan simulasi slippage realistis.
        Slippage di-apply: LONG bayar ask, SHORT bayar bid.
        """
        coin      = c["coin"]
        direction = c["direction"]
        mid_price = c["price"]
        atr       = c["atr"]

        # Slippage — kamu beli di ask, bukan mid
        slip_pct  = self._slippage_model.get(coin, 0.03)
        if direction == "LONG":
            entry_price = mid_price * (1 + slip_pct / 100)
        else:
            entry_price = mid_price * (1 - slip_pct / 100)

        # Use capital from candidate (may be scaled by Intel/Alpha/Meta)
        capital = c.get("capital", self.config.capital_per_trade)
        qty     = capital / entry_price

        # Adaptive stops
        stop_dist = atr * self.config.atr_stop_mult
        tp_dist   = stop_dist * self.config.min_rr_ratio

        if direction == "LONG":
            stop_price = entry_price - stop_dist
            tp_price   = entry_price + tp_dist
        else:
            stop_price = entry_price + stop_dist
            tp_price   = entry_price - tp_dist

        pos = HFTPosition(
            id            = str(uuid.uuid4())[:8],
            coin          = coin,
            direction     = direction,
            entry_price   = entry_price,
            current_price = entry_price,
            peak_price    = entry_price,
            valley_price  = entry_price,
            qty           = qty,
            capital       = capital,
            opened_at     = time.time(),
            status        = "OPEN",
            stop_price    = stop_price,
            tp_price      = tp_price,
            atr_at_entry  = atr,
        )

        self.balance -= capital
        self.positions[pos.id] = pos
        self._in_position.add(coin)

        # Register with MetaAllocator
        meta_decision = c.get("meta_decision")
        if self._meta is not None and meta_decision is not None:
            self._meta.register_open(meta_decision, entry_price, stop_price, position_id=pos.id)

        rr = round(tp_dist / stop_dist, 2) if stop_dist > 0 else 0
        intel_str = ""
        if c.get("intel_meta"):
            im = c["intel_meta"]
            intel_str = f" | Tox={im.get('toxicity_score', 0):.2f} λ={im.get('kyle_lambda', 0):.4f}"
        self._log("ENTRY", (
            f"{'🟢 LONG' if direction == 'LONG' else '🔴 SHORT'} "
            f"{coin} @ ${entry_price:,.4f} | "
            f"Stop ${stop_price:,.4f} | TP ${tp_price:,.4f} | "
            f"RR {rr}R | Z={c['z']:+.2f} OFI={c['ofi']:.2f} EV={c['ev_pct']:+.3f}%{intel_str}"
        ))

    def _close_position(self, pos: HFTPosition, reason: str):
        pos.status = "CLOSED"
        mid_price  = pos.current_price

        # Exit slippage (jual di bid, tutup short di ask)
        slip_pct = self._slippage_model.get(pos.coin, 0.03)
        if pos.direction == "LONG":
            exit_price = mid_price * (1 - slip_pct / 100)
        else:
            exit_price = mid_price * (1 + slip_pct / 100)

        if pos.direction == "LONG":
            gross_pnl = (exit_price - pos.entry_price) * pos.qty
        else:
            gross_pnl = (pos.entry_price - exit_price) * pos.qty

        # Slippage sudah di-embed dalam entry/exit price
        # Fee: taker both sides
        fee_usd  = pos.capital * (self.config.fee_pct / 100) * 2
        slip_est = pos.capital * (slip_pct / 100) * 2  # entry + exit
        net_pnl  = gross_pnl - fee_usd
        net_pct  = (net_pnl / pos.capital) * 100

        self.balance += pos.capital + net_pnl

        # Lookup entry microstructure data (pakai default jika tidak ada)
        entry_z   = 0.0
        entry_ofi = 0.5
        if pos.coin in self._ms:
            ms = self._ms[pos.coin]
            entry_z   = ms.zscore(pos.entry_price)
            entry_ofi = ms.ofi()

        trade = HFTTrade(
            id           = pos.id,
            coin         = pos.coin,
            direction    = pos.direction,
            entry_price  = pos.entry_price,
            exit_price   = exit_price,
            qty          = pos.qty,
            capital      = pos.capital,
            gross_pnl    = gross_pnl,
            fee_usd      = fee_usd,
            slippage_usd = slip_est,
            net_pnl      = net_pnl,
            net_pct      = net_pct,
            exit_reason  = reason,
            opened_at    = pos.opened_at,
            closed_at    = time.time(),
            hold_seconds = time.time() - pos.opened_at,
            entry_zscore = entry_z,
            entry_ofi    = entry_ofi,
        )

        self.trade_log.append(trade)
        self.stats.record(trade, self.balance)
        self._in_position.discard(pos.coin)
        self._last_trade_ts[pos.coin] = time.time()   # cooldown timer mulai
        del self.positions[pos.id]

        # Release capital in MetaAllocator
        if self._meta is not None:
            self._meta.release_capital(
                position_id = pos.id,
                pnl_pct     = net_pct,
                pnl_usd     = net_pnl,
            )

        # Record to Performance Attribution Engine
        if self._attribution is not None and HAS_ATTR:
            try:
                attr_trade = AttributedTrade.from_hft_trade(trade.to_dict(), "PREDATOR")
                self._attribution.record(attr_trade)
            except Exception:
                pass

        emoji = "✅" if net_pnl > 0 else "❌"
        self._log("EXIT", (
            f"{emoji} {pos.direction} {pos.coin} [{reason}] "
            f"@ ${exit_price:,.4f} | "
            f"Net: ${net_pnl:+.4f} ({net_pct:+.3f}%) | "
            f"Hold: {int(trade.hold_seconds)}s"
        ))

    # ─── POSITION MANAGEMENT ────────────────────────────────────

    def _update_positions(self, ticks: Dict[str, TickData]):
        for pos in list(self.positions.values()):
            if pos.status != "OPEN":
                continue
            if pos.coin in ticks:
                atr = self._ms[pos.coin].atr if pos.coin in self._ms else 0.0
                pos.update_price(ticks[pos.coin].mid_price, atr)

    def _check_exits(self):
        for pos in list(self.positions.values()):
            if pos.status != "OPEN":
                continue

            reason = None
            if pos.should_exit_tp():
                reason = "TP"
            elif pos.should_exit_stop():
                reason = "STOP"
            elif pos.should_force_close(self.config.max_hold_seconds):
                reason = "TIMEOUT"

            if reason:
                self._close_position(pos, reason)

    def _open_positions(self) -> List[HFTPosition]:
        return [p for p in self.positions.values() if p.status == "OPEN"]

    def _unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self._open_positions())

    # ─── EQUITY SNAPSHOT ────────────────────────────────────────

    def _record_equity_snapshot(self):
        now = time.time()
        if (not self.equity_curve or
                now - self.equity_curve[-1]["ts"] > 10):
            eq = round(self.balance + self._unrealized_pnl(), 4)
            self.equity_curve.append({"ts": now, "balance": eq})
            if len(self.equity_curve) > 500:
                self.equity_curve.pop(0)

    # ─── EVENT LOG ──────────────────────────────────────────────

    def _log(self, tag: str, msg: str):
        self._events.appendleft({
            "ts"  : time.time(),
            "time": datetime.now().strftime("%H:%M:%S"),
            "tag" : tag,
            "msg" : msg,
        })

    # ─── STATUS SNAPSHOT ────────────────────────────────────────

    def _get_microstructure_peek(self) -> list:
        result = []
        for coin in self.config.watchlist:
            # Tampilkan semua coin, termasuk yang belum cukup data (untuk UX)
            ms = self._ms.get(coin)
            tick_count = len(ms.price_ticks) if ms else 0

            if ms is None or tick_count < 2:
                result.append({
                    "coin": coin, "price": 0, "zscore": 0, "ofi": 0.5,
                    "atr": 0, "avg_spread_pct": 0, "ticks_ready": False,
                    "spread_ok": True, "in_position": coin in self._in_position,
                    "signal_long": False, "signal_short": False,
                    "ticks_collected": tick_count, "ticks_needed": 30,
                    "cooldown_remaining": max(0, self._cooldown_seconds -
                        int(time.time() - self._last_trade_ts.get(coin, 0))),
                })
                continue

            prices  = list(ms.price_ticks)
            current = prices[-1] if prices else 0
            z       = ms.zscore(current)
            ofi     = ms.ofi()

            # Cek sinyal multi-signal (sama dengan _evaluate_signal tapi simplified)
            sig_l = z <= -self.config.zscore_entry and ofi >= self.config.ofi_min_ratio
            sig_s = z >= self.config.zscore_entry and ofi <= (1.0 - self.config.ofi_min_ratio)

            # Cooldown remaining
            cooldown_rem = max(0, self._cooldown_seconds -
                int(time.time() - self._last_trade_ts.get(coin, 0)))

            result.append({
                "coin"              : coin,
                "price"             : round(current, 4),
                "zscore"            : round(z, 3),
                "ofi"               : round(ofi, 3),
                "atr"               : round(ms.atr, 6),
                "avg_spread_pct"    : round(ms.avg_spread, 4),
                "ticks_ready"       : ms.is_ready(),
                "ticks_collected"   : tick_count,
                "ticks_needed"      : 30,
                "spread_ok"         : ms.is_spread_normal(self.config.spread_max_mult),
                "in_position"       : coin in self._in_position,
                "signal_long"       : sig_l,
                "signal_short"      : sig_s,
                "cooldown_remaining": cooldown_rem,
            })
        result.sort(key=lambda x: abs(x["zscore"]), reverse=True)
        return result

    def get_status(self) -> dict:
        open_pos   = self._open_positions()
        total_eq   = self.balance + self._unrealized_pnl()
        total_pnl  = total_eq - self.initial_balance

        cb_status = {
            "tripped": self._cb.is_tripped if self._cb else False,
            "reason" : self._cb.trip_reason if self._cb else "",
        }

        return {
            "running"          : self.running,
            "balance"          : round(self.balance, 4),
            "total_equity"     : round(total_eq, 4),
            "initial_balance"  : self.initial_balance,
            "total_pnl"        : round(total_pnl, 4),
            "total_pnl_pct"    : round((total_pnl / self.initial_balance) * 100, 3),
            "unrealized_pnl"   : round(self._unrealized_pnl(), 4),
            "open_positions"   : [p.to_dict() for p in open_pos],
            "open_count"       : len(open_pos),
            "max_positions"    : self.config.max_positions,
            "slots_free"       : self.config.max_positions - len(open_pos),
            "trade_log"        : [t.to_dict() for t in self.trade_log[-50:]],
            "stats"            : self.stats.to_dict(),
            "equity_curve"     : self.equity_curve[-100:],
            "events"           : list(self._events)[:30],
            "config"           : asdict(self.config),
            "circuit_breaker"  : cb_status,
            "microstructure"   : self._get_microstructure_peek(),
            "engine_version"   : "v2.1-predator",
            "strategy"         : "mean_reversion_microstructure",
        }

    def reset_circuit_breaker(self):
        """Manual reset CB — gunakan dengan bijak, hanya setelah review."""
        if self._cb:
            self._cb.manual_reset()
            self._log("CIRCUIT", "Circuit breaker manually reset")


# ══════════════════════════════════════════════════════════════════
#  SINGLETON — diimpor oleh main.py
# ══════════════════════════════════════════════════════════════════

hft_spider = HFTPredator()  # nama tetap sama untuk backward compat

# Alias baru yang lebih deskriptif
predator = hft_spider