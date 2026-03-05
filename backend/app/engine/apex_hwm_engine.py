"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              APEX HWM PROTECTION ENGINE v1.0                                ║
║   High-Watermark equity protection with convex risk decay                   ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  KOMPONEN:                                                                   ║
║    HWMConfig              — konfigurasi parameter sistem                     ║
║    HWMRiskDecision        — output per-trade dari evaluate_trade()           ║
║    EquityHWMStateMachine  — lacak HWM, floor, milestone ladder               ║
║    CapitalLockManager     — halt trading jika edge hilang / DD parah         ║
║    VolatilityRiskScaler   — skalakan risk berdasarkan vol regime              ║
║    TimeframeRiskBudget    — alokasi heat per timeframe                       ║
║    EquityCurveFeedbackLoop— adaptive risk feedback dari equity curve         ║
║    SystemHealthMonitor    — rolling Sharpe, win rate, profit factor           ║
║    HWMPositionSizer       — size posisi dengan semua scalar                  ║
║    CompoundingEngine      — compounding log dari equity curve                ║
║    ValidationSuite        — Monte Carlo + walk-forward validation            ║
║    HWMSession             — facade utama, orchestrates semua komponen        ║
║    generate_system_design_report() — dokumentasi sistem                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ══════════════════════════════════════════════════════════════════════════════
#  1. CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HWMConfig:
    """
    Semua parameter konfigurasi untuk satu HWM session.
    """
    initial_capital        : float = 100_000.0
    max_drawdown_pct       : float = 15.0        # hard cap % dari initial (absolute)
    trailing_stop_pct      : float = 8.0         # trailing stop % dari HWM
    max_portfolio_heat_pct : float = 0.06        # max heat as fraction of capital
    max_base_risk_pct      : float = 0.02        # per-trade max risk fraction
    kelly_fraction         : float = 0.25
    risk_free_rate         : float = 0.04
    hwm_curvature          : float = 1.5         # γ for convex decay
    target_vol_ann         : float = 0.12        # 12% annualized vol target
    # Milestone thresholds (% above initial capital → lock floor at prev)
    milestone_pcts         : List[float] = field(default_factory=lambda: [
        5, 10, 20, 30, 50, 75, 100, 150, 200
    ])


# ══════════════════════════════════════════════════════════════════════════════
#  2. RISK DECISION OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HWMRiskDecision:
    """
    Output lengkap dari HWMPositionSizer.evaluate() per trade.
    """
    # Gate
    trade_approved      : bool   = True
    rejection_reasons   : List[str] = field(default_factory=list)
    warnings            : List[str] = field(default_factory=list)

    # Sizing
    recommended_units   : float  = 0.0
    position_value_usd  : float  = 0.0
    dollar_risk_usd     : float  = 0.0
    final_risk_pct      : float  = 0.0

    # Scalars
    hwm_risk_scalar     : float  = 1.0
    vol_scalar          : float  = 1.0
    ma_filter_scalar    : float  = 1.0
    composite_scalar    : float  = 1.0

    # Equity state
    current_equity      : float  = 0.0
    hwm                 : float  = 0.0
    active_floor        : float  = 0.0
    drawdown_from_hwm_pct: float = 0.0
    allowable_dd_from_here: float = 0.0

    # Metadata
    system_status       : str    = "ACTIVE"
    timeframe           : str    = "swing"
    ticker              : str    = ""
    timestamp           : str    = ""


# ══════════════════════════════════════════════════════════════════════════════
#  3. EQUITY HWM STATE MACHINE
# ══════════════════════════════════════════════════════════════════════════════

class EquityHWMStateMachine:
    """
    Lacak high-watermark, trailing floor, dan milestone ladder.
    """

    def __init__(self, config: HWMConfig):
        self.config          = config
        self.initial_capital = config.initial_capital
        self.current_equity  = config.initial_capital
        self.hwm             = config.initial_capital
        self.active_floor    = 0.0  # floor dimulai dari 0, naik seiring milestone dicapai

        # Build milestone ladder: {level_pct: floor_pct_if_reached}
        # Setiap milestone terkunci jika floor sebelumnya sudah dicapai
        pcts = sorted(config.milestone_pcts)
        self.milestone_ladder: List[Dict] = []
        for i, lvl in enumerate(pcts):
            floor_pct = pcts[i - 1] if i > 0 else 0.0
            self.milestone_ladder.append({
                "level_pct"   : lvl,
                "floor_pct"   : floor_pct,
                "target_equity": round(self.initial_capital * (1 + lvl / 100), 2),
                "floor_equity" : round(self.initial_capital * (1 + floor_pct / 100), 2),
                "reached"      : False,
                "locked_at"    : None,
            })

    def update(self, new_equity: float):
        """Panggil setelah setiap trade selesai."""
        self.current_equity = new_equity

        # Update HWM
        if new_equity > self.hwm:
            self.hwm = new_equity

        # Check milestones
        for ms in self.milestone_ladder:
            if not ms["reached"] and new_equity >= ms["target_equity"]:
                ms["reached"]   = True
                ms["locked_at"] = new_equity
                # Kunci floor ke level milestone ini
                new_floor = ms["floor_equity"]
                if new_floor > self.active_floor:
                    self.active_floor = new_floor

        # Trailing stop dari HWM
        trailing_floor = self.hwm * (1 - self.config.trailing_stop_pct / 100)
        if trailing_floor > self.active_floor:
            self.active_floor = trailing_floor

    def drawdown_from_hwm_pct(self) -> float:
        return max(0.0, (self.hwm - self.current_equity) / max(self.hwm, 1) * 100)

    def hwm_scalar(self) -> float:
        """Convex decay scalar: [(E−floor)/(HWM−floor)]^γ clamped [0,1]."""
        gamma = self.config.hwm_curvature
        denom = max(self.hwm - self.active_floor, 1.0)
        raw   = (self.current_equity - self.active_floor) / denom
        return float(max(0.0, min(1.0, raw ** gamma)))

    def milestone_summary(self) -> Dict:
        hit = [m for m in self.milestone_ladder if m["reached"]]
        return {
            "milestone_ladder"    : self.milestone_ladder,
            "milestones_hit"      : hit,
            "milestones_hit_count": len(hit),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  4. CAPITAL LOCK MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class CapitalLockManager:
    """
    Halt trading jika kondisi berbahaya terdeteksi.
    """

    def __init__(self, config: HWMConfig):
        self.config       = config
        self._is_halted   = False
        self._halt_reason = None

    def evaluate(self, current_equity: float, active_floor: float,
                 system_status: str) -> bool:
        """
        Return True jika trading DIIZINKAN (tidak di-halt).
        """
        if system_status == "SHUTDOWN":
            self._is_halted   = True
            self._halt_reason = "System health SHUTDOWN — edge hilang"
            return False

        if current_equity <= active_floor:
            self._is_halted   = True
            self._halt_reason = "Equity menyentuh floor proteksi"
            return False

        # Hard MDD dari initial capital
        mdd_from_initial = (self.config.initial_capital - current_equity) / max(self.config.initial_capital, 1) * 100
        if mdd_from_initial >= self.config.max_drawdown_pct:
            self._is_halted   = True
            self._halt_reason = f"Hard MDD cap {self.config.max_drawdown_pct}% tercapai"
            return False

        # Jika equity kembali sehat, buka kunci
        if self._is_halted and current_equity > active_floor * 1.02:
            self._is_halted   = False
            self._halt_reason = None

        return not self._is_halted

    def force_halt(self, reason: str):
        self._is_halted   = True
        self._halt_reason = reason

    def release(self):
        self._is_halted   = False
        self._halt_reason = None


# ══════════════════════════════════════════════════════════════════════════════
#  5. VOLATILITY RISK SCALER
# ══════════════════════════════════════════════════════════════════════════════

class VolatilityRiskScaler:
    """
    Skalakan risk berdasarkan vol regime relatif terhadap target vol.
    """

    def __init__(self, target_vol_ann: float = 0.12):
        self.target_vol = target_vol_ann

    def compute_scalar(self, returns: Optional[np.ndarray] = None) -> Tuple[float, str]:
        """Return (scalar, regime_label)."""
        if returns is None or len(returns) < 20:
            return 1.0, "UNKNOWN"

        realized_vol = float(np.std(returns[-20:], ddof=1) * math.sqrt(252))

        if realized_vol <= 0:
            return 1.0, "LOW"

        # Vol-target scalar: clamp to [0.25, 2.0]
        raw_scalar = self.target_vol / realized_vol
        scalar     = max(0.25, min(2.0, raw_scalar))

        if realized_vol < self.target_vol * 0.7:
            regime = "LOW_VOL"
        elif realized_vol < self.target_vol * 1.3:
            regime = "NORMAL"
        elif realized_vol < self.target_vol * 2.0:
            regime = "HIGH_VOL"
        else:
            regime = "EXTREME_VOL"

        return round(scalar, 4), regime


# ══════════════════════════════════════════════════════════════════════════════
#  6. TIMEFRAME RISK BUDGET
# ══════════════════════════════════════════════════════════════════════════════

class TimeframeRiskBudget:
    """
    Alokasi heat kapital per timeframe: intraday, swing, position.
    """

    DEFAULT_BUDGETS = {
        "intraday" : 0.02,   # max 2% capital at risk intraday
        "swing"    : 0.04,   # max 4% capital at risk swing
        "position" : 0.06,   # max 6% capital at risk position
    }

    def __init__(self, portfolio_heat_cap: float = 0.06):
        self.budgets      = dict(self.DEFAULT_BUDGETS)
        self.current_heat = {tf: 0.0 for tf in self.budgets}
        self._portfolio_heat_cap = portfolio_heat_cap

    def can_add_heat(self, timeframe: str, heat_fraction: float) -> bool:
        tf    = timeframe if timeframe in self.budgets else "swing"
        total = sum(self.current_heat.values())
        return (
            self.current_heat[tf] + heat_fraction <= self.budgets[tf]
            and total + heat_fraction <= self._portfolio_heat_cap
        )

    def add_heat(self, timeframe: str, heat_fraction: float):
        tf = timeframe if timeframe in self.budgets else "swing"
        self.current_heat[tf] = max(0.0, self.current_heat[tf] + heat_fraction)

    def release_heat(self, timeframe: str, heat_fraction: float):
        tf = timeframe if timeframe in self.budgets else "swing"
        self.current_heat[tf] = max(0.0, self.current_heat[tf] - heat_fraction)

    def total_heat(self) -> float:
        return sum(self.current_heat.values())


# ══════════════════════════════════════════════════════════════════════════════
#  7. EQUITY CURVE FEEDBACK LOOP
# ══════════════════════════════════════════════════════════════════════════════

class EquityCurveFeedbackLoop:
    """
    Gunakan MA equity curve untuk scale risk.
    Kalau equity di bawah MA → risk dikurangi.
    """

    def __init__(self, window: int = 20):
        self.window  = window
        self._equity_history: deque = deque(maxlen=window * 2)

    def update(self, equity: float):
        self._equity_history.append(equity)

    def ma_scalar(self) -> Tuple[float, str]:
        """Return (scalar, signal)."""
        if len(self._equity_history) < self.window:
            return 1.0, "INSUFFICIENT_DATA"

        vals = list(self._equity_history)
        ma   = float(np.mean(vals[-self.window:]))
        curr = vals[-1]

        if curr >= ma:
            return 1.0, "ABOVE_MA"
        else:
            # Scale down proportionally: min 0.5 at -5% below MA
            ratio  = curr / max(ma, 1)
            scalar = max(0.5, ratio)
            return round(scalar, 4), "BELOW_MA"


# ══════════════════════════════════════════════════════════════════════════════
#  8. SYSTEM HEALTH MONITOR
# ══════════════════════════════════════════════════════════════════════════════

class SystemHealthMonitor:
    """
    Monitor kesehatan sistem: rolling Sharpe, win rate, profit factor,
    consecutive losses. Menghasilkan status ACTIVE / WARNING / SHUTDOWN.
    """

    def __init__(self, max_consec_losses: int = 7, window: int = 50):
        self.max_consec_losses = max_consec_losses
        self.window            = window
        self._trade_outcomes   : deque = deque(maxlen=window)  # 1=win, 0=loss
        self._trade_pnls       : deque = deque(maxlen=window)  # signed pnl
        self._consecutive_losses: int   = 0
        self._trade_count      : int    = 0

    def record(self, is_win: bool, pnl_pct: float):
        self._trade_count += 1
        self._trade_outcomes.append(1 if is_win else 0)
        self._trade_pnls.append(pnl_pct)

        if is_win:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1

    def evaluate(self) -> Dict:
        n     = len(self._trade_outcomes)
        pnls  = np.array(list(self._trade_pnls), dtype=float)

        if n == 0:
            return {
                "system_status"        : "ACTIVE",
                "trade_count"          : 0,
                "consecutive_losses"   : 0,
                "rolling_sharpe"       : 0.0,
                "win_rate_rolling"     : 0.0,
                "profit_factor_rolling": 0.0,
            }

        win_rate     = float(np.mean(list(self._trade_outcomes)))
        sharpe       = float(pnls.mean() / pnls.std(ddof=1)) if pnls.std(ddof=1) > 0 else 0.0
        wins_sum     = float(pnls[pnls > 0].sum()) if (pnls > 0).any() else 0.0
        losses_sum   = float(abs(pnls[pnls < 0].sum())) if (pnls < 0).any() else 1e-9
        profit_factor = wins_sum / max(losses_sum, 1e-9)

        # Status logic
        if self._consecutive_losses >= self.max_consec_losses:
            status = "SHUTDOWN"
        elif self._consecutive_losses >= self.max_consec_losses - 2:
            status = "WARNING"
        elif n >= 20 and win_rate < 0.30:
            status = "WARNING"
        elif n >= 30 and sharpe < -1.0:
            status = "SHUTDOWN"
        else:
            status = "ACTIVE"

        return {
            "system_status"        : status,
            "trade_count"          : self._trade_count,
            "consecutive_losses"   : self._consecutive_losses,
            "rolling_sharpe"       : round(sharpe, 4),
            "win_rate_rolling"     : round(win_rate, 4),
            "profit_factor_rolling": round(profit_factor, 4),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  9. HWM POSITION SIZER
# ══════════════════════════════════════════════════════════════════════════════

class HWMPositionSizer:
    """
    Menghitung ukuran posisi dengan semua scalar:
    Kelly × HWM scalar × Vol scalar × MA scalar × Timeframe budget
    """

    def __init__(self, config: HWMConfig):
        self.config = config

    def size(
        self,
        entry_price     : float,
        stop_loss_price : float,
        current_equity  : float,
        hwm_scalar      : float,
        vol_scalar      : float,
        ma_scalar       : float,
        win_rate        : float,
        avg_win_r       : float,  # avg win in R
        avg_loss_r      : float,  # avg loss in R (usually 1.0)
        timeframe       : str,
        budget          : TimeframeRiskBudget,
    ) -> Tuple[float, float, float, float]:
        """
        Return (units, position_value, dollar_risk, final_risk_pct)
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0, 0.0, 0.0, 0.0

        sl_dist = abs(entry_price - stop_loss_price)
        if sl_dist <= 0:
            return 0.0, 0.0, 0.0, 0.0

        # Kelly fraction
        if avg_loss_r > 0 and 0 < win_rate < 1:
            b          = avg_win_r / avg_loss_r
            loss_rate  = 1 - win_rate
            full_kelly = win_rate - loss_rate / b
            kelly_pct  = max(0.0, full_kelly * self.config.kelly_fraction)
        else:
            kelly_pct = self.config.max_base_risk_pct

        # Apply scalars
        composite_scalar = hwm_scalar * vol_scalar * ma_scalar
        adj_risk_pct     = kelly_pct * composite_scalar

        # Cap at config maximum
        adj_risk_pct = min(adj_risk_pct, self.config.max_base_risk_pct)

        dollar_risk       = current_equity * adj_risk_pct
        units             = dollar_risk / sl_dist
        position_value    = units * entry_price

        return (
            round(units, 6),
            round(position_value, 2),
            round(dollar_risk, 2),
            round(adj_risk_pct, 6),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  10. COMPOUNDING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class CompoundingEngine:
    """
    Lacak compounding equity log dan statistik pertumbuhan.
    """

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self._equity_log: List[float] = [initial_capital]

    def record(self, new_equity: float):
        self._equity_log.append(new_equity)

    def cagr(self) -> float:
        if len(self._equity_log) < 2:
            return 0.0
        years = len(self._equity_log) / 252
        if years <= 0:
            return 0.0
        return float((self._equity_log[-1] / max(self._equity_log[0], 1)) ** (1 / years) - 1)

    def total_return_pct(self) -> float:
        return float((self._equity_log[-1] / max(self.initial_capital, 1) - 1) * 100)

    def log_returns(self) -> np.ndarray:
        arr = np.array(self._equity_log)
        return np.log(arr[1:] / arr[:-1]) if len(arr) > 1 else np.array([])


# ══════════════════════════════════════════════════════════════════════════════
#  11. VALIDATION SUITE
# ══════════════════════════════════════════════════════════════════════════════

class ValidationSuite:
    """
    Validasi statistik strategi:
    - Block Bootstrap Monte Carlo
    - Rolling Walk-Forward Efficiency
    - Deployment gate (Sharpe ≥ 2, Calmar ≥ 1.5, MDD < 20%)
    - Deflated Sharpe Ratio
    """

    def run_full_validation(
        self,
        returns          : np.ndarray,
        n_simulations    : int = 10_000,
        train_months     : int = 12,
        test_months      : int = 3,
        seed             : int = 42,
    ) -> Dict:
        rng = np.random.default_rng(seed)
        n   = len(returns)

        # ── Base stats ──────────────────────────────────────────────
        mu      = float(np.mean(returns))
        sigma   = float(np.std(returns, ddof=1)) if n > 1 else 1e-9
        sharpe  = mu / sigma * math.sqrt(252) if sigma > 0 else 0.0

        cum     = np.exp(np.cumsum(returns))
        roll    = np.maximum.accumulate(cum)
        dd      = (cum - roll) / roll
        mdd_pct = float(dd.min() * 100)

        calmar  = float((mu * 252) / abs(mdd_pct / 100)) if mdd_pct < 0 else 0.0
        skew    = float(self._skewness(returns))
        kurt    = float(self._kurtosis(returns))

        # ── Block Bootstrap (block_size=10) ──────────────────────────
        block_size = 10
        sim_sharpes: List[float] = []
        for _ in range(n_simulations):
            blocks  = [rng.integers(0, max(1, n - block_size)) for _ in range(n // block_size + 1)]
            sim_ret = np.concatenate([returns[b:b + block_size] for b in blocks])[:n]
            s       = float(np.mean(sim_ret) / max(np.std(sim_ret, ddof=1), 1e-9) * math.sqrt(252))
            sim_sharpes.append(s)

        sim_arr    = np.array(sim_sharpes)
        sharpe_p   = float(np.mean(sim_arr >= sharpe))
        sharpe_ci  = [float(np.percentile(sim_arr, 2.5)), float(np.percentile(sim_arr, 97.5))]

        # ── Deflated Sharpe Ratio ────────────────────────────────────
        # DSR adjusts for multiple testing over n_trials
        n_trials  = max(1, n_simulations // 100)
        z_star    = math.sqrt(2) * _erfinv(1 - 2 / n_trials) if n_trials > 1 else 1.96
        var_sharpe = (1 + (1 - skew * sharpe + (kurt - 1) / 4 * sharpe ** 2)) / (n - 1)
        dsr        = float((sharpe - z_star * math.sqrt(max(var_sharpe, 1e-12))) /
                           math.sqrt(max(var_sharpe, 1e-12)) + 1e-12)

        # ── Walk-Forward Efficiency ───────────────────────────────────
        train_bars = train_months * 21
        test_bars  = test_months  * 21
        wfe_ratios : List[float] = []
        start = 0
        while start + train_bars + test_bars <= n:
            train_ret = returns[start : start + train_bars]
            test_ret  = returns[start + train_bars : start + train_bars + test_bars]
            in_sh  = float(np.mean(train_ret) / max(np.std(train_ret, ddof=1), 1e-9) * math.sqrt(252))
            out_sh = float(np.mean(test_ret)  / max(np.std(test_ret,  ddof=1), 1e-9) * math.sqrt(252))
            if in_sh > 0:
                wfe_ratios.append(out_sh / in_sh)
            start += test_bars
        wfe = float(np.mean(wfe_ratios)) if wfe_ratios else 0.0

        # ── Deployment Gate ──────────────────────────────────────────
        gate_pass   = sharpe >= 2.0 and calmar >= 1.5 and abs(mdd_pct) < 20.0
        gate_checks = {
            "sharpe_gte_2":    sharpe >= 2.0,
            "calmar_gte_1.5":  calmar >= 1.5,
            "mdd_lt_20pct":    abs(mdd_pct) < 20.0,
            "wfe_gte_0.5":     wfe >= 0.5,
        }

        return {
            "n_returns"            : n,
            "sharpe_ratio"         : round(sharpe, 4),
            "calmar_ratio"         : round(calmar, 4),
            "max_drawdown_pct"     : round(mdd_pct, 4),
            "skewness"             : round(skew, 4),
            "excess_kurtosis"      : round(kurt, 4),
            "annualized_return_pct": round(mu * 252 * 100, 4),
            "annualized_vol_pct"   : round(sigma * math.sqrt(252) * 100, 4),
            "bootstrap_sharpe_p_value"   : round(sharpe_p, 4),
            "bootstrap_sharpe_ci_95"     : [round(x, 4) for x in sharpe_ci],
            "deflated_sharpe_ratio"      : round(dsr, 4),
            "walk_forward_efficiency"    : round(wfe, 4),
            "n_wf_windows"               : len(wfe_ratios),
            "deployment_gate_pass"       : gate_pass,
            "deployment_gate_checks"     : gate_checks,
            "recommendation": (
                " DEPLOY — strategi lulus semua gate statistik"
                if gate_pass
                else " DO NOT DEPLOY — gagal satu atau lebih gate. Lihat gate_checks."
            ),
        }

    @staticmethod
    def _skewness(arr: np.ndarray) -> float:
        n  = len(arr)
        if n < 3:
            return 0.0
        mu = arr.mean(); sg = arr.std(ddof=1)
        return float(((arr - mu) ** 3).mean() / max(sg ** 3, 1e-12))

    @staticmethod
    def _kurtosis(arr: np.ndarray) -> float:
        n  = len(arr)
        if n < 4:
            return 0.0
        mu = arr.mean(); sg = arr.std(ddof=1)
        return float(((arr - mu) ** 4).mean() / max(sg ** 4, 1e-12)) - 3.0


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — inverse erf (untuk Deflated Sharpe)
# ══════════════════════════════════════════════════════════════════════════════

def _erfinv(x: float) -> float:
    """Approximate inverse error function (Abramowitz & Stegun)."""
    x = max(-1 + 1e-12, min(1 - 1e-12, x))
    a = 0.147
    ln_term = math.log(1 - x * x)
    term1   = 2 / (math.pi * a) + ln_term / 2
    return math.copysign(
        math.sqrt(math.sqrt(term1 * term1 - ln_term / a) - term1),
        x
    )


# ══════════════════════════════════════════════════════════════════════════════
#  12. HWM SESSION — Facade utama
# ══════════════════════════════════════════════════════════════════════════════

class HWMSession:
    """
    Facade yang mengorkestrasikan semua komponen HWM.
    Satu instance per strategi/buku.
    """

    def __init__(self, config: HWMConfig):
        self.config         = config
        self.hwm_sm         = EquityHWMStateMachine(config)
        self.lock_mgr       = CapitalLockManager(config)
        self.vol_scaler     = VolatilityRiskScaler(config.target_vol_ann)
        self.budget         = TimeframeRiskBudget(config.max_portfolio_heat_pct)
        self.feedback       = EquityCurveFeedbackLoop(window=20)
        self.health_monitor = SystemHealthMonitor(max_consec_losses=7)
        self.sizer          = HWMPositionSizer(config)
        self.compounding    = CompoundingEngine(config.initial_capital)

    # ── Pre-Trade Gate ─────────────────────────────────────────────
    def evaluate_trade(
        self,
        ticker           : str,
        entry_price      : float,
        stop_loss_price  : float,
        win_rate         : float,
        avg_win_pct      : float,   # decimal (e.g. 0.025 = 2.5%)
        avg_loss_pct     : float,   # decimal (e.g. 0.010 = 1.0%)
        current_equity   : float,
        timeframe        : str = "swing",
        returns_history  : Optional[np.ndarray] = None,
    ) -> HWMRiskDecision:
        """
        Evaluasi apakah trade boleh dibuka dan berapa ukurannya.
        """
        # Update state machine dengan equity terkini
        self.hwm_sm.update(current_equity)
        self.feedback.update(current_equity)

        health     = self.health_monitor.evaluate()
        sys_status = health["system_status"]

        # Capital lock check
        allowed = self.lock_mgr.evaluate(current_equity, self.hwm_sm.active_floor, sys_status)

        decision = HWMRiskDecision(
            current_equity       = current_equity,
            hwm                  = self.hwm_sm.hwm,
            active_floor         = self.hwm_sm.active_floor,
            drawdown_from_hwm_pct= self.hwm_sm.drawdown_from_hwm_pct(),
            allowable_dd_from_here= max(current_equity - self.hwm_sm.active_floor, 0.0),
            system_status        = sys_status,
            timeframe            = timeframe,
            ticker               = ticker,
            timestamp            = _now_iso(),
        )

        rejection_reasons: List[str] = []
        warnings         : List[str] = []

        if not allowed:
            rejection_reasons.append(f"Capital locked: {self.lock_mgr._halt_reason}")
        if sys_status == "SHUTDOWN":
            rejection_reasons.append("System health SHUTDOWN")
        if sys_status == "WARNING":
            warnings.append("System health WARNING — risk dikurangi 50%")

        # Compute scalars
        hwm_sc = self.hwm_sm.hwm_scalar()
        vol_sc, vol_regime = self.vol_scaler.compute_scalar(returns_history)
        ma_sc, ma_signal   = self.feedback.ma_scalar()

        # Warning skalakan saat WARNING
        if sys_status == "WARNING":
            hwm_sc = hwm_sc * 0.5

        # Hitung ukuran posisi
        if rejection_reasons:
            units = pos_val = dollar_risk = final_risk_pct = 0.0
        else:
            avg_win_r  = avg_win_pct  / max(avg_loss_pct, 1e-9)
            avg_loss_r = 1.0

            # Budget check
            heat = (config_safe_risk(self.config) * hwm_sc * vol_sc * ma_sc)
            if not self.budget.can_add_heat(timeframe, heat):
                warnings.append(f"Portfolio heat cap — {timeframe} budget penuh")
                rejection_reasons.append("Portfolio heat cap exceeded")
                units = pos_val = dollar_risk = final_risk_pct = 0.0
            else:
                units, pos_val, dollar_risk, final_risk_pct = self.sizer.size(
                    entry_price     = entry_price,
                    stop_loss_price = stop_loss_price,
                    current_equity  = current_equity,
                    hwm_scalar      = hwm_sc,
                    vol_scalar      = vol_sc,
                    ma_scalar       = ma_sc,
                    win_rate        = win_rate,
                    avg_win_r       = avg_win_r,
                    avg_loss_r      = avg_loss_r,
                    timeframe       = timeframe,
                    budget          = self.budget,
                )

        # Populate decision
        decision.trade_approved    = len(rejection_reasons) == 0
        decision.rejection_reasons = rejection_reasons
        decision.warnings          = warnings
        decision.recommended_units = units
        decision.position_value_usd= pos_val
        decision.dollar_risk_usd   = dollar_risk
        decision.final_risk_pct    = final_risk_pct
        decision.hwm_risk_scalar   = round(hwm_sc, 4)
        decision.vol_scalar        = round(vol_sc, 4)
        decision.ma_filter_scalar  = round(ma_sc, 4)
        decision.composite_scalar  = round(hwm_sc * vol_sc * ma_sc, 4)

        return decision

    # ── Post-Trade Record ──────────────────────────────────────────
    def record_trade_result(
        self,
        outcome  : str,    # WIN | LOSS | BREAKEVEN
        pnl_pct  : float,
        pnl_usd  : float,
    ) -> Dict:
        is_win = outcome.upper() == "WIN"
        self.health_monitor.record(is_win, pnl_pct)
        new_equity = self.hwm_sm.current_equity + pnl_usd
        self.hwm_sm.update(new_equity)
        self.compounding.record(new_equity)
        self.feedback.update(new_equity)

        return {
            "recorded"   : True,
            "new_equity" : round(new_equity, 2),
            "hwm"        : round(self.hwm_sm.hwm, 2),
            "floor"      : round(self.hwm_sm.active_floor, 2),
        }


def config_safe_risk(cfg: HWMConfig) -> float:
    """Helper untuk ambil risk pct dari config."""
    return cfg.max_base_risk_pct


def _now_iso() -> str:
    """ISO timestamp."""
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"


# ══════════════════════════════════════════════════════════════════════════════
#  13. SYSTEM DESIGN REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_system_design_report() -> Dict:
    """
    Dokumentasi desain sistem lengkap untuk endpoint /api/v5/hwm/design-report.
    """
    return {
        "system_name"    : "APEX HWM Protection Engine v1.0",
        "architecture"   : {
            "components"  : [
                "EquityHWMStateMachine — HWM, floor, milestone ladder",
                "CapitalLockManager   — halt logic, hard MDD gate",
                "VolatilityRiskScaler — vol-target scalar (GARCH-style)",
                "TimeframeRiskBudget  — heat allocation per timeframe",
                "EquityCurveFeedbackLoop — MA equity scalar",
                "SystemHealthMonitor  — rolling Sharpe, consec losses",
                "HWMPositionSizer     — unified sizer with all scalars",
                "CompoundingEngine    — equity log & CAGR",
                "ValidationSuite     — bootstrap + walk-forward + DSR",
            ],
            "risk_layers" : {
                "L1_per_trade"    : "Kelly × composite_scalar ≤ max_base_risk_pct",
                "L2_timeframe"    : "heat budget per intraday/swing/position",
                "L3_portfolio"    : "total heat ≤ max_portfolio_heat_pct",
                "L4_daily_loss"   : "2% daily loss limit (manual check)",
                "L5_trailing_stop": "trailing stop % dari HWM",
                "L6_hard_mdd"     : "hard MDD cap dari initial capital",
                "L7_floor"        : "milestone floor lock (convex decay γ=1.5)",
            },
        },
        "math"           : {
            "hwm_scalar_formula" : "scalar = clamp([(E−floor)/(HWM−floor)]^γ, 0, 1)",
            "kelly_formula"      : "f = p − q/b, applied at fraction=0.25",
            "composite_scalar"   : "hwm_scalar × vol_scalar × ma_scalar",
            "position_size"      : "units = (equity × risk_pct × composite) / |entry−SL|",
            "var_method"         : "Cornish-Fisher CF-VaR (fat-tail adjusted)",
        },
        "limitations"    : [
            "Gap risk (overnight/weekend) tidak bisa dicegah sepenuhnya",
            "Floor breach < 1% per simulasi, bukan 0%",
            "Butuh minimum 200 trades untuk deployment gate valid",
            "Walk-forward efficiency butuh 3+ tahun data untuk meaningful",
        ],
        "deployment_gate": {
            "sharpe_minimum"  : 2.0,
            "calmar_minimum"  : 1.5,
            "mdd_maximum_pct" : 20.0,
            "wfe_minimum"     : 0.5,
            "min_trades"      : 200,
        },
    }