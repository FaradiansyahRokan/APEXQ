"""
╔══════════════════════════════════════════════════════════════════════════════╗
║      APEX ULTRA HFT RAPID SCALPER  —  "The Jackal ULTRA" v4.0 WS          ║
║   Full WebSocket Feed · Triple Engine · Zero-Latency Tick Processing       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UPGRADE DARI v3.0 (REST polling) → v4.0 (Full WebSocket):                 ║
║                                                                              ║
║  v3.0: REST allMids polling (80–150ms per cycle)                            ║
║  v4.0: WebSocket push stream (<5ms latency, exchange-initiated)             ║
║                                                                              ║
║  ARSITEKTUR WS v4.0:                                                         ║
║                                                                              ║
║   Hyperliquid Exchange                                                       ║
║        │                                                                     ║
║   ┌────┴────────────────────────────────────────┐                           ║
║   │  WS Stream 1: allMids (semua harga, ~10ms)  │                           ║
║   │  WS Stream 2: l2Book per coin (OFI realtime)│                           ║
║   └────┬────────────────────────────────────────┘                           ║
║        │ push (exchange → kita)                                              ║
║        ▼                                                                     ║
║   WS Tick Cache (in-memory dict, always fresh)                              ║
║        │                                                                     ║
║   ┌────▼────────────────────────────────────────┐                           ║
║   │  Engine Loop (scan cache setiap 15ms)       │                           ║
║   │  Engine 1: Burst   → cooldown 0.5s          │                           ║
║   │  Engine 2: Pullback → cooldown 0.15s        │                           ║
║   │  Engine 3: Accel   → cooldown 0.30s         │                           ║
║   └────┬────────────────────────────────────────┘                           ║
║        │                                                                     ║
║   REST API (hanya untuk order execution)                                    ║
║   POST /exchange → market order                                              ║
║                                                                              ║
║  KENAPA WS JAUH LEBIH BAIK:                                                 ║
║  REST poll: kita request → tunggu → dapat data (80–150ms delay)            ║
║  WS push  : exchange kirim langsung saat ada update (<5ms delay)           ║
║  Untuk HFT, selisih 100ms itu sudah beda universe.                         ║
║                                                                              ║
║  WS SUBSCRIPTION (Hyperliquid format):                                      ║
║  {"method":"subscribe","subscription":{"type":"allMids"}}                  ║
║  {"method":"subscribe","subscription":{"type":"l2Book","coin":"BTC"}}      ║
║                                                                              ║
║  FALLBACK STRATEGY:                                                          ║
║  Jika WS disconnect → auto-reconnect dengan exponential backoff             ║
║  Jika WS down > 3s → fallback ke REST sementara                            ║
║                                                                              ║
║  REST DIPAKAI HANYA UNTUK:                                                  ║
║  • Kirim market order (POST /exchange)                                       ║
║  • Cancel order (POST /exchange)                                             ║
║  • Get account balance (POST /info)                                          ║
║                                                                              ║
║  TRIPLE ENGINE (sama seperti v3.0, tapi sekarang feed-nya real-time):      ║
║  Engine 1 — BURST       : 2 tick konsekutif → masuk                        ║
║  Engine 2 — PULLBACK    : retrace micro dalam trend → masuk                 ║
║  Engine 3 — ACCELERATION: tick makin cepat (interval menyempit) → masuk    ║
║                                                                              ║
║  TARGET v4.0 WS:                                                             ║
║  Latency feed  : <5ms (vs 80–150ms REST)                                   ║
║  Trades/menit  : 40–100 (lebih banyak karena deteksi lebih cepat)          ║
║  Win rate      : 55–60%                                                      ║
║  Avg hold      : 2–6 detik                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

─── PSEUDOCODE ARSITEKTUR WS v4.0 ─────────────────────────────────────────────

WEBSOCKET FEED (background tasks, berjalan paralel dengan engine loop):
────────────────────────────────────────────────────────────────────────
Task A: _ws_allmids_task()
  connect → wss://api.hyperliquid.xyz/ws
  subscribe {"type":"allMids"}
  on message:
    for coin, mid_price in data["mids"].items():
      if coin in watchlist:
        ws_tick_cache[coin].price = mid_price
        ws_tick_cache[coin].ts    = now()
        → trigger _on_price_update(coin)  # langsung proses, tidak tunggu loop

Task B: _ws_orderbook_task()
  connect → wss://api.hyperliquid.xyz/ws
  for each coin in hot_coins (top 10):
    subscribe {"type":"l2Book","coin":coin}
  on message:
    coin = data["coin"]
    ws_tick_cache[coin].bid    = data["levels"][0][0]
    ws_tick_cache[coin].ask    = data["levels"][1][0]
    ws_tick_cache[coin].bid_sz = data["levels"][0][1]
    ws_tick_cache[coin].ask_sz = data["levels"][1][1]

Reconnect logic:
  on disconnect: wait 0.5s → reconnect (exponential backoff max 5s)
  heartbeat ping setiap 15s (HL requirement)

ENGINE LOOP (scan WS cache setiap 15ms):
─────────────────────────────────────────
every 0.015s:
  ticks = dict(ws_tick_cache)    # snapshot cache saat ini (no network call!)
  _update_burst(ticks)
  _update_positions(ticks)
  _check_exits()
  vault.update(equity)
  if can_trade: _scan_entries(ticks)

TRIPLE ENGINE ENTRY (sama seperti v3.0):
─────────────────────────────────────────
Engine 1 (Burst):    streak ≥ 2 + move ≥ 0.003% + OFI mild gate  → MASUK
Engine 2 (Pullback): trend ≥ 2 tick + retrace kecil + OFI        → MASUK
Engine 3 (Accel):    interval tick menyempit 1.4x + move          → MASUK

REST API (hanya saat execute order):
─────────────────────────────────────
POST /exchange  → kirim market order (saat ada sinyal)
POST /exchange  → cancel order (jika perlu)
POST /info      → ambil balance (saat startup)

──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import json
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
    print("WARNING: websockets not installed. Run: pip install websockets")


# ══════════════════════════════════════════════════════════════════
#  KONSTANTA
# ══════════════════════════════════════════════════════════════════

FEE_PER_SIDE   = 0.035   # Hyperliquid taker % per side
FEE_RT         = FEE_PER_SIDE * 2   # 0.070% round-trip
SLIPPAGE_EST   = 0.015   # % slippage untuk liquid perp (BTC/ETH/SOL)

# WebSocket endpoints
HL_WS_URL      = "wss://api.hyperliquid.xyz/ws"
HL_REST_URL    = "https://api.hyperliquid.xyz/info"
HL_EXCHANGE_URL= "https://api.hyperliquid.xyz/exchange"

# WS timing
WS_PING_INTERVAL   = 15.0   # Hyperliquid requires ping every 15s
WS_RECONNECT_INIT  = 0.5    # initial reconnect delay
WS_RECONNECT_MAX   = 5.0    # max reconnect delay
WS_STALE_THRESHOLD = 3.0    # detik sebelum dianggap stale → fallback REST


# ══════════════════════════════════════════════════════════════════
#  CONFIG — RAPID SCALPER
# ══════════════════════════════════════════════════════════════════

@dataclass
class RapidConfig:
    """
    Parameter Rapid Scalper — semua bisa diubah live via /api/hft-rapid/config.

    ULTRA v3.0 — Triple Engine, Max Frequency.

    PERUBAHAN KRITIS vs v2.0:
    scan_interval 0.07→0.015s | burst_cooldown 2.0→0.5s | tp 0.07→0.04%
    sl 0.06→0.05% | max_positions 10→20 | Engine 3 BARU: AccelSpike
    max_daily_dd_pct : 2–4%
    """

    # ── Universe ─────────────────────────────────────────────────
    watchlist: List[str] = field(default_factory=lambda: [
        "BTC","ETH","SOL","BNB","XRP",
        "DOGE","ADA","AVAX","LINK","MATIC",
        "APT","ARB","OP","SUI","INJ",
        "LTC","ATOM","NEAR","FTM","FIL",
        "TRB","PEPE","WIF","BOME","MEME",
        "ONDO","ENA","AERO","BB","ZRO",
        "JUP","RAY","ORCA","JTO","PYTH",
        "DYDX","GMX","GNS","PENDLE","LQTY",
        "ENS","ZEC","MINA","ICP","TAO",
        "RNDR","FET","AGIX","OCEAN","AI",
        "SEI","BLUR","WLD","NFP","AXS",
        "FLOW","MANA","SAND","GALA","APE",
        "CRV","CVX","AAVE","MKR","COMP",
        "SNX","BAL","UNI","SUSHI","YFI",
    ])

    # ── Entry Engine 1 — Burst Detector (ULTRA) ──────────────────
    burst_window       : int   = 4      # lebih banyak history → akurasi lebih baik
    min_streak         : int   = 2      # 2 = paling agresif, sinyal terbanyak
    min_move_pct       : float = 0.003  # turun 0.005→0.003 → lebih sensitif micro-move
    ofi_floor          : float = 0.20   # sangat longgar, hanya block extreme
    ofi_ceiling        : float = 0.80   # sangat longgar
    max_spread_pct     : float = 0.25   # sedikit lebih toleran

    # ── Entry Engine 2 — Micro Pullback (ULTRA) ──────────────────
    pullback_enabled        : bool  = True
    pullback_min_trend_ticks: int   = 2
    pullback_max_pct        : float = 0.030  # sedikit lebih dalam boleh
    pullback_min_move_pct   : float = 0.003
    pullback_cooldown       : float = 0.15   # turun 0.3→0.15s → re-entry lebih cepat

    # ── Entry Engine 3 — Acceleration Spike (BARU!) ──────────────
    accel_enabled      : bool  = True    # aktifkan engine 3
    accel_window       : int   = 5       # track 5 timestamp tick terakhir
    accel_ratio        : float = 1.4     # interval harus 1.4x lebih cepat
    accel_min_move_pct : float = 0.003   # min total price move dalam accel window
    accel_cooldown     : float = 0.30    # cooldown engine 3

    # ── Multi-Position Per Coin (BARU!) ──────────────────────────
    allow_multi_pos_per_coin: bool = True  # beda engine boleh buka bersamaan
    max_pos_per_coin        : int  = 2     # max 2 posisi per coin

    # ── Exit — ULTRA Blade ────────────────────────────────────────
    tp_pct             : float = 0.04   # turun 0.07→0.04% — jauh lebih sering hit
    sl_pct             : float = 0.05   # turun 0.06→0.05% — cut loss cepat
    flip_threshold_pct : float = 0.03   # lebih sensitif 0.04→0.03%
    max_hold_seconds   : int   = 6      # turun 8→6s — timeout lebih ketat

    # ── Execution ULTRA ────────────────────────────────────────────
    scan_interval      : float = 0.015  # 15ms — 7x lebih cepat dari 0.07s (!)
    capital_per_trade  : float = 50.0   # USD per posisi
    max_positions      : int   = 20     # naik 10→20 posisi parallel
    hot_coins_l2       : int   = 6      # L2 book untuk 6 coin terpanas

    # ── Burst Cooldown Per Engine (ULTRA) ─────────────────────────
    burst_cooldown     : float = 0.50   # DRASTIS: 2.0→0.5s — 4x lebih agresif

    # ── Equity Lock (The Vault) ───────────────────────────────────
    lock_step_pct      : float = 0.30   # lebih sering lock (tiap 0.3% gain)
    lock_ratio         : float = 0.60   # kunci 60% gains
    max_daily_dd_pct   : float = 3.0    # daily hard stop
    max_loss_streak    : int   = 10     # lebih toleran sebelum pause

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
        self.prices      : deque = deque(maxlen=window + 4)
        self.ticks       : deque = deque(maxlen=window + 4)
        self.tick_count  : int   = 0
        self.last_signal : float = 0.0
        # Engine 3: track tick arrival timestamps untuk acceleration detection
        self.tick_ts     : deque = deque(maxlen=10)  # timestamp setiap tick masuk

    def update(self, tick: BurstTick):
        self.prices.append(tick.price)
        self.ticks.append(tick)
        self.tick_ts.append(tick.ts)   # catat timestamp untuk accel engine
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

    def detect_pullback(self, min_trend_ticks: int, pullback_max_pct: float,
                        min_move_pct: float, max_spread_pct: float
                        ) -> Tuple[bool, str, dict]:
        """
        Micro Pullback Engine — entry saat retrace kecil dalam trend yang masih aktif.

        Logika:
        ──────
        1. Cek ada trend UP atau DOWN dalam N tick terakhir
           (minimal min_trend_ticks tick majority satu arah)
        2. Cek apakah tick TERAKHIR adalah pullback kecil:
           - Trend UP: harga sedikit turun dari prev tapi trend masih aktif
           - Trend DOWN: harga sedikit naik dari prev tapi trend masih aktif
        3. Pullback dalam batas pullback_max_pct → sinyal valid

        Kenapa ini menambah trade frequency:
        Burst butuh streak konsekutif murni (jarang).
        Pullback menangkap retrace pendek setelah trend terbentuk (lebih sering).
        Bersama-sama = 2–3x lebih banyak sinyal valid.
        """
        if len(self.prices) < min_trend_ticks + 2:
            return False, "", {}

        last_tick = self.ticks[-1]

        # Spread guard
        if last_tick.spread_pct > max_spread_pct:
            return False, "", {"blocked": "spread"}

        prices = list(self.prices)

        # Hitung majority trend dalam N tick sebelum yang paling akhir
        trend_window = prices[-(min_trend_ticks + 2):-1]
        if len(trend_window) < 2:
            return False, "", {}

        up_ticks   = sum(1 for i in range(1, len(trend_window)) if trend_window[i] > trend_window[i-1])
        down_ticks = sum(1 for i in range(1, len(trend_window)) if trend_window[i] < trend_window[i-1])

        if up_ticks < min_trend_ticks and down_ticks < min_trend_ticks:
            return False, "", {"up": up_ticks, "dn": down_ticks, "need": min_trend_ticks}

        trend_dir = "UP" if up_ticks >= down_ticks else "DOWN"

        # Cek prior move (trend harus cukup kuat)
        prior_start = trend_window[0]
        prior_end   = trend_window[-1]
        if prior_start == 0:
            return False, "", {}
        prior_move_pct = abs(prior_end - prior_start) / prior_start * 100
        if prior_move_pct < min_move_pct:
            return False, "", {"prior_move": prior_move_pct, "needed": min_move_pct}

        # Cek pullback di tick terakhir
        current = prices[-1]
        prev    = prices[-2]

        if trend_dir == "UP":
            if current >= prev:
                return False, "", {}         # bukan pullback
            pullback_pct = (prev - current) / prev * 100
            if pullback_pct > pullback_max_pct:
                return False, "", {"pullback_too_deep": pullback_pct}
            direction = "LONG"
        else:
            if current <= prev:
                return False, "", {}         # bukan bounce
            pullback_pct = (current - prev) / prev * 100
            if pullback_pct > pullback_max_pct:
                return False, "", {"bounce_too_big": pullback_pct}
            direction = "SHORT"

        # OFI cek sangat longgar (hanya block extreme)
        ofi = last_tick.ofi
        if direction == "LONG"  and ofi < 0.20:
            return False, "", {"blocked": "ofi_extreme_short"}
        if direction == "SHORT" and ofi > 0.80:
            return False, "", {"blocked": "ofi_extreme_long"}

        meta = {
            "streak"       : up_ticks if trend_dir == "UP" else down_ticks,
            "move_pct"     : round(prior_move_pct, 5),
            "pullback_pct" : round(pullback_pct, 5),
            "ofi"          : round(ofi, 3),
            "spread_pct"   : round(last_tick.spread_pct, 4),
            "engine"       : "pullback",
        }
        return True, direction, meta

    def detect_acceleration(
        self,
        accel_window    : int   = 5,
        accel_ratio     : float = 1.4,
        min_move_pct    : float = 0.003,
        max_spread_pct  : float = 0.25,
    ) -> Tuple[bool, str, dict]:
        """
        ENGINE 3 — Acceleration Spike Detector (BARU di v3.0 ULTRA).

        Filosofi:
        ─────────
        Institutional HFT mendeteksi "order flow acceleration" — bukan hanya arah,
        tapi KECEPATAN masuknya order. Jika tick-tick datang makin cepat (interval
        antar tick menyempit), artinya ada market participant besar yang agresif.

        Cara kerja:
        ───────────
        1. Track timestamp setiap tick yang masuk ke dalam deque
        2. Hitung interval antar tick: [t1-t0, t2-t1, t3-t2, ...]
        3. Jika interval[-3] > interval[-2] > interval[-1] dengan rasio ≥ accel_ratio:
           → tick makin cepat datang = ada momentum burst yang sedang terbentuk
        4. Cek total price move dalam window tsb minimal min_move_pct
        5. Arah: net price move (positive = LONG, negative = SHORT)

        Contoh konkret:
        ───────────────
        tick ts: [0.000, 0.080, 0.140, 0.180, 0.205]  ← makin sempit!
        interval:         [80ms, 60ms, 40ms, 25ms]
        ratio = 80/25 = 3.2x → jauh di atas accel_ratio 1.4 → SINYAL VALID

        Kenapa ini menambah edge:
        Engine 1 (burst) deteksi streak harga konsekutif.
        Engine 3 (accel) deteksi kecepatan — bisa masuk SEBELUM streak terbentuk penuh.
        Keduanya komplementer, bukan duplikat.
        """
        if len(self.tick_ts) < accel_window:
            return False, "", {"ready": False, "have": len(self.tick_ts)}

        if len(self.prices) < accel_window:
            return False, "", {}

        last_tick = self.ticks[-1]
        if last_tick.spread_pct > max_spread_pct:
            return False, "", {"blocked": "spread"}

        # Ambil N timestamp terakhir dan hitung intervals
        ts_list   = list(self.tick_ts)[-accel_window:]
        intervals = [ts_list[i] - ts_list[i-1] for i in range(1, len(ts_list))]

        if len(intervals) < 3:
            return False, "", {}

        # Filter zero-interval (tick datang hampir bersamaan — latency artifact)
        intervals = [max(iv, 0.001) for iv in intervals]

        # Cek apakah intervals menyempit secara konsisten
        # Kita cek 3 interval terakhir: [-3] > [-2] > [-1]
        iv_old  = intervals[-3]
        iv_mid  = intervals[-2]
        iv_new  = intervals[-1]

        is_accelerating = (iv_old > iv_mid > iv_new)
        if not is_accelerating:
            return False, "", {"iv_old": iv_old, "iv_mid": iv_mid, "iv_new": iv_new}

        # Cek rasio: interval lama harus ≥ accel_ratio × interval baru
        ratio = iv_old / iv_new
        if ratio < accel_ratio:
            return False, "", {"ratio": ratio, "needed": accel_ratio}

        # Cek total price move dalam window
        prices      = list(self.prices)[-accel_window:]
        price_start = prices[0]
        price_end   = prices[-1]
        if price_start == 0:
            return False, "", {}

        move_pct = (price_end - price_start) / price_start * 100
        if abs(move_pct) < min_move_pct:
            return False, "", {"move_pct": abs(move_pct), "needed": min_move_pct}

        direction = "LONG" if move_pct > 0 else "SHORT"

        # OFI ultra-longgar (hanya block benar-benar ekstrem)
        ofi = last_tick.ofi
        if direction == "LONG"  and ofi < 0.15:
            return False, "", {"blocked": "ofi_extreme"}
        if direction == "SHORT" and ofi > 0.85:
            return False, "", {"blocked": "ofi_extreme"}

        meta = {
            "streak"    : 0,
            "move_pct"  : round(abs(move_pct), 5),
            "ofi"       : round(ofi, 3),
            "spread_pct": round(last_tick.spread_pct, 4),
            "accel_ratio": round(ratio, 2),
            "iv_ms"     : round(iv_new * 1000, 1),   # interval terbaru dalam ms
            "engine"    : "accel",
        }
        return True, direction, meta

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
#  WS FEED MANAGER — Real-time Market Data via WebSocket
# ══════════════════════════════════════════════════════════════════

class WSFeedManager:
    """
    WebSocket Market Feed — pengganti REST polling.

    CARA KERJA:
    ───────────
    Mengelola 2 WebSocket connection ke Hyperliquid secara bersamaan:

    Connection 1: allMids stream
      → Terima update harga SEMUA coin setiap kali ada perubahan
      → Update ws_cache[coin].price + timestamp
      → Latency: <5ms dari exchange (vs 80-150ms REST)

    Connection 2: l2Book stream (orderbook)
      → Subscribe ke top-N coin (hot coins) untuk data bid/ask/size
      → Update ws_cache[coin].bid, .ask, .bid_sz, .ask_sz
      → Digunakan untuk OFI calculation real-time

    RECONNECT LOGIC:
    ────────────────
    Auto-reconnect dengan exponential backoff:
      - Attempt 1: tunggu 0.5s
      - Attempt 2: tunggu 1.0s
      - Attempt 3: tunggu 2.0s
      - ...max: 5.0s

    Jika WS stale > WS_STALE_THRESHOLD detik:
      - Engine akan fallback ke REST untuk sementara
      - Reconnect tetap dicoba di background

    HEARTBEAT:
    ──────────
    Hyperliquid membutuhkan ping setiap 15 detik.
    Jika tidak, server akan close connection.
    WSFeedManager handle ini secara otomatis.
    """

    def __init__(self, watchlist: List[str], hot_coins_count: int = 10):
        self.watchlist        = watchlist
        self.hot_coins_count  = hot_coins_count

        # Shared tick cache — diupdate oleh WS, dibaca oleh engine loop
        # Key: coin str, Value: BurstTick
        self.cache            : Dict[str, BurstTick] = {}
        self._cache_ts        : Dict[str, float]     = {}  # last update time per coin

        # Connection state
        self._allmids_task    : Optional[asyncio.Task] = None
        self._orderbook_task  : Optional[asyncio.Task] = None
        self._running         : bool = False

        # Stats
        self.msg_count        : int   = 0
        self.reconnect_count  : int   = 0
        self._last_allmids_ts : float = 0.0
        self._last_book_ts    : float = 0.0

        # Callback untuk saat harga diupdate (opsional, untuk event-driven trigger)
        self._on_price_cb     = None

        # Hot coins list (bisa diupdate dinamis)
        self._hot_coins       : List[str] = watchlist[:hot_coins_count]

    def set_price_callback(self, cb):
        """Register callback yang dipanggil setiap ada update harga."""
        self._on_price_cb = cb

    def update_hot_coins(self, coins: List[str]):
        """Update daftar hot coins untuk orderbook subscription."""
        self._hot_coins = coins[:self.hot_coins_count]

    def is_fresh(self, coin: str) -> bool:
        """Cek apakah data coin masih fresh (< WS_STALE_THRESHOLD detik)."""
        last = self._cache_ts.get(coin, 0)
        return (time.time() - last) < WS_STALE_THRESHOLD

    def get_tick(self, coin: str) -> Optional[BurstTick]:
        """Get tick terbaru untuk coin. Return None jika stale."""
        if not self.is_fresh(coin):
            return None
        return self.cache.get(coin)

    def snapshot(self, watchlist: List[str]) -> Dict[str, BurstTick]:
        """
        Ambil snapshot semua tick saat ini dari cache.
        Tidak ada network call — langsung dari memory.
        Ini yang membuat WS jauh lebih cepat dari REST poll.
        """
        now = time.time()
        result = {}
        for coin in watchlist:
            tick = self.cache.get(coin)
            if tick and (now - self._cache_ts.get(coin, 0)) < WS_STALE_THRESHOLD:
                result[coin] = tick
        return result

    @property
    def allmids_age_ms(self) -> float:
        """Berapa ms sejak allMids terakhir diterima."""
        return (time.time() - self._last_allmids_ts) * 1000 if self._last_allmids_ts else 9999

    @property
    def orderbook_age_ms(self) -> float:
        """Berapa ms sejak orderbook update terakhir."""
        return (time.time() - self._last_book_ts) * 1000 if self._last_book_ts else 9999

    async def start(self):
        """Start kedua WS tasks secara parallel."""
        self._running = True
        self._allmids_task   = asyncio.create_task(self._allmids_loop())
        self._orderbook_task = asyncio.create_task(self._orderbook_loop())

    async def stop(self):
        """Stop semua WS connections."""
        self._running = False
        for task in [self._allmids_task, self._orderbook_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # ─── WS CONNECTION 1: allMids ────────────────────────────────

    async def _allmids_loop(self):
        """
        WebSocket loop untuk allMids stream.
        Auto-reconnect dengan exponential backoff.
        """
        backoff = WS_RECONNECT_INIT
        while self._running:
            try:
                async with websockets.connect(
                    HL_WS_URL,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    backoff = WS_RECONNECT_INIT  # reset on success
                    # Subscribe allMids
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "allMids"}
                    }))

                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                            self._handle_allmids(msg)
                        except asyncio.TimeoutError:
                            # Kirim ping manual jika tidak ada msg > 20s
                            await ws.ping()

            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                self.reconnect_count += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, WS_RECONNECT_MAX)

    def _handle_allmids(self, raw: str):
        """
        Parse allMids message dan update cache.

        Format pesan dari Hyperliquid:
        {"channel":"allMids","data":{"mids":{"BTC":"67234.5","ETH":"3521.2",...}}}
        """
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "allMids":
                return
            mids = msg.get("data", {}).get("mids", {})
            now  = time.time()
            self._last_allmids_ts = now
            self.msg_count += 1

            for coin, mid_str in mids.items():
                if coin not in self.watchlist:
                    continue
                try:
                    mid = float(mid_str)
                except (ValueError, TypeError):
                    continue

                existing = self.cache.get(coin)
                if existing:
                    # Update harga, pertahankan bid/ask/size dari orderbook WS
                    existing.price = mid
                    existing.ts    = now
                    # Jika belum ada orderbook data, estimasi dari mid
                    if existing.bid <= 0:
                        slip = 0.010
                        existing.bid = mid * (1 - slip / 100)
                        existing.ask = mid * (1 + slip / 100)
                else:
                    # Buat tick baru dengan estimasi spread
                    slip = 0.010   # default 0.010% half-spread estimate
                    self.cache[coin] = BurstTick(
                        coin   = coin,
                        price  = mid,
                        bid    = mid * (1 - slip / 100),
                        ask    = mid * (1 + slip / 100),
                        bid_sz = 1.0,
                        ask_sz = 1.0,
                        ts     = now,
                    )
                self._cache_ts[coin] = now

                # Trigger callback jika ada (event-driven)
                if self._on_price_cb:
                    try:
                        self._on_price_cb(coin, self.cache[coin])
                    except Exception:
                        pass

        except Exception:
            pass

    # ─── WS CONNECTION 2: l2Book (Orderbook) ─────────────────────

    async def _orderbook_loop(self):
        """
        WebSocket loop untuk l2Book stream.
        Subscribe ke hot coins untuk data bid/ask/OFI real-time.
        """
        backoff = WS_RECONNECT_INIT
        while self._running:
            try:
                async with websockets.connect(
                    HL_WS_URL,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    backoff = WS_RECONNECT_INIT
                    # Subscribe l2Book untuk setiap hot coin
                    for coin in self._hot_coins:
                        await ws.send(json.dumps({
                            "method": "subscribe",
                            "subscription": {"type": "l2Book", "coin": coin}
                        }))
                        await asyncio.sleep(0.02)  # stagger subscriptions

                    while self._running:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=20.0)
                            self._handle_orderbook(msg)
                        except asyncio.TimeoutError:
                            await ws.ping()

            except asyncio.CancelledError:
                break
            except Exception:
                if not self._running:
                    break
                self.reconnect_count += 1
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, WS_RECONNECT_MAX)

    def _handle_orderbook(self, raw: str):
        """
        Parse l2Book message dan update OFI data di cache.

        Format pesan dari Hyperliquid:
        {"channel":"l2Book","data":{"coin":"BTC","levels":[[["67234","10.5",...],[...]]]}
        Atau format alternatif: {"coin":"BTC","levels":{"bids":[...],"asks":[...]}}
        """
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "l2Book":
                return
            data = msg.get("data", {})
            coin = data.get("coin", "")
            if not coin or coin not in self.watchlist:
                return

            lvls = data.get("levels", [])
            # Hyperliquid format: levels = [[bids...], [asks...]]
            # Each level: [price_str, size_str, ...]
            bids = lvls[0][:5] if len(lvls) > 0 else []
            asks = lvls[1][:5] if len(lvls) > 1 else []

            if not bids or not asks:
                return

            bb  = float(bids[0][0])   # best bid price
            ba  = float(asks[0][0])   # best ask price
            bsz = sum(float(b[1]) for b in bids[:3])
            asz = sum(float(a[1]) for a in asks[:3])
            mid = (bb + ba) / 2
            now = time.time()
            self._last_book_ts = now

            existing = self.cache.get(coin)
            if existing:
                existing.bid    = bb
                existing.ask    = ba
                existing.bid_sz = bsz
                existing.ask_sz = asz
                existing.price  = mid
                existing.ts     = now
            else:
                self.cache[coin] = BurstTick(
                    coin=coin, price=mid,
                    bid=bb, ask=ba,
                    bid_sz=bsz, ask_sz=asz,
                    ts=now,
                )
            self._cache_ts[coin] = now

        except Exception:
            pass

    def to_dict(self) -> dict:
        return {
            "msg_count"       : self.msg_count,
            "reconnect_count" : self.reconnect_count,
            "allmids_age_ms"  : round(self.allmids_age_ms, 1),
            "orderbook_age_ms": round(self.orderbook_age_ms, 1),
            "cached_coins"    : len(self.cache),
            "hot_coins"       : self._hot_coins,
            "ws_available"    : HAS_WS,
        }


# ══════════════════════════════════════════════════════════════════
#  THE JACKAL — MAIN RAPID SCALPER ENGINE
# ══════════════════════════════════════════════════════════════════

class RapidScalper:
    """
    Lite HFT Rapid Scalper — The Jackal ULTRA v4.0 WS.

    Filosofi eksekusi v4.0:
    ─────────────────────────
    - WebSocket feed: harga push dari exchange (<5ms latency)
    - Engine loop scan WS cache setiap 15ms (bukan request setiap 15ms)
    - REST hanya untuk: kirim order, cancel, ambil balance
    - Triple engine entry: burst + pullback + acceleration
    - Multi-position per coin (beda engine bisa concurrent)
    - Vault protect gains dengan ratchet floor

    Flow:
    ─────
    WSFeedManager (background)        Engine Loop (15ms cycle)
    ─────────────────────────         ──────────────────────────
    WS allMids → cache.price    →     snapshot(cache)
    WS l2Book  → cache.bid/ask  →     burst.update(tick)
                                      check_exits()
                                      scan_entries() → REST order
    """

    HL_INFO     = HL_REST_URL
    HL_EXCHANGE = HL_EXCHANGE_URL

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

        # ── WebSocket Feed Manager (v4.0 NEW) ────────────────────
        self._ws_feed        : Optional[WSFeedManager]          = None
        self._ws_task        : Optional[asyncio.Task]           = None
        self._fallback_session: Optional[aiohttp.ClientSession] = None

        # Latency tracking
        self._last_fetch_ms  : float = 0.0
        self._avg_fetch_ms   : float = 0.0
        self._fetch_count    : int   = 0

        # Pause karena consecutive loss
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

        # ── Inisialisasi WS Feed Manager ─────────────────────────
        if HAS_WS:
            hot_coins = self.config.watchlist[:self.config.hot_coins_l2]
            self._ws_feed = WSFeedManager(
                watchlist       = self.config.watchlist,
                hot_coins_count = self.config.hot_coins_l2,
            )
            await self._ws_feed.start()
            self._log("FEED", f"🌐 WebSocket feed started — {len(self.config.watchlist)} coins, {self.config.hot_coins_l2} with L2 orderbook")
            # Tunggu sebentar agar cache terisi sebelum trading
            await asyncio.sleep(0.5)
        else:
            self._log("FEED", "⚠️ websockets not installed — using REST fallback (slower)")

        self._log("ENGINE", "🐆 Jackal ULTRA v4.0 awakens — WS-powered HFT active")
        self._task = asyncio.create_task(self._main_loop())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Stop WS feed
        if self._ws_feed:
            await self._ws_feed.stop()
            self._ws_feed = None
        # Close fallback session
        if self._fallback_session and not self._fallback_session.closed:
            await self._fallback_session.close()
        for pos in list(self.positions.values()):
            if pos.status == "OPEN":
                self._close_position(pos, "MANUAL")
        self._log("ENGINE", "🛑 Jackal ULTRA halted — all positions closed")

    # ─── MAIN LOOP (WS-powered) ──────────────────────────────────

    async def _main_loop(self):
        """
        Engine loop v4.0 — scan WS cache setiap 15ms.

        PERBEDAAN FUNDAMENTAL dari v3.0:
        ────────────────────────────────
        v3.0: setiap loop iteration → REST HTTP request → tunggu 80-150ms response
        v4.0: setiap loop iteration → snapshot WS memory cache → proses < 1ms

        Karena WS push data ke cache di background, engine loop
        tidak perlu menunggu network. Loop bisa berjalan murni di 15ms.
        """
        connector = aiohttp.TCPConnector(ssl=False, limit=20)
        async with aiohttp.ClientSession(connector=connector) as session:
            self._fallback_session = session

            while self.running:
                t0 = time.perf_counter()
                try:
                    # ── 1. Ambil ticks dari WS cache (no network!) ──
                    ticks = await self._get_ticks(session)

                    if not ticks:
                        await asyncio.sleep(0.005)
                        continue

                    # ── 2. Update burst state ────────────────────────
                    self._update_burst(ticks)

                    # ── 3. Update open positions ─────────────────────
                    self._update_positions(ticks)

                    # ── 4. Check exits ───────────────────────────────
                    self._check_exits()

                    # ── 5. Vault check ───────────────────────────────
                    equity = self.balance + sum(p.unrealized_pnl for p in self.positions.values())
                    can_trade, vault_reason = self._vault.update(equity)

                    # ── 6. Scan entries ──────────────────────────────
                    if can_trade:
                        if time.time() < self._loss_pause_until:
                            pass
                        elif self.stats.consecutive_losses >= self.config.max_loss_streak:
                            self._loss_pause_until = time.time() + 60
                            self._log("CIRCUIT", f"⏸ {self.config.max_loss_streak} losses beruntun — pause 60s")
                            self.stats.consecutive_losses = 0
                        else:
                            open_slots = self.config.max_positions - len(self._open_positions())
                            if open_slots > 0:
                                self._scan_entries(ticks)
                    else:
                        if "HALTED" not in (self._events[0]["msg"] if self._events else ""):
                            self._log("VAULT", f"🔒 {vault_reason}")

                    # ── 7. Update hot coins untuk WS orderbook ───────
                    if self._ws_feed and self._fetch_count % 50 == 0:
                        active_coins = list(self._in_position)
                        candidates   = [c for c in self.config.watchlist if c not in active_coins]
                        new_hot      = (active_coins + candidates)[:self.config.hot_coins_l2]
                        self._ws_feed.update_hot_coins(new_hot)

                    # ── 8. Equity snapshot ───────────────────────────
                    self._record_equity()

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self._log("ERROR", f"Loop: {e}")

                # Timing — WS mode: loop overhead ~0.1ms, sleep 14.9ms
                # REST mode: loop overhead 80-150ms, sleep minimal
                elapsed = (time.perf_counter() - t0) * 1000
                self._update_latency(elapsed)
                sleep_s = max(0.001, self.config.scan_interval - elapsed / 1000)
                await asyncio.sleep(sleep_s)

    # ─── TICK DATA — WS CACHE + REST FALLBACK ────────────────────

    async def _get_ticks(self, session: aiohttp.ClientSession) -> Dict[str, BurstTick]:
        """
        Abstraksi feed — ambil ticks dari sumber terbaik.

        Priority 1: WS cache (zero latency, preferred)
        Priority 2: REST fallback (jika WS tidak tersedia)

        Engine loop tidak perlu tahu dari mana data datang.
        Ini adalah pattern yang dipakai di HFT systems nyata:
        feed abstraction layer yang transparan ke strategy layer.
        """
        if self._ws_feed is not None:
            ticks = self._ws_feed.snapshot(self.config.watchlist)
            if ticks:
                if self._fetch_count % 200 == 0:
                    self._log("FEED", (
                        f"📡 WS: {len(ticks)} coins | "
                        f"allMids {self._ws_feed.allmids_age_ms:.0f}ms | "
                        f"book {self._ws_feed.orderbook_age_ms:.0f}ms | "
                        f"msgs {self._ws_feed.msg_count}"
                    ))
                return ticks
            self._log("FEED", "⚠️ WS stale — REST fallback")

        return await self._fetch_ticks_rest(session)

    async def _fetch_ticks_rest(self, session: aiohttp.ClientSession) -> Dict[str, BurstTick]:
        """
        REST fallback feed — dipakai jika WS tidak tersedia / stale.
        Concurrent l2Book fetch menggunakan asyncio.gather.
        """
        ticks: Dict[str, BurstTick] = {}
        ts = time.time()

        try:
            async with session.post(
                self.HL_INFO,
                json={"type": "allMids"},
                timeout=aiohttp.ClientTimeout(total=2.0),
            ) as resp:
                if resp.status == 200:
                    mids = await resp.json()
                    for coin in self.config.watchlist:
                        if coin in mids:
                            mid  = float(mids[coin])
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

        hot = list(self._in_position)[:4]
        if len(hot) < self.config.hot_coins_l2:
            candidates = [c for c in self.config.watchlist if c not in hot]
            hot += candidates[:(self.config.hot_coins_l2 - len(hot))]
        hot = hot[:self.config.hot_coins_l2]

        async def _fetch_l2(coin: str):
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
                            bb  = float(bids[0][0])
                            ba  = float(asks[0][0])
                            bsz = sum(float(b[1]) for b in bids[:3])
                            asz = sum(float(a[1]) for a in asks[:3])
                            return coin, BurstTick(
                                coin=coin, price=(bb+ba)/2,
                                bid=bb, ask=ba,
                                bid_sz=bsz, ask_sz=asz,
                                ts=time.time(),
                            )
            except Exception:
                pass
            return coin, None

        results = await asyncio.gather(*[_fetch_l2(c) for c in hot])
        for coin, tick in results:
            if tick is not None:
                ticks[coin] = tick

        return ticks

    # ─── BURST STATE UPDATE ──────────────────────────────────────

    def _update_burst(self, ticks: Dict[str, BurstTick]):
        for coin, tick in ticks.items():
            if coin not in self._burst:
                self._burst[coin] = BurstState(coin, self.config.burst_window)
            self._burst[coin].update(tick)

    # ─── ENTRY SCANNER ULTRA ────────────────────────────────────

    def _scan_entries(self, ticks: Dict[str, BurstTick]):
        """
        ULTRA Triple-Engine entry scanner — Burst + Pullback + Acceleration.

        PERUBAHAN vs v2.0:
        ─────────────────
        • Engine 3 BARU: AccelSpike — masuk berdasarkan kecepatan tick
        • Multi-pos per coin: Engine berbeda boleh buka bersamaan (max_pos_per_coin=2)
        • burst_cooldown: 2.0s → 0.5s (4x lebih agresif)
        • pullback_cooldown: 0.3s → 0.15s

        Logic per coin:
        1. Cek berapa posisi sudah open untuk coin ini
        2. Jika < max_pos_per_coin: lanjut scan semua engine
        3. Tiap engine punya cooldown sendiri (independent)
        4. Tidak pakai `continue` setelah masuk (kecuali sudah penuh)
        """
        now = time.time()
        for coin in self.config.watchlist:
            if coin not in ticks or coin not in self._burst:
                continue

            burst = self._burst[coin]

            # Hitung posisi aktif untuk coin ini
            coin_pos_count = sum(
                1 for p in self._open_positions() if p.coin == coin
            )

            # Jika single-pos mode ATAU sudah penuh
            if not self.config.allow_multi_pos_per_coin:
                if coin in self._in_position:
                    continue
            else:
                if coin_pos_count >= self.config.max_pos_per_coin:
                    continue

            if self.balance < self.config.capital_per_trade:
                break  # balance habis, stop scan

            # ── ENGINE 1: Burst ──────────────────────────────────────────────
            burst_cd = self._cooldown_ts.get(coin + "_burst", 0)
            if now - burst_cd >= self.config.burst_cooldown:
                signal, direction, meta = burst.detect_burst(
                    min_streak     = self.config.min_streak,
                    min_move_pct   = self.config.min_move_pct,
                    ofi_floor      = self.config.ofi_floor,
                    ofi_ceiling    = self.config.ofi_ceiling,
                    max_spread_pct = self.config.max_spread_pct,
                )
                if signal and self.balance >= self.config.capital_per_trade:
                    meta["engine"] = "burst"
                    self._enter_position(coin, direction, ticks[coin], meta)
                    coin_pos_count += 1
                    if coin_pos_count >= self.config.max_pos_per_coin:
                        continue

            # ── ENGINE 2: Micro Pullback ─────────────────────────────────────
            if self.config.pullback_enabled:
                pb_cd = self._cooldown_ts.get(coin + "_pullback", 0)
                if now - pb_cd >= self.config.pullback_cooldown:
                    signal, direction, meta = burst.detect_pullback(
                        min_trend_ticks = self.config.pullback_min_trend_ticks,
                        pullback_max_pct= self.config.pullback_max_pct,
                        min_move_pct    = self.config.pullback_min_move_pct,
                        max_spread_pct  = self.config.max_spread_pct,
                    )
                    if signal and self.balance >= self.config.capital_per_trade:
                        self._enter_position(coin, direction, ticks[coin], meta)
                        coin_pos_count += 1
                        if coin_pos_count >= self.config.max_pos_per_coin:
                            continue

            # ── ENGINE 3: Acceleration Spike (BARU! v3.0 ULTRA) ─────────────
            if self.config.accel_enabled:
                accel_cd = self._cooldown_ts.get(coin + "_accel", 0)
                if now - accel_cd >= self.config.accel_cooldown:
                    signal, direction, meta = burst.detect_acceleration(
                        accel_window   = self.config.accel_window,
                        accel_ratio    = self.config.accel_ratio,
                        min_move_pct   = self.config.accel_min_move_pct,
                        max_spread_pct = self.config.max_spread_pct,
                    )
                    if signal and self.balance >= self.config.capital_per_trade:
                        self._enter_position(coin, direction, ticks[coin], meta)
                        coin_pos_count += 1

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
        pos._engine     = meta.get("engine", "burst")  # type: ignore

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

        # Multi-pos support: hanya discard _in_position jika tidak ada posisi lain untuk coin ini
        remaining_open = [
            p for p in self.positions.values()
            if p.status == "OPEN" and p.coin == pos.coin and p.id != pos.id
        ]
        if not remaining_open:
            self._in_position.discard(pos.coin)

        # Track cooldown per engine (independent per engine, bukan per coin global)
        engine_key = pos.coin + "_" + getattr(pos, "_engine", "burst")
        self._cooldown_ts[engine_key] = time.time()
        # Legacy global key (hanya dipakai jika single-pos mode)
        if not self.config.allow_multi_pos_per_coin:
            self._cooldown_ts[pos.coin] = time.time()
        del self.positions[pos.id]

        icon = "✅" if net_pnl > 0 else "❌"
        engine_tag = getattr(pos, "_engine", "burst").upper()
        self._log("EXIT", (
            f"{icon} {pos.direction} {pos.coin} [{reason}][{engine_tag}] "
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

            cd_rem = max(0, self.config.burst_cooldown - (time.time() - self._cooldown_ts.get(coin, 0)))

            # Pullback signal check untuk snapshot
            pb_sig, pb_dir, _ = burst.detect_pullback(
                min_trend_ticks  = self.config.pullback_min_trend_ticks,
                pullback_max_pct = self.config.pullback_max_pct,
                min_move_pct     = self.config.pullback_min_move_pct,
                max_spread_pct   = self.config.max_spread_pct,
            ) if self.config.pullback_enabled else (False, "", {})

            # Engine 3: Acceleration signal check untuk snapshot
            ac_sig, ac_dir, ac_meta = burst.detect_acceleration(
                accel_window   = self.config.accel_window,
                accel_ratio    = self.config.accel_ratio,
                min_move_pct   = self.config.accel_min_move_pct,
                max_spread_pct = self.config.max_spread_pct,
            ) if self.config.accel_enabled else (False, "", {})

            # Active engine cooldowns
            now_ts    = time.time()
            burst_cd  = now_ts - self._cooldown_ts.get(coin + "_burst", 0)
            pb_cd     = now_ts - self._cooldown_ts.get(coin + "_pullback", 0)
            accel_cd  = now_ts - self._cooldown_ts.get(coin + "_accel", 0)

            # Count active positions for this coin
            coin_pos_count = sum(1 for p in self._open_positions() if p.coin == coin)

            result.append({
                "coin"                 : coin,
                "price"                : round(latest.price, 5) if latest else 0,
                "ready"                : burst.is_ready(),
                "ticks"                : burst.tick_count,
                "in_position"          : coin in self._in_position,
                "coin_pos_count"       : coin_pos_count,
                "ofi"                  : round(latest.ofi if latest else 0.5, 3),
                "spread_pct"           : round(latest.spread_pct if latest else 0, 4),
                "up_streak"            : up_s,
                "down_streak"          : down_s,
                # Engine 1
                "signal_long"          : sig and sig_dir == "LONG",
                "signal_short"         : sig and sig_dir == "SHORT",
                # Engine 2
                "pb_signal_long"       : pb_sig and pb_dir == "LONG",
                "pb_signal_short"      : pb_sig and pb_dir == "SHORT",
                # Engine 3 (BARU)
                "ac_signal_long"       : ac_sig and ac_dir == "LONG",
                "ac_signal_short"      : ac_sig and ac_dir == "SHORT",
                "ac_ratio"             : round(ac_meta.get("accel_ratio", 0), 2),
                "ac_iv_ms"             : round(ac_meta.get("iv_ms", 0), 1),
                # Cooldowns
                "cooldown_remaining"   : round(cd_rem, 2),
                "burst_cd_remaining"   : round(max(0, self.config.burst_cooldown - burst_cd), 2),
                "pullback_cd_remaining": round(max(0, self.config.pullback_cooldown - pb_cd), 2),
                "accel_cd_remaining"   : round(max(0, self.config.accel_cooldown - accel_cd), 2),
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
            "engine_version"    : "v4.0-ws-triple-engine",
            "strategy"          : "ws_burst+pullback+accel",
            "ws_feed"           : self._ws_feed.to_dict() if self._ws_feed else {"ws_available": HAS_WS, "active": False},
        }

    def reset_vault(self):
        """Manual vault resume setelah operator review."""
        if self._vault:
            self._vault.manual_resume()
            self._log("VAULT", "🔓 Vault manually resumed by operator")

    def reset_full(self):
        """Full reset — stop engine, clear state."""
        self.positions         = {}
        self.trade_log         = []
        self._burst            = {}
        self._in_position      = set()
        self._cooldown_ts      = {}
        self._loss_pause_until = 0.0
        self.stats.reset()
        self.equity_curve      = []


# ══════════════════════════════════════════════════════════════════
#  SINGLETON — diimpor oleh main.py
# ══════════════════════════════════════════════════════════════════

rapid_scalper = RapidScalper()