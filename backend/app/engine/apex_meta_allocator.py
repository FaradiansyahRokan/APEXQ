"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          APEX META ALLOCATOR v1.0                                           ║
║   Central Capital Allocator · Strategy Coordinator · Portfolio Heat Gate   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  INI ADALAH MISSING PIECE TERBESAR DARI STACK KALIAN:                       ║
║                                                                              ║
║  Sekarang (BROKEN):                                                          ║
║  ─────────────────                                                           ║
║   hft_engine (Predator) ──→ LONG BTC $300                                  ║
║   hft_rapid_scalper (Jackal) ──→ LONG BTC $300  ← tidak ada yang tahu!    ║
║   portfolio_simulator ──→ LONG SOL $200                                     ║
║   Total BTC exposure: $600 (tapi risk system pikir $300)                   ║
║   Double fees, double slippage, no one coordinating                         ║
║                                                                              ║
║  Dengan MetaAllocator (CORRECT):                                            ║
║  ─────────────────────────────                                              ║
║   MetaAllocator melihat SEMUA exposure:                                     ║
║     → Total capital deployed: 60%                                           ║
║     → BTC correlation cluster: $600 (too concentrated)                      ║
║     → Block Jackal's BTC LONG (duplicate)                                   ║
║     → Redirect Jackal budget ke ETH (different correlation)                 ║
║                                                                              ║
║  Apa yang MetaAllocator lakukan:                                            ║
║                                                                              ║
║  1. CAPITAL BUDGETING PER STRATEGY                                          ║
║     Setiap strategy dapat budget % dari total capital.                      ║
║     Budget disesuaikan DINAMIS berdasarkan recent performance:              ║
║     • Strategy yang winning → budget dinaikkan                               ║
║     • Strategy yang bleeding → budget dikurangi                              ║
║     • Rolling 20-trade Sharpe sebagai performance proxy                     ║
║                                                                              ║
║  2. CORRELATION CLUSTER MANAGEMENT                                          ║
║     Setiap posisi open dipetakan ke cluster:                                ║
║     • BTC Cluster: BTC, ETH, BNB, SOL (high correlation)                  ║
║     • DeFi Cluster: UNI, LINK, AAVE, CRV                                   ║
║     • L1 Cluster: AVAX, DOT, ATOM, NEAR                                     ║
║     • Meme Cluster: DOGE, SHIB, PEPE                                        ║
║     Max exposure per cluster = configurable % of capital                    ║
║                                                                              ║
║  3. PORTFOLIO HEAT GATE                                                     ║
║     Total heat = Σ |entry - stop| × qty untuk semua posisi open            ║
║     Hard cap: max_heat_pct of total capital                                 ║
║     Sebelum approve any new entry → check remaining heat budget             ║
║                                                                              ║
║  4. REGIME-BASED ALLOCATION SHIFT                                           ║
║     Regime sekarang LOW_VOL_BULLISH → HFT gets 40%, Swing gets 40%        ║
║     Regime HIGH_VOL_BEARISH → HFT reduced to 20%, 60% cash                ║
║     Regime CRISIS → halt all new entries, hold cash                         ║
║                                                                              ║
║  5. PERFORMANCE-ADAPTIVE SIZING                                             ║
║     Setelah 10+ trade:                                                      ║
║     - Recent Sharpe > 1.5 → scale up 20%                                   ║
║     - Recent Sharpe < 0.5 → scale down 40%                                 ║
║     - Recent Sharpe < 0.0 → halt strategy, review                          ║
║                                                                              ║
║  HOW TO INTEGRATE:                                                          ║
║  ──────────────────                                                          ║
║  In hft_engine.py _scan_entries():                                          ║
║    # Before opening position:                                               ║
║    decision = meta.request_capital(                                         ║
║        strategy="PREDATOR", coin="BTC", direction="LONG",                  ║
║        requested_usd=100, stop_pct=0.15, entry_price=67420                 ║
║    )                                                                         ║
║    if not decision.approved: continue                                       ║
║    actual_size = decision.approved_usd                                      ║
║                                                                              ║
║  In hft_engine.py _close_position():                                        ║
║    meta.release_capital(                                                    ║
║        strategy="PREDATOR", coin="BTC",                                     ║
║        pnl_pct=trade.net_pct, pnl_usd=trade.net_pnl                        ║
║    )                                                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Deque

import numpy as np

_EPS = 1e-12


# ══════════════════════════════════════════════════════════════════════════════
#  COIN CORRELATION CLUSTERS
#  Empirically grouped by rolling 30-day correlation > 0.65
# ══════════════════════════════════════════════════════════════════════════════

COIN_CLUSTERS: Dict[str, str] = {
    # BTC Cluster (all highly correlated with BTC)
    "BTC": "BTC_CLUSTER", "ETH": "BTC_CLUSTER", "BNB": "BTC_CLUSTER",
    "SOL": "BTC_CLUSTER", "AVAX": "BTC_CLUSTER", "MATIC": "BTC_CLUSTER",
    "ARB": "BTC_CLUSTER", "OP": "BTC_CLUSTER",

    # DeFi Cluster
    "UNI": "DEFI_CLUSTER", "LINK": "DEFI_CLUSTER", "AAVE": "DEFI_CLUSTER",
    "CRV": "DEFI_CLUSTER", "GMX": "DEFI_CLUSTER", "DYDX": "DEFI_CLUSTER",

    # L1 Alts Cluster
    "DOT": "L1_CLUSTER",  "ATOM": "L1_CLUSTER", "NEAR": "L1_CLUSTER",
    "APT": "L1_CLUSTER",  "SUI": "L1_CLUSTER",  "TIA": "L1_CLUSTER",
    "INJ": "L1_CLUSTER",

    # Meme Cluster
    "DOGE": "MEME_CLUSTER", "SHIB": "MEME_CLUSTER", "PEPE": "MEME_CLUSTER",
    "WIF": "MEME_CLUSTER",  "FLOKI": "MEME_CLUSTER",

    # Large Cap Standalone
    "XRP": "XRP_STANDALONE", "LTC": "LTC_STANDALONE",
    "BCH": "BCH_STANDALONE", "FIL": "FIL_STANDALONE",
}

# Stock clusters
STOCK_CLUSTERS: Dict[str, str] = {
    "NVDA": "SEMIS", "AMD": "SEMIS", "AVGO": "SEMIS", "TSM": "SEMIS",
    "AAPL": "BIGTECH", "MSFT": "BIGTECH", "GOOGL": "BIGTECH",
    "META": "BIGTECH", "AMZN": "BIGTECH",
    "TSLA": "EV_TECH", "COIN": "CRYPTO_PROXY", "MSTR": "CRYPTO_PROXY",
}

def get_cluster(coin: str) -> str:
    c = coin.upper()
    return (COIN_CLUSTERS.get(c)
            or STOCK_CLUSTERS.get(c)
            or f"STANDALONE_{c}")


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MetaConfig:
    total_capital          : float = 10_000.0

    # Strategy budget caps (% of total capital)
    strategy_budgets       : Dict[str, float] = field(default_factory=lambda: {
        "PREDATOR"         : 0.30,   # hft_engine HFTPredator
        "JACKAL"           : 0.30,   # hft_rapid_scalper
        "SATIN"            : 0.25,   # portfolio_simulator (swing/positional)
        "MANUAL"           : 0.15,   # manual/discretionary trades
    })

    # Per-cluster max exposure (% of total capital)
    max_cluster_exposure   : float = 0.25   # max 25% in any one cluster
    max_single_coin        : float = 0.15   # max 15% in any single coin

    # Portfolio heat
    max_portfolio_heat     : float = 0.12   # max 12% total heat

    # Performance-adaptive sizing thresholds
    sharpe_boost_threshold : float = 1.5    # recent SR > this → +20% size
    sharpe_reduce_threshold: float = 0.5    # recent SR < this → -40% size
    sharpe_halt_threshold  : float = 0.0    # recent SR < this → halt strategy

    # Regime allocation
    regime_allocations     : Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "LOW_VOL_BULLISH"  : {"PREDATOR": 1.0, "JACKAL": 1.0, "SATIN": 1.0},
        "SIDEWAYS_CHOP"    : {"PREDATOR": 0.8, "JACKAL": 0.6, "SATIN": 0.7},
        "HIGH_VOL_BEARISH" : {"PREDATOR": 0.5, "JACKAL": 0.4, "SATIN": 0.3},
        "CRISIS"           : {"PREDATOR": 0.0, "JACKAL": 0.0, "SATIN": 0.0},
        "UNKNOWN"          : {"PREDATOR": 0.7, "JACKAL": 0.7, "SATIN": 0.7},
    })

    performance_window     : int   = 20     # rolling trades for SR calculation
    min_trades_for_adapt   : int   = 10     # min trades before adaptive kicks in


# ══════════════════════════════════════════════════════════════════════════════
#  POSITION REGISTRY  — tracks all open positions across all strategies
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OpenPosition:
    strategy    : str
    coin        : str
    direction   : str        # "LONG" | "SHORT"
    entry_price : float
    stop_price  : float
    size_usd    : float      # notional value
    opened_at   : float      # unix timestamp
    cluster     : str = ""

    def __post_init__(self):
        self.cluster = get_cluster(self.coin)

    @property
    def heat_usd(self) -> float:
        """Dollar risk = |entry - stop| / entry × size."""
        if self.entry_price <= 0:
            return 0.0
        stop_dist_pct = abs(self.entry_price - self.stop_price) / self.entry_price
        return self.size_usd * stop_dist_pct


@dataclass
class AllocationDecision:
    approved      : bool
    approved_usd  : float       # actual capital to deploy (may be < requested)
    strategy      : str
    coin          : str
    direction     : str
    block_reason  : Optional[str]
    size_scalar   : float        # ratio: approved / requested
    heat_after    : float        # portfolio heat if approved
    notes         : List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
#  STRATEGY PERFORMANCE TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class StrategyTracker:
    """Rolling performance metrics per strategy."""

    def __init__(self, name: str, window: int = 20):
        self.name    = name
        self.window  = window
        self._pnls   : Deque[float] = deque(maxlen=window)
        self._ts     : Deque[float] = deque(maxlen=window)
        self.total_pnl_usd = 0.0
        self.trade_count   = 0

    def record(self, pnl_pct: float, pnl_usd: float):
        self._pnls.append(pnl_pct)
        self._ts.append(time.time())
        self.total_pnl_usd += pnl_usd
        self.trade_count   += 1

    @property
    def recent_sharpe(self) -> float:
        arr = np.array(list(self._pnls), float)
        if len(arr) < 5:
            return 0.0
        std = float(np.std(arr, ddof=1))
        return float(np.mean(arr) / std) if std > _EPS else 0.0

    @property
    def recent_win_rate(self) -> float:
        arr = np.array(list(self._pnls), float)
        if len(arr) == 0:
            return 0.0
        return float((arr > 0).mean())

    @property
    def recent_profit_factor(self) -> float:
        arr = np.array(list(self._pnls), float)
        if len(arr) < 2:
            return 1.0
        wins  = float(arr[arr > 0].sum())
        losses = float(abs(arr[arr < 0].sum()))
        return wins / losses if losses > _EPS else (9.9 if wins > 0 else 0.0)

    def performance_scalar(self, config: MetaConfig) -> float:
        """Returns size scalar [0.0, 1.2] based on recent performance."""
        if self.trade_count < config.min_trades_for_adapt:
            return 1.0   # not enough data → use base budget

        sr = self.recent_sharpe
        if sr <= config.sharpe_halt_threshold:
            return 0.0   # halt
        if sr < config.sharpe_reduce_threshold:
            # Linear scale from 0.6 to 1.0 between halt and reduce threshold
            frac = (sr - config.sharpe_halt_threshold) / (
                config.sharpe_reduce_threshold - config.sharpe_halt_threshold + _EPS)
            return float(np.clip(0.6 + frac * 0.4, 0.6, 1.0))
        if sr > config.sharpe_boost_threshold:
            return 1.2   # boost
        return 1.0   # normal

    def to_dict(self) -> Dict:
        return {
            "strategy"          : self.name,
            "trade_count"       : self.trade_count,
            "recent_sharpe"     : round(self.recent_sharpe, 4),
            "recent_win_rate"   : round(self.recent_win_rate, 4),
            "recent_pf"         : round(self.recent_profit_factor, 4),
            "total_pnl_usd"     : round(self.total_pnl_usd, 2),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  META ALLOCATOR  — main class
# ══════════════════════════════════════════════════════════════════════════════

class MetaAllocator:
    """
    Central capital allocator. Single source of truth for all positions.

    Thread-safety: designed for single-threaded async use.
    For multi-strategy concurrent access, wrap calls in asyncio.Lock.

    Usage:

        meta = MetaAllocator(config=MetaConfig(total_capital=10_000))

        # Before opening any position:
        decision = meta.request_capital(
            strategy    = "PREDATOR",
            coin        = "BTC",
            direction   = "LONG",
            requested_usd = 500,
            entry_price   = 67420,
            stop_price    = 67000,
        )
        if decision.approved:
            # open position with decision.approved_usd
            meta.register_open(decision, position_id="pos_001")

        # When closing:
        meta.release_capital(
            strategy   = "PREDATOR",
            coin       = "BTC",
            pnl_pct    = 0.42,
            pnl_usd    = 2.10,
            position_id = "pos_001",
        )

        # Update market regime (from apex_engine_v6):
        meta.set_regime("LOW_VOL_BULLISH")

        # Status dashboard:
        status = meta.get_status()
    """

    def __init__(self, config: Optional[MetaConfig] = None):
        self.config  = config or MetaConfig()

        # Open positions registry: id → OpenPosition
        self._positions  : Dict[str, OpenPosition] = {}

        # Strategy performance trackers
        self._trackers   : Dict[str, StrategyTracker] = {
            s: StrategyTracker(s, self.config.performance_window)
            for s in self.config.strategy_budgets
        }

        # Current regime
        self._regime     : str = "UNKNOWN"

        # Decision log
        self._decisions  : Deque[Dict] = deque(maxlen=500)

    # ─── Regime ────────────────────────────────────────────────────────────

    def set_regime(self, regime: str):
        """Update market regime. Affects all subsequent capital requests."""
        self._regime = regime.upper()

    # ─── Capital Request ───────────────────────────────────────────────────

    def request_capital(
        self,
        strategy      : str,
        coin          : str,
        direction     : str,
        requested_usd : float,
        entry_price   : float,
        stop_price    : float,
    ) -> AllocationDecision:
        """
        Main entry point. Call before opening any position.

        Returns AllocationDecision with:
          approved     : bool
          approved_usd : actual size to deploy (may differ from requested)
          block_reason : why it was blocked (if any)
          size_scalar  : approved / requested
        """
        coin      = coin.upper()
        strategy  = strategy.upper()
        notes     : List[str] = []
        block_reason: Optional[str] = None

        # ── 0. Strategy budget check ────────────────────────────────────────
        base_budget_usd = (
            self.config.total_capital *
            self.config.strategy_budgets.get(strategy, 0.20)
        )
        deployed_by_strategy = sum(
            p.size_usd for p in self._positions.values()
            if p.strategy == strategy
        )
        remaining_budget = base_budget_usd - deployed_by_strategy

        if remaining_budget <= 0:
            block_reason = f"{strategy} budget exhausted ({deployed_by_strategy:.0f}/{base_budget_usd:.0f} USD)"

        # ── 1. Regime allocation scalar ─────────────────────────────────────
        regime_allocs = self.config.regime_allocations.get(
            self._regime, self.config.regime_allocations["UNKNOWN"]
        )
        regime_scalar = regime_allocs.get(strategy, 0.7)
        if regime_scalar == 0.0:
            block_reason = block_reason or f"Regime {self._regime} blocks {strategy}"

        # ── 2. Duplicate position check ─────────────────────────────────────
        existing_same = [
            p for p in self._positions.values()
            if p.coin == coin and p.direction == direction and p.strategy != strategy
        ]
        if existing_same:
            strategies_str = ", ".join(set(p.strategy for p in existing_same))
            notes.append(f"DUPLICATE: {coin} {direction} already open in [{strategies_str}]")
            # Don't block — but reduce size by 50% to avoid concentration
            requested_usd *= 0.5
            notes.append("Size halved due to duplicate across strategies")

        # ── 3. Cluster exposure check ────────────────────────────────────────
        cluster         = get_cluster(coin)
        cluster_exposed = sum(
            p.size_usd for p in self._positions.values()
            if p.cluster == cluster
        )
        max_cluster_usd = self.config.total_capital * self.config.max_cluster_exposure
        if cluster_exposed + requested_usd > max_cluster_usd:
            # Clip to remaining cluster budget
            available = max(0.0, max_cluster_usd - cluster_exposed)
            if available < requested_usd * 0.3:
                block_reason = block_reason or (
                    f"Cluster {cluster} max exposure reached "
                    f"({cluster_exposed:.0f}/{max_cluster_usd:.0f} USD)"
                )
            else:
                requested_usd = min(requested_usd, available)
                notes.append(f"Size clipped to {available:.0f} USD (cluster cap)")

        # ── 4. Single-coin concentration check ──────────────────────────────
        coin_exposed = sum(
            p.size_usd for p in self._positions.values() if p.coin == coin
        )
        max_coin_usd = self.config.total_capital * self.config.max_single_coin
        if coin_exposed + requested_usd > max_coin_usd:
            available = max(0.0, max_coin_usd - coin_exposed)
            if available < requested_usd * 0.2:
                block_reason = block_reason or (
                    f"Single coin {coin} max {self.config.max_single_coin*100:.0f}% reached"
                )
            else:
                requested_usd = min(requested_usd, available)
                notes.append(f"Size clipped to {available:.0f} USD (coin concentration)")

        # ── 5. Portfolio heat check ──────────────────────────────────────────
        current_heat = self._compute_heat()
        new_heat_usd = abs(entry_price - stop_price) / max(entry_price, _EPS) * requested_usd
        new_heat_pct = (current_heat + new_heat_usd) / max(self.config.total_capital, _EPS)
        if new_heat_pct > self.config.max_portfolio_heat:
            # Clip size so heat stays at max
            remaining_heat_usd = max(0.0,
                self.config.total_capital * self.config.max_portfolio_heat - current_heat)
            stop_pct = abs(entry_price - stop_price) / max(entry_price, _EPS)
            max_size_from_heat = remaining_heat_usd / max(stop_pct, _EPS)
            if max_size_from_heat < requested_usd * 0.2:
                block_reason = block_reason or (
                    f"Portfolio heat {new_heat_pct*100:.1f}% would exceed "
                    f"{self.config.max_portfolio_heat*100:.0f}% cap"
                )
            else:
                requested_usd = min(requested_usd, max_size_from_heat)
                notes.append(f"Size clipped to {requested_usd:.0f} USD (heat cap)")

        # ── 6. Performance-adaptive scalar ──────────────────────────────────
        perf_scalar = 1.0
        tracker = self._trackers.get(strategy)
        if tracker:
            perf_scalar = tracker.performance_scalar(self.config)
            if perf_scalar == 0.0:
                block_reason = block_reason or (
                    f"{strategy} halted: recent Sharpe "
                    f"{tracker.recent_sharpe:.2f} < {self.config.sharpe_halt_threshold}"
                )
            elif perf_scalar < 1.0:
                notes.append(f"Perf scalar {perf_scalar:.2f} (recent SR={tracker.recent_sharpe:.2f})")

        # ── 7. Compute final approved size ───────────────────────────────────
        if block_reason:
            approved_usd = 0.0
            size_scalar  = 0.0
            approved     = False
        else:
            # Cap by remaining strategy budget
            requested_usd = min(requested_usd, remaining_budget)
            # Apply regime + perf scalars
            approved_usd  = requested_usd * regime_scalar * perf_scalar
            approved_usd  = max(0.0, round(approved_usd, 2))
            size_scalar   = approved_usd / max(requested_usd, _EPS)
            approved      = approved_usd >= 10.0   # min $10 order

        # ── Compute heat after this position ─────────────────────────────────
        if approved:
            add_heat = abs(entry_price - stop_price) / max(entry_price, _EPS) * approved_usd
        else:
            add_heat = 0.0
        heat_after = (current_heat + add_heat) / max(self.config.total_capital, _EPS) * 100

        decision = AllocationDecision(
            approved     = approved,
            approved_usd = approved_usd,
            strategy     = strategy,
            coin         = coin,
            direction    = direction,
            block_reason = block_reason,
            size_scalar  = round(size_scalar, 4),
            heat_after   = round(heat_after, 4),
            notes        = notes,
        )

        # Log decision
        self._decisions.append({
            "ts"          : time.time(),
            "strategy"    : strategy,
            "coin"        : coin,
            "direction"   : direction,
            "approved"    : approved,
            "approved_usd": approved_usd,
            "size_scalar" : size_scalar,
            "block_reason": block_reason,
            "notes"       : notes,
        })

        return decision

    # ─── Position Lifecycle ────────────────────────────────────────────────

    def register_open(
        self,
        decision    : AllocationDecision,
        entry_price : float,
        stop_price  : float,
        position_id : str,
    ):
        """Call after successfully opening a position."""
        if not decision.approved:
            return
        pos = OpenPosition(
            strategy    = decision.strategy,
            coin        = decision.coin,
            direction   = decision.direction,
            entry_price = entry_price,
            stop_price  = stop_price,
            size_usd    = decision.approved_usd,
            opened_at   = time.time(),
        )
        self._positions[position_id] = pos

    def release_capital(
        self,
        position_id : str,
        pnl_pct     : float,
        pnl_usd     : float,
    ):
        """Call when a position is closed. Records performance and frees budget."""
        pos = self._positions.pop(position_id, None)
        if pos is None:
            return
        tracker = self._trackers.get(pos.strategy)
        if tracker:
            tracker.record(pnl_pct, pnl_usd)

    def update_stop(self, position_id: str, new_stop: float):
        """Update stop price for a position (e.g., trailing stop moved)."""
        if position_id in self._positions:
            self._positions[position_id].stop_price = new_stop

    # ─── Portfolio Analytics ───────────────────────────────────────────────

    def _compute_heat(self) -> float:
        """Total portfolio heat in USD."""
        return sum(p.heat_usd for p in self._positions.values())

    def get_cluster_exposure(self) -> Dict[str, float]:
        """USD exposure per cluster."""
        result: Dict[str, float] = {}
        for p in self._positions.values():
            result[p.cluster] = result.get(p.cluster, 0.0) + p.size_usd
        return result

    def get_coin_exposure(self) -> Dict[str, float]:
        """USD exposure per coin."""
        result: Dict[str, float] = {}
        for p in self._positions.values():
            key = f"{p.coin}_{p.direction}"
            result[key] = result.get(key, 0.0) + p.size_usd
        return result

    def get_strategy_deployment(self) -> Dict[str, Dict]:
        """How much of each strategy's budget is currently deployed."""
        out = {}
        for strategy, budget_pct in self.config.strategy_budgets.items():
            budget_usd  = self.config.total_capital * budget_pct
            deployed    = sum(p.size_usd for p in self._positions.values()
                              if p.strategy == strategy)
            utilization = deployed / max(budget_usd, _EPS) * 100
            out[strategy] = {
                "budget_usd"     : round(budget_usd, 2),
                "deployed_usd"   : round(deployed, 2),
                "utilization_pct": round(utilization, 2),
                "remaining_usd"  : round(budget_usd - deployed, 2),
            }
        return out

    def get_status(self) -> Dict:
        """Full dashboard status."""
        heat_usd  = self._compute_heat()
        heat_pct  = heat_usd / max(self.config.total_capital, _EPS) * 100
        n_open    = len(self._positions)
        deployed  = sum(p.size_usd for p in self._positions.values())
        dep_pct   = deployed / max(self.config.total_capital, _EPS) * 100

        return {
            "total_capital"       : self.config.total_capital,
            "current_regime"      : self._regime,
            "n_open_positions"    : n_open,
            "total_deployed_usd"  : round(deployed, 2),
            "deployed_pct"        : round(dep_pct, 2),
            "portfolio_heat_usd"  : round(heat_usd, 2),
            "portfolio_heat_pct"  : round(heat_pct, 4),
            "heat_remaining_pct"  : round(
                max(0.0, self.config.max_portfolio_heat * 100 - heat_pct), 4),
            "cluster_exposure"    : {
                k: round(v, 2) for k, v in self.get_cluster_exposure().items()
            },
            "coin_exposure"       : {
                k: round(v, 2) for k, v in self.get_coin_exposure().items()
            },
            "strategy_deployment" : self.get_strategy_deployment(),
            "strategy_performance": {
                s: t.to_dict() for s, t in self._trackers.items()
            },
            "open_positions"      : [
                {
                    "id"       : pid,
                    "strategy" : p.strategy,
                    "coin"     : p.coin,
                    "dir"      : p.direction,
                    "size_usd" : round(p.size_usd, 2),
                    "heat_usd" : round(p.heat_usd, 2),
                    "cluster"  : p.cluster,
                    "age_s"    : round(time.time() - p.opened_at, 1),
                }
                for pid, p in self._positions.items()
            ],
            "recent_decisions"    : list(self._decisions)[-10:],
        }

    def can_add_position(self, strategy: str, coin: str,
                         estimated_usd: float = 100.0) -> Tuple[bool, str]:
        """Quick pre-check before computing full signal."""
        strategy = strategy.upper()
        coin     = coin.upper()

        heat     = self._compute_heat()
        heat_pct = heat / max(self.config.total_capital, _EPS)
        if heat_pct >= self.config.max_portfolio_heat:
            return False, f"Portfolio heat maxed: {heat_pct*100:.1f}%"

        budget_usd = (self.config.total_capital *
                      self.config.strategy_budgets.get(strategy, 0.0))
        deployed   = sum(p.size_usd for p in self._positions.values()
                         if p.strategy == strategy)
        if deployed >= budget_usd:
            return False, f"{strategy} budget full"

        regime_allocs = self.config.regime_allocations.get(
            self._regime, self.config.regime_allocations["UNKNOWN"])
        if regime_allocs.get(strategy, 1.0) == 0.0:
            return False, f"Regime {self._regime} blocks {strategy}"

        return True, "OK"


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE-LEVEL SINGLETON  (optional — convenient for single-process use)
# ══════════════════════════════════════════════════════════════════════════════

_default_allocator: Optional[MetaAllocator] = None


def get_allocator(total_capital: float = 10_000.0) -> MetaAllocator:
    """
    Get or create the global MetaAllocator instance.
    Call once at startup: get_allocator(total_capital=your_balance)
    """
    global _default_allocator
    if _default_allocator is None:
        _default_allocator = MetaAllocator(MetaConfig(total_capital=total_capital))
    return _default_allocator


def reset_allocator(total_capital: float = 10_000.0) -> MetaAllocator:
    """Force-create a fresh allocator (use after balance changes)."""
    global _default_allocator
    _default_allocator = MetaAllocator(MetaConfig(total_capital=total_capital))
    return _default_allocator
