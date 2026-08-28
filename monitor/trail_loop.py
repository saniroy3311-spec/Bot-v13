class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        self._running = True

    async def push_binance_tick(self, *args, **kwargs):
        pass

    async def push_delta_tick(self, *args, **kwargs):
        pass

    async def push_ws_candle(self, *args, **kwargs):
        pass

    async def on_price_tick(self, *args, **kwargs):
        pass

    async def on_candle(self, *args, **kwargs):
        pass

    async def _fire_exit(self, *args, **kwargs):
        pass

    async def run(self, *args, **kwargs):
        pass

    def stop(self, *args, **kwargs):
        self._running = False

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float) -> tuple:
        if not pos or not pos.get("in_pos", True):
            return pos, False, 0.0, "", None

        side = pos.get("side", "LONG")
        entry_p = float(pos.get("entry_price", current_price))
        sl_p = float(pos.get("sl_price", entry_p))
        tp_p = float(pos.get("tp_price", entry_p))
        initial_sl_pts = float(pos.get("initial_sl_pts", 125.0))
        is_be_locked = pos.get("is_be_locked", False)
        current_stage = pos.get("current_trail_stage", 0)
        
        trail_stages = [
            (140.0, 30.0),
            (240.0, 120.0),
            (340.0, 220.0),
            (440.0, 330.0),
            (560.0, 450.0)
        ]
        
        event = None

        if side == "LONG":
            pos["highest_p"] = max(pos.get("highest_p", entry_p), high)
            pos["lowest_p"] = min(pos.get("lowest_p", entry_p), low)
            gain_pts = pos["highest_p"] - entry_p

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos["is_be_locked"] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos.get("sl_price", 0):
                    pos["sl_price"] = new_sl
                    event = {
                        "type": "BREAKEVEN_LOCK",
                        "text": f"🛡️ BREAKEVEN LOCKED\n• Side: LONG\n• Locked SL: ${new_sl:,.2f}"
                    }

            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos["current_trail_stage"] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos.get("sl_price", 0):
                        pos["sl_price"] = new_trail_sl
                        event = {
                            "type": f"TRAIL_STAGE_{stage_num}",
                            "text": f"🔒 TRAIL STAGE {stage_num} ACTIVATED\n• Gain: +{gain_pts:.1f} pts\n• Trailing SL: ${new_trail_sl:,.2f}"
                        }

            hit_tp = high >= tp_p
            hit_sl = low <= pos.get("sl_price", sl_p)

            if hit_tp or hit_sl:
                if hit_tp:
                    exit_p = tp_p
                    exit_reason = "TAKE_PROFIT"
                else:
                    exit_p = pos.get("sl_price", sl_p)
                    cur_st = pos.get("current_trail_stage", 0)
                    if cur_st > 0:
                        exit_reason = f"Trail SL (Stage {cur_st})"
                    elif pos.get("is_be_locked", False):
                        exit_reason = "Breakeven (Fee Protected)"
                    else:
                        exit_reason = "Stop Loss"
                return pos, True, exit_p, exit_reason, event

        else:
            pos["lowest_p"] = min(pos.get("lowest_p", entry_p), low)
            pos["highest_p"] = max(pos.get("highest_p", entry_p), high)
            gain_pts = entry_p - pos["lowest_p"]

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos["is_be_locked"] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos.get("sl_price", 999999):
                    pos["sl_price"] = new_sl
                    event = {
                        "type": "BREAKEVEN_LOCK",
                        "text": f"🛡️ BREAKEVEN LOCKED\n• Side: SHORT\n• Locked SL: ${new_sl:,.2f}"
                    }

            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos["current_trail_stage"] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos.get("sl_price", 999999):
                        pos["sl_price"] = new_trail_sl
                        event = {
                            "type": f"TRAIL_STAGE_{stage_num}",
                            "text": f"🔒 TRAIL STAGE {stage_num} ACTIVATED\n• Gain: +{gain_pts:.1f} pts\n• Trailing SL: ${new_trail_sl:,.2f}"
                        }

            hit_tp = low <= tp_p
            hit_sl = high >= pos.get("sl_price", sl_p)

            if hit_tp or hit_sl:
                if hit_tp:
                    exit_p = tp_p
                    exit_reason = "TAKE_PROFIT"
                else:
                    exit_p = pos.get("sl_price", sl_p)
                    cur_st = pos.get("current_trail_stage", 0)
                    if cur_st > 0:
                        exit_reason = f"Trail SL (Stage {cur_st})"
                    elif pos.get("is_be_locked", False):
                        exit_reason = "Breakeven (Fee Protected)"
                    else:
                        exit_reason = "Stop Loss"
                return pos, True, exit_p, exit_reason, event

        return pos, False, 0.0, "", event

TrailLoopMonitor = TrailMonitor
