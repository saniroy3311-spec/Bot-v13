from __future__ import annotations
"""
risk/guards.py — Bot v13  [NEW FILE 2026-09-05]

WHY THIS FILE EXISTS
────────────────────
Your .env contained an "ANTI-STREAK PROTECTION & CIRCUIT BREAKER" block:

    COOLDOWN_BARS=4
    MAX_CONSECUTIVE_LOSSES_PAUSE=2
    CONSECUTIVE_LOSS_PAUSE_MINUTES=45
    CONSECUTIVE_LOSS_SIZE_SCALE=true
    MIN_SCALE_LOTS=50
    DIRECTIONAL_LOCKOUT_MINUTES=30

None of those keys appeared anywhere in the codebase. They were read by nothing.
That is why the 2026-09-04 session shows re-entry ONE SECOND after a stop-out
(14:21:01 exit -> 14:21:02 entry) and fifteen consecutive losing longs between
14:18 and 17:27 with no pause at all.

This module implements them for real.

NOTE ON SIZE SCALING: scaling down after losses reduces the damage of a bad
streak. It does not make a losing strategy profitable. Treat it as damage
control, not as an edge.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from config import (
    COOLDOWN_BARS,
    MAX_CONSECUTIVE_LOSSES_PAUSE,
    CONSECUTIVE_LOSS_PAUSE_MINUTES,
    CONSECUTIVE_LOSS_SIZE_SCALE,
    MIN_SCALE_LOTS,
    DIRECTIONAL_LOCKOUT_MINUTES,
    CANDLE_TIMEFRAME,
)

logger = logging.getLogger("Guards")


def _tf_seconds(tf: str) -> int:
    """'3m' -> 180, '1h' -> 3600. Falls back to 180s."""
    try:
        tf = str(tf).strip().lower()
        unit, num = tf[-1], int(tf[:-1])
        return num * {"m": 60, "h": 3600, "d": 86400, "s": 1}[unit]
    except Exception:
        return 180


BAR_SECONDS = _tf_seconds(CANDLE_TIMEFRAME)


@dataclass
class TradeGuards:
    """
    Blocks new entries after losses. All state is in wall-clock seconds so it
    survives being checked from any callback.

    Call record_exit() after every closed trade and can_enter() before every
    entry. Persist/restore with to_dict()/from_dict() so a restart does not
    wipe an active pause.
    """

    consecutive_losses:  int   = 0
    last_exit_ts:        float = 0.0
    pause_until_ts:      float = 0.0
    # is_long -> unix ts until which that direction is locked out
    lockout_until:       dict  = field(default_factory=dict)

    # ── query ─────────────────────────────────────────────────────────────────

    def can_enter(self, is_long: bool, now: Optional[float] = None):
        """Returns (allowed: bool, reason: str)."""
        now = now if now is not None else time.time()

        if self.pause_until_ts > now:
            mins = (self.pause_until_ts - now) / 60.0
            return False, (
                f"circuit breaker active — {self.consecutive_losses} consecutive "
                f"losses, {mins:.1f} min remaining"
            )

        if COOLDOWN_BARS > 0 and self.last_exit_ts > 0:
            cooldown_end = self.last_exit_ts + COOLDOWN_BARS * BAR_SECONDS
            if cooldown_end > now:
                return False, (
                    f"cooldown — {(cooldown_end - now):.0f}s left "
                    f"({COOLDOWN_BARS} bars after last exit)"
                )

        until = self.lockout_until.get(bool(is_long), 0.0)
        if until > now:
            side = "LONG" if is_long else "SHORT"
            return False, (
                f"{side} locked out for {(until - now) / 60.0:.1f} more min "
                f"after a loss in this direction"
            )

        return True, "ok"

    def scaled_lots(self, base_lots: int) -> int:
        """Reduce size while a losing streak is in progress."""
        if not CONSECUTIVE_LOSS_SIZE_SCALE or self.consecutive_losses <= 0:
            return int(base_lots)
        # halve per consecutive loss, floored at MIN_SCALE_LOTS
        scaled = int(base_lots / (2 ** self.consecutive_losses))
        return max(int(MIN_SCALE_LOTS), min(int(base_lots), scaled))

    # ── update ────────────────────────────────────────────────────────────────

    def record_exit(self, is_long: bool, pnl: float, now: Optional[float] = None) -> None:
        now = now if now is not None else time.time()
        self.last_exit_ts = now

        if pnl < 0:
            self.consecutive_losses += 1

            if DIRECTIONAL_LOCKOUT_MINUTES > 0:
                self.lockout_until[bool(is_long)] = now + DIRECTIONAL_LOCKOUT_MINUTES * 60
                logger.warning(
                    f"[GUARD] {'LONG' if is_long else 'SHORT'} locked out for "
                    f"{DIRECTIONAL_LOCKOUT_MINUTES} min after a loss."
                )

            if (MAX_CONSECUTIVE_LOSSES_PAUSE > 0
                    and self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES_PAUSE):
                self.pause_until_ts = now + CONSECUTIVE_LOSS_PAUSE_MINUTES * 60
                logger.warning(
                    f"[GUARD] CIRCUIT BREAKER — {self.consecutive_losses} consecutive "
                    f"losses. Paused for {CONSECUTIVE_LOSS_PAUSE_MINUTES} min."
                )
        else:
            if self.consecutive_losses:
                logger.info(
                    f"[GUARD] Loss streak reset after {self.consecutive_losses} losses."
                )
            self.consecutive_losses = 0

    def reset_streak(self) -> None:
        self.consecutive_losses = 0
        self.pause_until_ts     = 0.0
        self.lockout_until.clear()

    # ── persistence ───────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "consecutive_losses": self.consecutive_losses,
            "last_exit_ts":       self.last_exit_ts,
            "pause_until_ts":     self.pause_until_ts,
            "lockout_until":      {str(k): v for k, v in self.lockout_until.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TradeGuards":
        g = cls()
        if not isinstance(d, dict):
            return g
        g.consecutive_losses = int(d.get("consecutive_losses", 0))
        g.last_exit_ts       = float(d.get("last_exit_ts", 0.0))
        g.pause_until_ts     = float(d.get("pause_until_ts", 0.0))
        g.lockout_until      = {
            (k == "True"): float(v) for k, v in (d.get("lockout_until") or {}).items()
        }
        return g
