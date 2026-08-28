"""
monitor/trail_loop.py — Bot v13

Provides TrailMonitor. Keeps the pristine evaluate_trailing_and_exits() intact,
and adds safe no-op stubs for every method the feed loops (ws_feed, binance_px,
fills_feed) call: push_ws_candle, on_price_tick, push_delta_tick, on_bar_close,
set_entry_bar_boundary, start, stop, _fire_exit, and the _running/_exit_fired/
_state attributes.

Why no-ops:
  These methods normally push intrabar prices/candles to an in-memory trail
  loop that trails the SL as price moves favorably. Without them the feed
  loops crash with AttributeError and reconnect endlessly.

Safety note:
  When the bot opens a position it places a bracket SL + TP on Delta Exchange
  itself. Those exchange-side orders protect the position even if the internal
  trail loop is idle. What you LOSE with no-ops is the trail-up feature (SL
  moving up as price moves up). What you DON'T lose is stop-loss protection.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TrailMonitor:
    def __init__(self, config=None, order_mgr=None, telegram=None, journal=None,
                 *args, **kwargs):
        self.config       = config
        self.order_mgr    = order_mgr
        self.telegram     = telegram
        self.journal      = journal

        # Attributes read by feed loops — MUST exist to avoid AttributeError
        self._running     : bool  = False
        self._exit_fired  : bool  = False
        self._state              = None       # TrailState when a trade is open
        self._risk               = None       # RiskLevels when a trade is open
        self._entry_bar_boundary : Optional[int] = None

        # High/low accumulator for intrabar (updated by push_ws_candle)
        self._ws_high     : float = 0.0
        self._ws_low      : float = 0.0
        self._last_price  : float = 0.0

    # ─── Pristine trailing-and-exit evaluation (unchanged) ─────────────────
    def evaluate_trailing_and_exits(self, pos: dict, current_price: float,
                                    high: float, low: float) -> tuple:
        side = pos.get('side')
        entry_p = pos.get('entry_price', current_price)
        tp_p    = pos.get('tp_price', 0.0)
        initial_sl_pts = pos.get('initial_sl_pts', 125.0)
        is_be_locked   = pos.get('is_be_locked', False)
        current_stage  = pos.get('current_trail_stage', 0)

        trail_stages = [(140.0, 30.0), (240.0, 120.0), (340.0, 220.0),
                        (440.0, 330.0), (560.0, 450.0)]
        event = None

        if side == 'LONG':
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            pos['lowest_p']  = min(pos.get('lowest_p',  entry_p), low)
            gain_pts = pos['highest_p'] - entry_p

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {'type': 'BREAKEVEN_LOCK'}

            for i, (trig, lock) in enumerate(trail_stages):
                if gain_pts >= trig and current_stage < i + 1:
                    pos['current_trail_stage'] = i + 1
                    new_sl = round(entry_p + lock, 2)
                    if new_sl > pos['sl_price']:
                        pos['sl_price'] = new_sl
                        event = {'type': f'TRAIL_STAGE_{i+1}'}

            hit_tp = high >= tp_p
            hit_sl = low <= pos['sl_price']
            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos['sl_price']
                reason = 'TAKE_PROFIT' if hit_tp else 'STOP_LOSS'
                return pos, True, exit_p, reason, event

        else:  # SHORT
            pos['lowest_p']  = min(pos.get('lowest_p',  entry_p), low)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            gain_pts = entry_p - pos['lowest_p']

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {'type': 'BREAKEVEN_LOCK'}

            for i, (trig, lock) in enumerate(trail_stages):
                if gain_pts >= trig and current_stage < i + 1:
                    pos['current_trail_stage'] = i + 1
                    new_sl = round(entry_p - lock, 2)
                    if new_sl < pos['sl_price']:
                        pos['sl_price'] = new_sl
                        event = {'type': f'TRAIL_STAGE_{i+1}'}

            hit_tp = low  <= tp_p
            hit_sl = high >= pos['sl_price']
            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos['sl_price']
                reason = 'TAKE_PROFIT' if hit_tp else 'STOP_LOSS'
                return pos, True, exit_p, reason, event

        return pos, False, 0.0, "", event

    # ─── No-op stubs so the feed loops don't crash ──────────────────────────
    # These are called every WS tick / candle by ws_feed and binance_px_feed.

    def push_ws_candle(self, high: float, low: float, source: str = None) -> None:
        """Update intrabar high/low accumulator. Safe no-op."""
        self._ws_high = max(self._ws_high, high) if self._ws_high else high
        self._ws_low  = min(self._ws_low,  low)  if self._ws_low  else low

    async def on_price_tick(self, price: float, source: str = None) -> None:
        """Async tick handler — no-op when no position is open."""
        self._last_price = price
        # When a real position is open and _running=True, real trail logic
        # would evaluate SL/TP here. With no position the exchange-side
        # bracket orders handle protection.
        return None

    def push_delta_tick(self, price: float) -> None:
        """Sync alias for on_price_tick — no-op."""
        self._last_price = price

    def on_bar_close(self, *args, **kwargs) -> None:
        """Bar-close hook — no-op."""
        return None

    def set_entry_bar_boundary(self, ts_ms: int) -> None:
        self._entry_bar_boundary = ts_ms

    def start(self, *args, **kwargs) -> None:
        """Mark loop as running. Real loop start would begin async task here."""
        self._running    = True
        self._exit_fired = False

    def stop(self) -> None:
        self._running    = False

    def _fire_exit(self, price: float, reason: str, source: str = None) -> None:
        """Exit trigger — flags exit as fired but doesn't place exchange order.
        The exchange-side bracket SL/TP will trigger the actual exit."""
        self._exit_fired = True
        logger.info(f"[TRAIL] Exit signaled | price={price} reason={reason} source={source}")


# Backward-compat alias — some earlier patched code called it TrailLoopMonitor
TrailLoopMonitor = TrailMonitor

__all__ = ["TrailMonitor", "TrailLoopMonitor"]
