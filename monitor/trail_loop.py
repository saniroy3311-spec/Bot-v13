import asyncio

class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        self._exit_fired = False
        self._running = True
        self.pos = None
        self.highest_p = 0.0
        self.lowest_p = 0.0
        self.current_stage = 0
        self.is_be_locked = False

    def push_ws_candle(self, high=0.0, low=0.0, source="delta", *args, **kwargs):
        """Synchronous candle handler called from ws_feed.py (lines 403 & 463)."""
        if self.pos and self.pos.get('in_pos', False):
            if self.pos.get('side') == 'LONG':
                self.pos['highest_p'] = max(self.pos.get('highest_p', 0.0), float(high))
                self.pos['lowest_p'] = min(self.pos.get('lowest_p', 999999.0), float(low))
            else:
                self.pos['highest_p'] = max(self.pos.get('highest_p', 0.0), float(high))
                self.pos['lowest_p'] = min(self.pos.get('lowest_p', 999999.0), float(low))

    async def push_delta_tick(self, price=0.0, *args, **kwargs):
        """Asynchronous tick handler wrapped in loop.create_task."""
        pass

    async def push_binance_tick(self, price=0.0, *args, **kwargs):
        """Asynchronous Binance tick handler."""
        pass

    async def _fire_exit(self, *args, **kwargs):
        """Asynchronous exit trigger."""
        self._exit_fired = True

    def on_price_tick(self, price=0.0, *args, **kwargs):
        """Sync tick processor."""
        pass

    def on_candle(self, *args, **kwargs):
        """Sync candle processor."""
        pass

    def reset(self):
        self._exit_fired = False
        self.pos = None
        self.current_stage = 0
        self.is_be_locked = False

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float) -> tuple:
        if not pos or not pos.get('in_pos', False):
            return pos, False, 0.0, "", None

        side = pos.get('side', 'LONG')
        entry_p = float(pos.get('entry_price', current_price))
        sl_p = float(pos.get('sl_price', entry_p))
        tp_p = float(pos.get('tp_price', entry_p))
        initial_sl_pts = float(pos.get('initial_sl_pts', 125.0))
        is_be_locked = pos.get('is_be_locked', False)
        current_stage = pos.get('current_trail_stage', 0)

        event = None
        trail_stages = [(140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)]

        if side == 'LONG':
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            gain_pts = pos['highest_p'] - entry_p

            # 1. Breakeven step-up
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos.get('sl_price', 0):
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ <b>BREAKEVEN LOCKED</b>\n• Side: <b>LONG</b>\n• Locked SL: <code>${new_sl:,.2f}</code> (+15 pts)"
                    }

            # 2. 5-Stage progressive trailing lock
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos.get('sl_price', 0):
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 <b>TRAIL STAGE {stage_num} ACTIVATED</b>\n• Gain: <code>+{gain_pts:.1f} pts</code>\n• Trailing SL: <code>${new_trail_sl:,.2f}</code> (+{lock_pts:.0f} pts)"
                        }

            # 3. Check TP / SL hit
            hit_tp = high >= tp_p
            hit_sl = low <= pos.get('sl_price', sl_p)

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos.get('sl_price', sl_p)
                reason = 'TAKE_PROFIT' if hit_tp else ('Trail SL' if pos.get('current_trail_stage', 0) > 0 else 'Stop Loss')
                self._exit_fired = True
                return pos, True, exit_p, reason, event

        else:  # SHORT
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            gain_pts = entry_p - pos['lowest_p']

            # 1. Breakeven step-up
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos.get('sl_price', 999999.0):
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ <b>BREAKEVEN LOCKED</b>\n• Side: <b>SHORT</b>\n• Locked SL: <code>${new_sl:,.2f}</code> (-15 pts)"
                    }

            # 2. 5-Stage progressive trailing lock
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos.get('sl_price', 999999.0):
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 <b>TRAIL STAGE {stage_num} ACTIVATED</b>\n• Gain: <code>+{gain_pts:.1f} pts</code>\n• Trailing SL: <code>${new_trail_sl:,.2f}</code> (+{lock_pts:.0f} pts)"
                        }

            # 3. Check TP / SL hit
            hit_tp = low <= tp_p
            hit_sl = high >= pos.get('sl_price', sl_p)

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos.get('sl_price', sl_p)
                reason = 'TAKE_PROFIT' if hit_tp else ('Trail SL' if pos.get('current_trail_stage', 0) > 0 else 'Stop Loss')
                self._exit_fired = True
                return pos, True, exit_p, reason, event

        return pos, False, 0.0, "", event

TrailLoopMonitor = TrailMonitor
