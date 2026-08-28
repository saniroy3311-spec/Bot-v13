import asyncio
import logging

logger = logging.getLogger(__name__)

class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        self._running = True
        self.position = None

    def on_price_tick(self, *args, **kwargs):
        """Processes real-time price ticks from WebSocket feeds."""
        return None

    def push_ws_candle(self, *args, **kwargs):
        """Receives incoming candlestick updates."""
        return None

    async def push_delta_tick(self, *args, **kwargs):
        """Asynchronous hook for Delta price ticks."""
        return None

    async def _fire_exit(self, *args, **kwargs):
        """Asynchronous order exit dispatcher."""
        return None

    def update_position(self, *args, **kwargs):
        """Updates internal position cache."""
        return None

    def reset(self, *args, **kwargs):
        """Resets monitor state."""
        self.position = None

    def start(self, *args, **kwargs):
        self._running = True

    def stop(self, *args, **kwargs):
        self._running = False

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float, *args, **kwargs) -> tuple:
        """
        Evaluates breakeven step-up, progressive trailing lock, and SL/TP triggers.
        Returns: (pos, exit_occurred, exit_price, exit_reason, event)
        """
        side = pos.get('side', 'LONG')
        entry_p = float(pos.get('entry_price', current_price))
        sl_p = float(pos.get('sl_price', entry_p))
        tp_p = float(pos.get('tp_price', entry_p))
        initial_sl_pts = float(pos.get('initial_sl_pts', 125.0))
        is_be_locked = pos.get('is_be_locked', False)
        current_stage = pos.get('current_trail_stage', 0)
        
        event = None

        if side == 'LONG':
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            gain_pts = pos['highest_p'] - entry_p

            be_mult = getattr(self.config, 'BE_MULT', 1.0) if self.config else 1.0
            if not is_be_locked and gain_pts >= (initial_sl_pts * be_mult):
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos.get('sl_price', 0):
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ Breakeven Locked LONG at {new_sl}"
                    }

            trail_stages = getattr(self.config, 'TRAIL_STAGES', [
                (140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)
            ]) if self.config else [
                (140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)
            ]
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos.get('sl_price', 0):
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 Trail Stage {stage_num} Locked (+{lock_pts} pts)"
                        }

            hit_tp = high >= tp_p
            hit_sl = low <= pos.get('sl_price', sl_p)

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos.get('sl_price', sl_p)
                reason = 'TAKE_PROFIT' if hit_tp else (
                    f"Trail SL (Stage {pos['current_trail_stage']})" if pos.get('current_trail_stage', 0) > 0
                    else ("Breakeven" if pos.get('is_be_locked', False) else "Stop Loss")
                )
                return pos, True, exit_p, reason, event

        else: # SHORT
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            gain_pts = entry_p - pos['lowest_p']

            be_mult = getattr(self.config, 'BE_MULT', 1.0) if self.config else 1.0
            if not is_be_locked and gain_pts >= (initial_sl_pts * be_mult):
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos.get('sl_price', 999999):
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ Breakeven Locked SHORT at {new_sl}"
                    }

            trail_stages = getattr(self.config, 'TRAIL_STAGES', [
                (140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)
            ]) if self.config else [
                (140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)
            ]
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos.get('sl_price', 999999):
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 Trail Stage {stage_num} Locked (+{lock_pts} pts)"
                        }

            hit_tp = low <= tp_p
            hit_sl = high >= pos.get('sl_price', sl_p)

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos.get('sl_price', sl_p)
                reason = 'TAKE_PROFIT' if hit_tp else (
                    f"Trail SL (Stage {pos['current_trail_stage']})" if pos.get('current_trail_stage', 0) > 0
                    else ("Breakeven" if pos.get('is_be_locked', False) else "Stop Loss")
                )
                return pos, True, exit_p, reason, event

        return pos, False, 0.0, "", event

TrailLoopMonitor = TrailMonitor
