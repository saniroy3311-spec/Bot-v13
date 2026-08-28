class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float) -> tuple:
        side = pos['side']
        entry_p = pos['entry_price']
        sl_p = pos['sl_price']
        tp_p = pos['tp_price']
        initial_sl_pts = pos.get('initial_sl_pts', 125.0)
        is_be_locked = pos.get('is_be_locked', False)
        current_stage = pos.get('current_trail_stage', 0)
        
        trail_stages = [(140.0, 30.0), (240.0, 120.0), (340.0, 220.0), (440.0, 330.0), (560.0, 450.0)]
        event = None

        if side == 'LONG':
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            gain_pts = pos['highest_p'] - entry_p

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {'type': 'BREAKEVEN_LOCK', 'text': f"🛡️ <b>BREAKEVEN LOCKED</b> (LONG)\nSL moved to: <code>${new_sl:,.2f}</code> (+15 pts)"}

            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {'type': f'TRAIL_STAGE_{stage_num}', 'text': f"🔒 <b>TRAIL STAGE {stage_num} LOCKED</b>\nGain: <code>+{gain_pts:.1f} pts</code>\nSL: <code>${new_trail_sl:,.2f}</code> (+{lock_pts:.0f} pts)"}

            hit_tp = high >= tp_p
            hit_sl = low <= pos['sl_price']

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos['sl_price']
                exit_reason = 'TAKE_PROFIT' if hit_tp else (f"Trail SL (Stage {pos.get('current_trail_stage', 0)})" if pos.get('current_trail_stage', 0) > 0 else ('Breakeven' if pos.get('is_be_locked') else 'Stop Loss'))
                return pos, True, exit_p, exit_reason, event

        else: # SHORT
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            gain_pts = entry_p - pos['lowest_p']

            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {'type': 'BREAKEVEN_LOCK', 'text': f"🛡️ <b>BREAKEVEN LOCKED</b> (SHORT)\nSL moved to: <code>${new_sl:,.2f}</code> (-15 pts)"}

            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {'type': f'TRAIL_STAGE_{stage_num}', 'text': f"🔒 <b>TRAIL STAGE {stage_num} LOCKED</b>\nGain: <code>+{gain_pts:.1f} pts</code>\nSL: <code>${new_trail_sl:,.2f}</code> (+{lock_pts:.0f} pts)"}

            hit_tp = low <= tp_p
            hit_sl = high >= pos['sl_price']

            if hit_tp or hit_sl:
                exit_p = tp_p if hit_tp else pos['sl_price']
                exit_reason = 'TAKE_PROFIT' if hit_tp else (f"Trail SL (Stage {pos.get('current_trail_stage', 0)})" if pos.get('current_trail_stage', 0) > 0 else ('Breakeven' if pos.get('is_be_locked') else 'Stop Loss'))
                return pos, True, exit_p, exit_reason, event

        return pos, False, 0.0, "", event

TrailLoopMonitor = TrailMonitor
