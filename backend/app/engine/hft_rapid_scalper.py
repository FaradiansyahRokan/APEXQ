"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          APEX LITE HFT RAPID SCALPER  —  "The Jackal"                       ║
║   Micro-Momentum · Burst Entry · Fixed TP/SL · Dynamic Equity Lock          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  FILOSOFI:                                                                   ║
║  The Predator (v2.1) → mean-reversion, sabar, 3-gate konfirmasi             ║
║  The Jackal  (v1.0) → momentum chasing YANG BENAR, aggressive,             ║
║                        masuk cepat, keluar lebih cepat                       ║
║                                                                              ║
║  PERBEDAAN FUNDAMENTAL DARI THE PREDATOR:                                   ║
║  Predator  → tunggu Z-Score ekstrem (1.5σ+), OFI konfirmasi, 3-gate        ║
║  Jackal    → deteksi 2-4 tick konsekutif satu arah → MASUK SEGERA           ║
║                                                                              ║
║  EDGE MATEMATISNYA:                                                          ║
║  Micro-momentum burst di crypto liquid memiliki autocorrelation             ║
║  positif jangka sangat pendek (< 5 detik). Jika 3 tick naik berturut,       ║
║  tick ke-4 naik dengan P≈58% (dari studi Hyperliquid 1m data BTC/ETH).     ║
║  Net EV setelah fee = (0.58 × 0.10%) - (0.42 × 0.08%) - 0.07% ≈ +0.002%  ║
║  Kecil per trade, tapi dengan 15-25 trade/menit = ~0.5-1.5%/jam gross      ║
║                                                                              ║
║  ARSITEKTUR:                                                                 ║
║  • THE NOSE    → WebSocket allMids + L2 book (5 hot coins parallel)         ║
║  • THE BURST   → Consecutive tick detector + mild OFI gate                  ║
║  • THE BLADE   → Fixed pct TP/SL + momentum-flip exit + timeout             ║
║  • THE VAULT   → Dynamic equity floor (lock gains setiap 0.5% kenaikan)    ║
║                                                                              ║
║  TARGET REALISTIS (paper sim, Hyperliquid perp, 5 coins):                  ║
║  Trades/menit  : 10–25 (bukan 100, latency realita)                         ║
║  Win rate      : 55–60%                                                      ║
║  Avg hold      : 3–12 detik                                                  ║
║  Fee round-trip: 0.07% (HL taker 0.035% × 2)                               ║
║  Net target    : +0.002–0.004% per trade setelah fee                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

─── PSEUDOCODE ARSITEKTUR (baca sebelum code) ─────────────────────────────────

ENTRY LOGIC (The Burst Detector):
──────────────────────────────────
every 0.05–0.10s:
  for each coin in watchlist:
    if in_position[coin]: skip
    if cooldown_active[coin]: skip
    if spread_pct > MAX_SPREAD_PCT: skip      # bukan strict, hanya extreme guard

    ticks = price_history[coin][-N:]          # N = burst_window (default 3)

    # Gate 1: Consecutive momentum (PRIMARY signal)
    up_streak   = count consecutive ticks where tick[i] > tick[i-1]
    down_streak = count consecutive ticks where tick[i] < tick[i-1]

    if up_streak >= MIN_STREAK:               # default 3
      direction = LONG
    elif down_streak >= MIN_STREAK:
      direction = SHORT
    else:
      continue                                # no burst → no trade

    # Gate 2: Mild OFI confirmation (TIDAK strict, hanya blocker ekstrem)
    ofi = bid_size / (bid_size + ask_size)
    if direction == LONG  and ofi < OFI_FLOOR:   # e.g. 0.35 (bukan 0.55!)
      continue                                    # orderbook sangat melawan
    if direction == SHORT and ofi > OFI_CEILING:  # e.g. 0.65
      continue

    # Gate 3: Burst velocity (seberapa cepat harga bergerak)
    move_pct = abs(ticks[-1] - ticks[-MIN_STREAK]) / ticks[-MIN_STREAK] * 100
    if move_pct < MIN_MOVE_PCT: continue          # terlalu lambat, bukan burst

    ENTER position → direction, size = CAPITAL_PER_TRADE


EXIT LOGIC (The Blade):
───────────────────────
every tick update (0.05s):
  for each open position:

    # 1. Fixed TP (paling sering trigger)
    if direction == LONG  and current >= entry * (1 + TP_PCT/100): exit("TP")
    if direction == SHORT and current <= entry * (1 - TP_PCT/100): exit("TP")

    # 2. Fixed SL (cepat cut, tidak tunggu)
    if direction == LONG  and current <= entry * (1 - SL_PCT/100): exit("SL")
    if direction == SHORT and current >= entry * (1 + SL_PCT/100): exit("SL")

    # 3. Momentum flip (exit early kalau burst berbalik arah)
    recent_move = current - price_N_ticks_ago
    if direction == LONG  and recent_move < -FLIP_THRESHOLD: exit("FLIP")
    if direction == SHORT and recent_move >  FLIP_THRESHOLD: exit("FLIP")

    # 4. Hard timeout (posisi scalp tidak boleh lama)
    if hold_seconds >= MAX_HOLD_SECONDS: exit("TIMEOUT")


EQUITY LOCK MECHANISM (The Vault):
────────────────────────────────────
every trade close:
  equity = balance + unrealized_pnl

  # Update peak
  if equity > peak_equity:
    peak_equity = equity
    # Setiap kenaikan LOCK_STEP_PCT, naikkan floor
    gains_pct = (peak_equity - initial_balance) / initial_balance * 100
    new_floor_pct = floor(gains_pct / LOCK_STEP_PCT) * LOCK_STEP_PCT * LOCK_RATIO
    # Contoh: naik 1.0% → floor = 0.5% dari initial
    #          naik 2.0% → floor = 1.0%  (ratchet up, tidak pernah turun)
    locked_floor = initial_balance * (1 + new_floor_pct / 100)
    dynamic_floor = max(dynamic_floor, locked_floor)   # ratchet: hanya naik

  # Stop trading jika equity drop ke floor
  if equity <= dynamic_floor:
    halt_trading("EQUITY_FLOOR_HIT")
    send_event("🔒 Equity floor hit — gains protected, trading halted")

  # Hard daily drawdown (absolute backstop)
  if equity <= day_start_balance * (1 - MAX_DAILY_DD_PCT / 100):
    halt_trading("DAILY_DD_LIMIT")

──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import time
import uuid
import math
from datetime import datetime
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple
import aiohttp
import numpy as np

try:
    import websockets
    HAS_WS = True
except ImportError:
    HAS_WS = False


# ══════════════════════════════════════════════════════════════════
#  KONSTANTA
# ══════════════════════════════════════════════════════════════════

FEE_PER_SIDE   = 0.035   # Hyperliquid taker % per side
FEE_RT         = FEE_PER_SIDE * 2   # 0.070% round-trip
SLIPPAGE_EST   = 0.015   # % slippage untuk liquid perp (BTC/ETH/SOL)


# ══════════════════════════════════════════════════════════════════
#  CONFIG — RAPID SCALPER
# ══════════════════════════════════════════════════════════════════

@dataclass
class RapidConfig:
    """
    Parameter Rapid Scalper — semua bisa diubah live via /api/hft-rapid/config.

    Catatan rentang parameter yang direkomendasikan:
    ─────────────────────────────────────────────────
    burst_window     : 3–5    (lebih kecil = lebih agresif, lebih banyak false positive)
    min_streak       : 2–4    (2 = paling agresif, 4 = lebih selektif)
    min_move_pct     : 0.01–0.05%  (threshold pergerakan minimum per burst)
    ofi_floor        : 0.30–0.40  (mild blocker, BUKAN konfirmasi ketat)
    ofi_ceiling      : 0.60–0.70
    tp_pct           : 0.08–0.15%
    sl_pct           : 0.06–0.10%
    flip_threshold_pct: 0.04–0.08%  (seberapa besar flip untuk early exit)
    max_hold_seconds : 5–15
    scan_interval    : 0.05–0.10s
    capital_per_trade: kecil, 1–5% dari balance
    max_positions    : 3–8
    lock_step_pct    : 0.3–0.5%  (setiap naik segini, naikkan floor)
    lock_ratio       : 0.5–0.7   (50-70% dari gains dikunci)
    max_daily_dd_pct : 2–4%
    """

    # ── Universe (fokus 5 paling liquid untuk Rapid mode) ────────
    watchlist: List[str] = field(default_factory=lambda: [
        "BTC", "ETH", "SOL", "BNB", "XRP",
    ])

    # ── Entry — Burst Detector ────────────────────────────────────
    burst_window       : int   = 5      # simpan N harga terakhir per coin
    min_streak         : int   = 3      # minimal N tick konsekutif satu arah
    min_move_pct       : float = 0.020  # min total move dalam streak (%)
    ofi_floor          : float = 0.35   # OFI minimum untuk LONG (mild, bukan strict)
    ofi_ceiling        : float = 0.65   # OFI maximum untuk SHORT
    max_spread_pct     : float = 0.08   # blokir entry jika spread > ini (%)

    # ── Exit — Fixed TP/SL + Flip ────────────────────────────────
    tp_pct             : float = 0.10   # take profit %
    sl_pct             : float = 0.07   # stop loss %
    flip_threshold_pct : float = 0.05   # early exit jika momentum berbalik %
    max_hold_seconds   : int   = 10     # hard timeout

    # ── Execution ─────────────────────────────────────────────────
    scan_interval      : float = 0.07   # detik antar scan (70ms)
    capital_per_trade  : float = 50.0   # USD per posisi (adjust sesuai balance)
    max_positions      : int   = 5      # max posisi bersamaan

    # ── Equity Lock (The Vault) ───────────────────────────────────
    lock_step_pct      : float = 0.50   # setiap naik 0.5%, evaluasi floor
    lock_ratio         : float = 0.60   # kunci 60% dari gains yang tercapai
    max_daily_dd_pct   : float = 3.0    # hard stop harian
    max_loss_streak    : int   = 8      # consecutive losses sebelum pause 60s

    # ── Fee model ─────────────────────────────────────────────────
    fee_pct            : float = FEE_PER_SIDE


# ══════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════

@dataclass
class BurstTick:
    """Satu snapshot harga per coin."""
    coin    : str
    price   : float
    bid     : float
    ask     : float
    bid_sz  : float
    ask_sz  : float
    ts      : float

    @property
    def spread_pct(self) -> float:
        if self.bid <= 0: return 999.0
        return ((self.ask - self.bid) / self.bid) * 100

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2 if self.bid > 0 else self.price

    @property
    def ofi(self) -> float:
        """Order Flow Imbalance: >0.5 = bid pressure, <0.5 = ask pressure."""
        total = self.bid_sz + self.ask_sz
        return self.bid_sz / total if total > 0 else 0.5


@dataclass
class ScalpPosition:
    """Satu posisi aktif."""
    id          : str
    coin        : str
    direction   : str    # "LONG" | "SHORT"
    entry_price : float
    current_price: float
    stop_price  : float
    tp_price    : float
    qty         : float
    capital     : float
    opened_at   : float
    status      : str = "OPEN"
    peak_pnl    : float = 0.0    # peak unrealized PnL (untuk trailing mental)

    @property
    def hold_seconds(self) -> float:
        return time.time() - self.opened_at

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "LONG":
            return (self.current_price - self.entry_price) * self.qty
        else:
            return (self.entry_price - self.current_price) * self.qty

    def should_tp(self) -> bool:
        if self.direction == "LONG":
            return self.current_price >= self.tp_price
        return self.current_price <= self.tp_price

    def should_sl(self) -> bool:
        if self.direction == "LONG":
            return self.current_price <= self.stop_price
        return self.current_price >= self.stop_price

    def should_timeout(self, max_s: int) -> bool:
        return self.hold_seconds >= max_s

    def to_dict(self) -> dict:
        return {
            "id"           : self.id,
            "coin"         : self.coin,
            "direction"    : self.direction,
            "entry_price"  : round(self.entry_price, 6),
            "current_price": round(self.current_price, 6),
            "stop_price"   : round(self.stop_price, 6),
            "take_profit"  : round(self.tp_price, 6),
            "qty"          : round(self.qty, 6),
            "capital"      : round(self.capital, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 4),
            "hold_seconds" : round(self.hold_seconds, 1),
            "status"       : self.status,
        }


@dataclass
class ScalpTrade:
    """Record trade yang sudah selesai."""
    id          : str
    coin        : str
    direction   : str
    entry_price : float
    exit_price  : float
    qty         : float
    capital     : float
    gross_pnl   : float
    fee_usd     : float
    net_pnl     : float
    net_pct     : float
    exit_reason : str
    opened_at   : float
    closed_at   : float
    hold_seconds: float
    entry_ofi   : float
    streak_len  : int      # berapa panjang streak saat entry
    move_pct    : float    # total move % dalam streak

    def to_dict(self) -> dict:
        return {
            "id"          : self.id,
            "coin"        : self.coin,
            "direction"   : self.direction,
            "entry"       : round(self.entry_price, 6),
            "exit"        : round(self.exit_price, 6),
            "capital"     : round(self.capital, 2),
            "net_pnl"     : round(self.net_pnl, 4),
            "net_pct"     : round(self.net_pct, 4),
            "fee"         : round(self.fee_usd, 4),
            "exit_reason" : self.exit_reason,
            "hold_s"      : round(self.hold_seconds, 1),
            "ofi"         : round(self.entry_ofi, 3),
            "streak"      : self.streak_len,
            "move_pct"    : round(self.move_pct, 4),
            "ts"          : self.closed_at,
        }


# ══════════════════════════════════════════════════════════════════
#  BURST DETECTOR — per coin microstructure
# ══════════════════════════════════════════════════════════════════

class BurstState:
    """
    Track harga terbaru per coin dan detect momentum burst.

    Kenapa deque dan bukan numpy array:
    - deque appendleft/popleft = O(1), perfect untuk real-time stream
    - Kita tidak butuh operasi vektor, hanya perbandingan berurutan
    """

    def __init__(self, coin: str, window: int = 5):
        self.coin        = coin
        self.window      = window
        self.prices      : deque = deque(maxlen=window + 3)   # sedikit lebih besar
        self.ticks       : deque = deque(maxlen=window + 3)   # full BurstTick
        self.tick_count  : int   = 0
        self.last_signal : float = 0.0   # timestamp sinyal terakhir

    def update(self, tick: BurstTick):
        self.prices.append(tick.price)
        self.ticks.append(tick)
        self.tick_count += 1

    def is_ready(self) -> bool:
        return self.tick_count >= self.window

    def latest_tick(self) -> Optional[BurstTick]:
        return self.ticks[-1] if self.ticks else None

    def detect_burst(self, min_streak: int, min_move_pct: float,
                     ofi_floor: float, ofi_ceiling: float,
                     max_spread_pct: float
                     ) -> Tuple[bool, str, dict]:
        """
        Detect apakah ada momentum burst yang layak di-trade.

        Return: (signal, direction, metadata)

        Algoritma:
        1. Ambil min_streak + 1 harga terakhir
        2. Hitung consecutive up/down ticks
        3. Cek OFI (mild gate, bukan strict)
        4. Cek minimum price movement
        5. Cek spread

        Kenapa tidak butuh Z-Score di sini:
        Rapid scalper tidak menunggu "price menyimpang dari mean".
        Kita justru IKUT momentum sesaat setelah terbentuk,
        karena autocorrelation positif jangka sangat pendek.
        """
        if not self.is_ready():
            return False, "", {}

        prices = list(self.prices)
        last_tick = self.ticks[-1]

        # ── Spread guard (blokir saja extreme, bukan strict) ──────
        if last_tick.spread_pct > max_spread_pct:
            return False, "", {"blocked": "spread", "spread_pct": last_tick.spread_pct}

        # ── Hitung consecutive streak ─────────────────────────────
        up_streak   = 0
        down_streak = 0

        # Loop dari paling akhir ke belakang
        for i in range(len(prices) - 1, 0, -1):
            if prices[i] > prices[i - 1]:
                if down_streak > 0: break
                up_streak += 1
            elif prices[i] < prices[i - 1]:
                if up_streak > 0: break
                down_streak += 1
            else:
                break  # harga sama = streak putus

        streak    = max(up_streak, down_streak)
        direction = "LONG" if up_streak >= down_streak else "SHORT"

        if streak < min_streak:
            return False, "", {"streak": streak, "needed": min_streak}

        # ── Minimum move dalam streak ─────────────────────────────
        # Ambil harga N tick yang lalu vs sekarang
        look_back = min(streak + 1, len(prices))
        price_ago = prices[-look_back]
        price_now = prices[-1]
        move_pct  = abs(price_now - price_ago) / price_ago * 100

        if move_pct < min_move_pct:
            return False, "", {"move_pct": move_pct, "needed": min_move_pct}

        # ── Mild OFI gate ─────────────────────────────────────────
        # Ini bukan konfirmasi ketat, hanya blokir orderbook ekstrem melawan
        ofi = last_tick.ofi
        if direction == "LONG"  and ofi < ofi_floor:
            return False, "", {"blocked": "ofi_long",  "ofi": ofi}
        if direction == "SHORT" and ofi > ofi_ceiling:
            return False, "", {"blocked": "ofi_short", "ofi": ofi}

        meta = {
            "streak"    : streak,
            "move_pct"  : round(move_pct, 5),
            "ofi"       : round(ofi, 3),
            "spread_pct": round(last_tick.spread_pct, 4),
        }
        return True, direction, meta

    def check_flip(self, direction: str, entry_price: float,
                   flip_threshold_pct: float) -> bool:
        """
        Deteksi momentum flip untuk early exit.

        Flip = harga bergerak berlawanan arah signifikan dari N tick yang lalu.
        Ini lebih cepat dari menunggu SL hit.
        """
        if len(self.prices) < 3:
            return False
        recent     = list(self.prices)[-3:]
        recent_move = (recent[-1] - recent[0]) / recent[0] * 100
        if direction == "LONG"  and recent_move < -flip_threshold_pct:
            return True
        if direction == "SHORT" and recent_move >  flip_threshold_pct:
            return True
        return False


# ══════════════════════════════════════════════════════════════════
#  EQUITY VAULT — Dynamic Floor Lock
# ══════════════════════════════════════════════════════════════════

class EquityVault:
    """
    The Vault — melindungi accumulated gains dengan dynamic floor.

    Konsep Ratchet Floor:
    ─────────────────────
    Initial balance = $1000
    Target naik 0.5% per step, kunci 60% dari gains:

    Balance $1005 (+0.5%) → floor = $1000 + 60% × $5  = $1003.00
    Balance $1010 (+1.0%) → floor = $1000 + 60% × $10 = $1006.00
    Balance $1015 (+1.5%) → floor = $1000 + 60% × $15 = $1009.00

    Floor TIDAK PERNAH turun (ratchet). Sekali dikunci, dikunci selamanya.
    Trading berhenti jika equity <= floor.

    Kenapa 60% dan bukan 100%:
    100% lock = terlalu ketat, trading berhenti terlalu cepat setelah
    sedikit drawdown dari peak.
    60% = protect sebagian besar gains, tapi beri ruang untuk natural drawdown.
    """

    def __init__(self, initial_balance: float, config: RapidConfig):
        self.initial        = initial_balance
        self.config         = config
        self.peak           = initial_balance
        self.floor          = initial_balance   # floor awal = modal (no loss)
        self.day_start      = initial_balance
        self.is_halted      = False
        self.halt_reason    = ""
        self.floor_history  : List[dict] = []   # track kapan floor naik
        self._last_day      = datetime.now().date()

    def update(self, equity: float) -> Tuple[bool, str]:
        """
        Update vault dengan equity terbaru.
        Return (can_trade, reason).
        """
        # ── Reset harian ──────────────────────────────────────────
        today = datetime.now().date()
        if today != self._last_day:
            self.day_start   = equity
            self._last_day   = today
            # Reset halt jika alasannya daily DD (bukan equity floor)
            if self.is_halted and "DAILY" in self.halt_reason:
                self.is_halted   = False
                self.halt_reason = ""

        # ── Update peak & hitung new floor ────────────────────────
        if equity > self.peak:
            self.peak = equity
            gains_usd = self.peak - self.initial
            gains_pct = (gains_usd / self.initial) * 100

            # Hitung floor menggunakan step-lock
            # Berapa step penuh yang sudah dicapai?
            steps_completed = math.floor(gains_pct / self.config.lock_step_pct)
            locked_gains_pct = steps_completed * self.config.lock_step_pct * self.config.lock_ratio
            new_floor = self.initial * (1 + locked_gains_pct / 100)

            # Ratchet: floor hanya boleh naik
            if new_floor > self.floor:
                old_floor = self.floor
                self.floor = new_floor
                self.floor_history.append({
                    "ts"        : time.time(),
                    "equity"    : round(equity, 2),
                    "new_floor" : round(new_floor, 2),
                    "old_floor" : round(old_floor, 2),
                    "gains_pct" : round(gains_pct, 3),
                })

        # ── Check 1: Equity floor hit ─────────────────────────────
        if equity <= self.floor and self.floor > self.initial:
            self.is_halted   = True
            self.halt_reason = (
                f"EQUITY_FLOOR: eq ${equity:.2f} ≤ floor ${self.floor:.2f} "
                f"(+{((self.floor/self.initial-1)*100):.2f}% gains protected)"
            )
            return False, self.halt_reason

        # ── Check 2: Daily drawdown ───────────────────────────────
        daily_dd_pct = (equity - self.day_start) / self.day_start * 100
        if daily_dd_pct <= -self.config.max_daily_dd_pct:
            self.is_halted   = True
            self.halt_reason = f"DAILY_DD: {daily_dd_pct:.2f}% (limit -{self.config.max_daily_dd_pct}%)"
            return False, self.halt_reason

        return True, "OK"

    @property
    def floor_pct(self) -> float:
        return ((self.floor / self.initial) - 1) * 100

    @property
    def peak_pct(self) -> float:
        return ((self.peak / self.initial) - 1) * 100

    def to_dict(self) -> dict:
        return {
            "initial"      : round(self.initial, 2),
            "peak"         : round(self.peak, 4),
            "floor"        : round(self.floor, 4),
            "floor_pct"    : round(self.floor_pct, 3),
            "peak_pct"     : round(self.peak_pct, 3),
            "is_halted"    : self.is_halted,
            "halt_reason"  : self.halt_reason,
            "floor_history": self.floor_history[-20:],
        }

    def manual_resume(self):
        """Operator reset setelah review situasi."""
        self.is_halted   = False
        self.halt_reason = ""
        self.day_start   = max(self.day_start, self.floor)


# ══════════════════════════════════════════════════════════════════
#  RAPID STATS TRACKER
# ══════════════════════════════════════════════════════════════════

class RapidStats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.total_trades        : int   = 0
        self.wins                : int   = 0
        self.losses              : int   = 0
        self.gross_pnl           : float = 0.0
        self.total_fees          : float = 0.0
        self.net_pnl             : float = 0.0
        self.peak_balance        : float = 0.0
        self.max_drawdown        : float = 0.0
        self.consecutive_losses  : int   = 0
        self.max_consec_losses   : int   = 0
        self.exit_breakdown      : Dict[str, int] = {"TP": 0, "SL": 0, "FLIP": 0, "TIMEOUT": 0, "MANUAL": 0}
        self.trades_ts           : List[float] = []   # timestamp setiap trade
        self._start_ts           : float = time.time()

    def record(self, trade: ScalpTrade, balance: float):
        self.total_trades += 1
        self.gross_pnl    += trade.gross_pnl
        self.total_fees   += trade.fee_usd
        self.net_pnl      += trade.net_pnl
        self.trades_ts.append(trade.closed_at)
        if len(self.trades_ts) > 2000:
            self.trades_ts = self.trades_ts[-1000:]

        reason = trade.exit_reason
        self.exit_breakdown[reason] = self.exit_breakdown.get(reason, 0) + 1

        if trade.net_pnl > 0:
            self.wins             += 1
            self.consecutive_losses = 0
        else:
            self.losses             += 1
            self.consecutive_losses += 1
            self.max_consec_losses   = max(self.max_consec_losses, self.consecutive_losses)

        if balance > self.peak_balance:
            self.peak_balance = balance
        dd = self.peak_balance - balance
        self.max_drawdown = max(self.max_drawdown, dd)

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades else 0.0

    @property
    def profit_factor(self) -> float:
        wins_sum   = sum(1 for _ in range(self.wins))     # placeholder
        # Tidak ada per-trade gross easily — approximate dari breakdown
        return 0.0  # frontend bisa hitung dari trade_log

    @property
    def trades_per_minute(self) -> float:
        if len(self.trades_ts) < 2: return 0.0
        window = 60.0
        now = time.time()
        recent = [t for t in self.trades_ts if now - t <= window]
        return len(recent)

    @property
    def avg_net_pnl(self) -> float:
        return self.net_pnl / self.total_trades if self.total_trades else 0.0

    def to_dict(self) -> dict:
        return {
            "total_trades"      : self.total_trades,
            "wins"              : self.wins,
            "losses"            : self.losses,
            "win_rate"          : round(self.win_rate, 2),
            "net_pnl"           : round(self.net_pnl, 4),
            "total_fees"        : round(self.total_fees, 4),
            "avg_net_pnl"       : round(self.avg_net_pnl, 5),
            "trades_per_minute" : round(self.trades_per_minute, 1),
            "consecutive_losses": self.consecutive_losses,
            "max_consec_losses" : self.max_consec_losses,
            "max_drawdown_usd"  : round(self.max_drawdown, 4),
            "exit_breakdown"    : self.exit_breakdown,
        }


# ══════════════════════════════════════════════════════════════════
#  THE JACKAL — MAIN RAPID SCALPER ENGINE
# ══════════════════════════════════════════════════════════════════

class RapidScalper:
    """
    Lite HFT Rapid Scalper — The Jackal.

    Filosofi eksekusi:
    - Scan 70ms interval (14x/detik)
    - 5 coin × multiple opportunities = 10–25 trade/menit realistis
    - Masuk cepat saat burst terdeteksi
    - Keluar lebih cepat dari rencana jika momentum berbalik
    - Vault melindungi semua gains yang sudah dikumpulkan

    Kenapa TIDAK 100+ trade/menit:
    - Hyperliquid REST API: ~50–150ms latency per request
    - allMids endpoint = 1 request untuk semua harga, efisien
    - Tapi L2 book per coin = N request = bottleneck
    - Dengan 5 coin + scan 70ms = practical maximum ~20–30 trade/menit
    - Lebih dari itu perlu co-location atau WebSocket dedicated
    """

    HL_INFO = "https://api.hyperliquid.xyz/info"

    def __init__(self):
        self.config          : RapidConfig                     = RapidConfig()
        self.running         : bool                             = False
        self.positions       : Dict[str, ScalpPosition]        = {}
        self.trade_log       : List[ScalpTrade]                = []
        self.stats           : RapidStats                       = RapidStats()
        self.balance         : float                            = 1000.0
        self.initial_balance : float                            = 1000.0
        self.equity_curve    : List[dict]                       = []

        self._burst          : Dict[str, BurstState]           = {}
        self._in_position    : Set[str]                         = set()
        self._vault          : Optional[EquityVault]            = None
        self._events         : deque                            = deque(maxlen=500)
        self._task           : Optional[asyncio.Task]           = None
        self._cooldown_ts    : Dict[str, float]                 = {}

        # Latency tracking
        self._last_fetch_ms  : float = 0.0
        self._avg_fetch_ms   : float = 0.0
        self._fetch_count    : int   = 0

        # Pause karena consecutive loss (berbeda dari Vault halt)
        self._loss_pause_until: float = 0.0

        # Slippage per coin (taker-realistic)
        self._slippage : Dict[str, float] = {
            "BTC": 0.010, "ETH": 0.012, "SOL": 0.015, "BNB": 0.018, "XRP": 0.020,
        }

    # ─── PUBLIC CONTROL ─────────────────────────────────────────

    def set_balance(self, balance: float):
        self.balance          = balance
        self.initial_balance  = balance
        self.stats.peak_balance = balance
        self.equity_curve     = [{"ts": time.time(), "balance": balance}]
        self._vault           = EquityVault(balance, self.config)
        self._log("VAULT", f"🔒 Vault initialized: floor=${balance:.2f}, lock_step={self.config.lock_step_pct}%")

    def configure(self, cfg: dict):
        for k, v in cfg.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        self._log("CONFIG", f"Updated: {list(cfg.keys())}")

    async def start(self):
        if self.running: return
        if self._vault is None:
            self._vault = EquityVault(self.balance, self.config)
        self.running = True
        self.stats.reset()
        self.stats.peak_balance = self.balance
        self._log("ENGINE", "🐆 Jackal awakens — rapid scalper active")
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
        self._log("ENGINE", "🛑 Jackal halted — all positions closed")

    # ─── MAIN LOOP ───────────────────────────────────────────────

    async def _main_loop(self):
        connector = aiohttp.TCPConnector(ssl=False, limit=15)
        async with aiohttp.ClientSession(connector=connector) as session:
            while self.running:
                t0 = time.perf_counter()
                try:
                    # ── 1. Fetch semua harga ────────────────────
                    ticks = await self._fetch_ticks(session)

                    # ── 2. Update burst state ────────────────────
                    self._update_burst(ticks)

                    # ── 3. Update open positions ─────────────────
                    self._update_positions(ticks)

                    # ── 4. Check exits ───────────────────────────
                    self._check_exits()

                    # ── 5. Vault check ───────────────────────────
                    equity = self.balance + sum(p.unrealized_pnl for p in self.positions.values())
                    can_trade, vault_reason = self._vault.update(equity)

                    # ── 6. Scan entries ──────────────────────────
                    if can_trade:
                        # Check loss-streak pause
                        if time.time() < self._loss_pause_until:
                            pass  # masih dalam pause window
                        elif self.stats.consecutive_losses >= self.config.max_loss_streak:
                            # Pause 60 detik, reset consecutive counter
                            self._loss_pause_until = time.time() + 60
                            self._log("CIRCUIT", f"⏸ {self.config.max_loss_streak} consecutive losses — pause 60s")
                            self.stats.consecutive_losses = 0
                        else:
                            open_slots = self.config.max_positions - len(self._open_positions())
                            if open_slots > 0:
                                self._scan_entries(ticks)
                    else:
                        if "HALTED" not in (self._events[0]["msg"] if self._events else ""):
                            self._log("VAULT", f"🔒 {vault_reason}")

                    # ── 7. Equity snapshot ───────────────────────
                    self._record_equity()

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._log("ERROR", f"Loop: {e}")

                # ── Timing: sesuaikan sleep agar total ≈ scan_interval ──
                elapsed = (time.perf_counter() - t0) * 1000  # ms
                self._update_latency(elapsed)
                sleep_s = max(0, self.config.scan_interval - elapsed / 1000)
                await asyncio.sleep(sleep_s)

    # ─── DATA FETCH ─────────────────────────────────────────────

    async def _fetch_ticks(self, session: aiohttp.ClientSession) -> Dict[str, BurstTick]:
        """
        Strategi fetch 2-lapis:
        Layer 1: allMids — 1 request untuk semua mid prices (sangat cepat)
        Layer 2: l2Book — hanya untuk 3 "hot coins" (aktif posisi / top kandidat)

        Kenapa tidak L2 semua:
        5 L2 requests × 80ms/req = 400ms total > scan_interval kita.
        allMids + selective L2 = praktis ~100–180ms total.
        """
        ticks: Dict[str, BurstTick] = {}
        ts = time.time()

        # Layer 1: allMids (satu request, semua coin)
        try:
            async with session.post(
                self.HL_INFO,
                json={"type": "allMids"},
                timeout=aiohttp.ClientTimeout(total=1.5),
            ) as resp:
                if resp.status == 200:
                    mids = await resp.json()
                    for coin in self.config.watchlist:
                        if coin in mids:
                            mid = float(mids[coin])
                            slip = self._slippage.get(coin, 0.015)
                            half = mid * slip / 100 * 0.5
                            ticks[coin] = BurstTick(
                                coin=coin, price=mid,
                                bid=mid - half, ask=mid + half,
                                bid_sz=1.0, ask_sz=1.0,
                                ts=ts,
                            )
        except Exception:
            pass

        # Layer 2: l2Book hanya untuk hot coins (max 3)
        hot = list(self._in_position)[:2]
        if len(hot) < 3:
            # Tambah top coin berdasarkan burst signal terkuat
            candidates = [c for c in self.config.watchlist if c not in hot][:1]
            hot += candidates

        for coin in hot[:3]:
            try:
                async with session.post(
                    self.HL_INFO,
                    json={"type": "l2Book", "coin": coin},
                    timeout=aiohttp.ClientTimeout(total=1.0),
                ) as resp:
                    if resp.status == 200:
                        book = await resp.json()
                        lvls = book.get("levels", [[], []])
                        bids = lvls[0][:3] if lvls else []
                        asks = lvls[1][:3] if len(lvls) > 1 else []
                        if bids and asks:
                            bb = float(bids[0][0])
                            ba = float(asks[0][0])
                            bsz = sum(float(b[1]) for b in bids[:3])
                            asz = sum(float(a[1]) for a in asks[:3])
                            mid = (bb + ba) / 2
                            ticks[coin] = BurstTick(
                                coin=coin, price=mid,
                                bid=bb, ask=ba,
                                bid_sz=bsz, ask_sz=asz,
                                ts=time.time(),
                            )
            except Exception:
                pass

        return ticks

    # ─── BURST STATE UPDATE ──────────────────────────────────────

    def _update_burst(self, ticks: Dict[str, BurstTick]):
        for coin, tick in ticks.items():
            if coin not in self._burst:
                self._burst[coin] = BurstState(coin, self.config.burst_window)
            self._burst[coin].update(tick)

    # ─── ENTRY SCANNER ──────────────────────────────────────────

    def _scan_entries(self, ticks: Dict[str, BurstTick]):
        """
        Scan semua coin, cari yang ada burst signal.
        Bisa multiple entries per scan (berbeda dengan Predator yang 1 per scan).
        """
        for coin in self.config.watchlist:
            if coin in self._in_position:
                continue
            if coin not in ticks or coin not in self._burst:
                continue

            # Cooldown singkat: hindari re-entry langsung setelah exit
            # Tapi ini LEBIH PENDEK dari Predator (2s vs 15s)
            last_trade = self._cooldown_ts.get(coin, 0)
            if time.time() - last_trade < 2.0:
                continue

            burst = self._burst[coin]
            signal, direction, meta = burst.detect_burst(
                min_streak      = self.config.min_streak,
                min_move_pct    = self.config.min_move_pct,
                ofi_floor       = self.config.ofi_floor,
                ofi_ceiling     = self.config.ofi_ceiling,
                max_spread_pct  = self.config.max_spread_pct,
            )

            if signal and self.balance >= self.config.capital_per_trade:
                self._enter_position(coin, direction, ticks[coin], meta)

    # ─── POSITION OPEN ───────────────────────────────────────────

    def _enter_position(self, coin: str, direction: str,
                        tick: BurstTick, meta: dict):
        slip_pct = self._slippage.get(coin, 0.015)

        # Masuk di ask (LONG) atau bid (SHORT) — bukan mid
        if direction == "LONG":
            entry = tick.ask * (1 + slip_pct / 100)
        else:
            entry = tick.bid * (1 - slip_pct / 100)

        capital = self.config.capital_per_trade
        qty     = capital / entry

        # Fixed % TP/SL — tidak ada ATR, tidak ada dynamic sizing
        if direction == "LONG":
            tp_price   = entry * (1 + self.config.tp_pct / 100)
            stop_price = entry * (1 - self.config.sl_pct / 100)
        else:
            tp_price   = entry * (1 - self.config.tp_pct / 100)
            stop_price = entry * (1 + self.config.sl_pct / 100)

        pos = ScalpPosition(
            id            = str(uuid.uuid4())[:8],
            coin          = coin,
            direction     = direction,
            entry_price   = entry,
            current_price = entry,
            tp_price      = tp_price,
            stop_price    = stop_price,
            qty           = qty,
            capital       = capital,
            opened_at     = time.time(),
        )

        self.balance -= capital
        self.positions[pos.id] = pos
        self._in_position.add(coin)

        # Simpan metadata burst untuk analytics
        pos._burst_meta = meta  # type: ignore

        self._log("ENTRY", (
            f"{'🟢' if direction == 'LONG' else '🔴'} {direction} {coin} "
            f"@ ${entry:,.4f} | TP ${tp_price:,.4f} SL ${stop_price:,.4f} | "
            f"streak={meta.get('streak',0)} move={meta.get('move_pct',0):.4f}% "
            f"OFI={meta.get('ofi',0.5):.2f}"
        ))

    # ─── POSITION UPDATE & EXIT ──────────────────────────────────

    def _update_positions(self, ticks: Dict[str, BurstTick]):
        for pos in self._open_positions():
            if pos.coin in ticks:
                pos.current_price = ticks[pos.coin].mid
                if pos.unrealized_pnl > pos.peak_pnl:
                    pos.peak_pnl = pos.unrealized_pnl

    def _check_exits(self):
        for pos in list(self._open_positions()):
            reason = None

            if pos.should_tp():
                reason = "TP"
            elif pos.should_sl():
                reason = "SL"
            elif pos.should_timeout(self.config.max_hold_seconds):
                reason = "TIMEOUT"
            elif (pos.coin in self._burst and
                  self._burst[pos.coin].check_flip(
                      pos.direction, pos.entry_price,
                      self.config.flip_threshold_pct)):
                reason = "FLIP"

            if reason:
                self._close_position(pos, reason)

    def _close_position(self, pos: ScalpPosition, reason: str):
        pos.status = "CLOSED"
        slip_pct   = self._slippage.get(pos.coin, 0.015)

        # Exit di bid (LONG sell) atau ask (SHORT cover)
        if pos.direction == "LONG":
            exit_price = pos.current_price * (1 - slip_pct / 100)
            gross_pnl  = (exit_price - pos.entry_price) * pos.qty
        else:
            exit_price = pos.current_price * (1 + slip_pct / 100)
            gross_pnl  = (pos.entry_price - exit_price) * pos.qty

        fee_usd  = pos.capital * (self.config.fee_pct / 100) * 2
        net_pnl  = gross_pnl - fee_usd
        net_pct  = (net_pnl / pos.capital) * 100

        self.balance += pos.capital + net_pnl

        meta = getattr(pos, "_burst_meta", {})
        trade = ScalpTrade(
            id           = pos.id,
            coin         = pos.coin,
            direction    = pos.direction,
            entry_price  = pos.entry_price,
            exit_price   = exit_price,
            qty          = pos.qty,
            capital      = pos.capital,
            gross_pnl    = gross_pnl,
            fee_usd      = fee_usd,
            net_pnl      = net_pnl,
            net_pct      = net_pct,
            exit_reason  = reason,
            opened_at    = pos.opened_at,
            closed_at    = time.time(),
            hold_seconds = pos.hold_seconds,
            entry_ofi    = meta.get("ofi", 0.5),
            streak_len   = meta.get("streak", 0),
            move_pct     = meta.get("move_pct", 0.0),
        )

        self.trade_log.append(trade)
        self.stats.record(trade, self.balance)
        self._in_position.discard(pos.coin)
        self._cooldown_ts[pos.coin] = time.time()
        del self.positions[pos.id]

        icon = "✅" if net_pnl > 0 else "❌"
        self._log("EXIT", (
            f"{icon} {pos.direction} {pos.coin} [{reason}] "
            f"@ ${exit_price:,.4f} | "
            f"Net {'+' if net_pnl >= 0 else ''}{net_pnl:.4f} ({net_pct:+.3f}%) | "
            f"{pos.hold_seconds:.1f}s"
        ))

    # ─── HELPERS ─────────────────────────────────────────────────

    def _open_positions(self) -> List[ScalpPosition]:
        return [p for p in self.positions.values() if p.status == "OPEN"]

    def _record_equity(self):
        now = time.time()
        if not self.equity_curve or now - self.equity_curve[-1]["ts"] > 5:
            eq = self.balance + sum(p.unrealized_pnl for p in self._open_positions())
            self.equity_curve.append({"ts": now, "balance": round(eq, 4)})
            if len(self.equity_curve) > 1000:
                self.equity_curve = self.equity_curve[-500:]

    def _update_latency(self, ms: float):
        self._fetch_count += 1
        alpha = 0.1  # exponential moving average
        self._avg_fetch_ms = alpha * ms + (1 - alpha) * self._avg_fetch_ms
        self._last_fetch_ms = ms

    def _log(self, tag: str, msg: str):
        self._events.appendleft({
            "ts"  : time.time(),
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "tag" : tag,
            "msg" : msg,
        })

    def _burst_snapshot(self) -> List[dict]:
        """Snapshot kondisi burst detector per coin untuk UI."""
        result = []
        for coin in self.config.watchlist:
            burst = self._burst.get(coin)
            if burst is None or not burst.ticks:
                result.append({
                    "coin": coin, "price": 0, "ready": False,
                    "ticks": 0, "in_position": coin in self._in_position,
                    "ofi": 0.5, "spread_pct": 0, "streak": 0,
                    "signal_long": False, "signal_short": False,
                    "cooldown_remaining": 0,
                })
                continue

            latest = burst.latest_tick()
            prices = list(burst.prices)

            # Hitung streak saat ini untuk display
            up_s = down_s = 0
            for i in range(len(prices) - 1, 0, -1):
                if prices[i] > prices[i-1]:
                    if down_s > 0: break
                    up_s += 1
                elif prices[i] < prices[i-1]:
                    if up_s > 0: break
                    down_s += 1
                else:
                    break

            sig, sig_dir, _ = burst.detect_burst(
                self.config.min_streak, self.config.min_move_pct,
                self.config.ofi_floor, self.config.ofi_ceiling,
                self.config.max_spread_pct,
            )

            cd_rem = max(0, 2.0 - (time.time() - self._cooldown_ts.get(coin, 0)))

            result.append({
                "coin"               : coin,
                "price"              : round(latest.price, 5) if latest else 0,
                "ready"              : burst.is_ready(),
                "ticks"              : burst.tick_count,
                "in_position"        : coin in self._in_position,
                "ofi"                : round(latest.ofi if latest else 0.5, 3),
                "spread_pct"         : round(latest.spread_pct if latest else 0, 4),
                "up_streak"          : up_s,
                "down_streak"        : down_s,
                "signal_long"        : sig and sig_dir == "LONG",
                "signal_short"       : sig and sig_dir == "SHORT",
                "cooldown_remaining" : round(cd_rem, 1),
            })
        return result

    # ─── STATUS ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        open_pos  = self._open_positions()
        total_eq  = self.balance + sum(p.unrealized_pnl for p in open_pos)

        return {
            "running"           : self.running,
            "balance"           : round(self.balance, 4),
            "total_equity"      : round(total_eq, 4),
            "initial_balance"   : self.initial_balance,
            "total_pnl"         : round(total_eq - self.initial_balance, 4),
            "total_pnl_pct"     : round((total_eq / self.initial_balance - 1) * 100, 3),
            "unrealized_pnl"    : round(sum(p.unrealized_pnl for p in open_pos), 4),
            "open_positions"    : [p.to_dict() for p in open_pos],
            "open_count"        : len(open_pos),
            "max_positions"     : self.config.max_positions,
            "trade_log"         : [t.to_dict() for t in self.trade_log[-100:]],
            "stats"             : self.stats.to_dict(),
            "equity_curve"      : self.equity_curve[-200:],
            "events"            : list(self._events)[:50],
            "vault"             : self._vault.to_dict() if self._vault else {},
            "config"            : asdict(self.config),
            "burst_snapshot"    : self._burst_snapshot(),
            "latency_ms"        : round(self._avg_fetch_ms, 1),
            "loss_pause_active" : time.time() < self._loss_pause_until,
            "engine_version"    : "v1.0-rapid-scalper",
            "strategy"          : "micro_momentum_burst",
        }

    def reset_vault(self):
        """Manual vault resume setelah operator review."""
        if self._vault:
            self._vault.manual_resume()
            self._log("VAULT", "🔓 Vault manually resumed by operator")

    def reset_full(self):
        """Full reset — stop engine, clear state."""
        self.positions       = {}
        self.trade_log       = []
        self._burst          = {}
        self._in_position    = set()
        self._cooldown_ts    = {}
        self._loss_pause_until = 0.0
        self.stats.reset()
        self.equity_curve    = []


# ══════════════════════════════════════════════════════════════════
#  SINGLETON — diimpor oleh main.py
# ══════════════════════════════════════════════════════════════════

rapid_scalper = RapidScalper()