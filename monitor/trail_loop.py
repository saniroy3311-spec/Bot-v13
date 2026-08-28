class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float) -> tuple:
        """
        Updates position state with high/low tracking, breakeven step-up,
        5-stage progressive trailing lock, and evaluates exit triggers.
        Returns: (updated_pos, exit_occurred, exit_price, exit_reason, notification_event)
        """
        side = pos['side']
        entry_p = pos['entry_price']
        sl_p = pos['sl_price']
        tp_p = pos['tp_price']
        initial_sl_pts = pos.get('initial_sl_pts', 115.0)
        is_be_locked = pos.get('is_be_locked', False)
        current_stage = pos.get('current_trail_stage', 0)
        
        trail_stages = getattr(self.config, 'TRAIL_STAGES', [
            (140.0, 30.0),
            (220.0, 100.0),
            (300.0, 180.0),
            (380.0, 260.0),
            (450.0, 340.0)
        ])
        
        event = None

        if side == 'LONG':
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            gain_pts = pos['highest_p'] - entry_p

            # 1. Breakeven Step-up (When gain >= 1.0x initial risk)
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ *BREAKEVEN LOCKED*\n• Side: *LONG*\n• Locked SL: `${new_sl:,.2f}` (+15 pts above entry `${entry_p:,.2f}`)"
                    }

            # 2. 5-Stage Dynamic Profit Locks
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 *TRAIL LOCK STAGE {stage_num} ACTIVATED*\n• Gain: `+{gain_pts:.1f} pts` (Trigger: +{trig_pts:.0f} pts)\n• Trailing SL moved to: `${new_trail_sl:,.2f}` (+{lock_pts:.0f} pts locked profit)"
                        }

            # 3. Check Exits (Take Profit or Stop Loss)
            hit_tp = high >= tp_p
            hit_sl = low <= pos['sl_price']

            if hit_tp or hit_sl:
                if hit_tp:
                    exit_p = tp_p
                    exit_reason = 'TAKE_PROFIT'
                else:
                    exit_p = pos['sl_price']
                    if pos.get('current_trail_stage', 0) > 0:
                        exit_reason = f"Trail SL (Stage {pos['current_trail_stage']})"
                    elif pos.get('is_be_locked', False):
                        exit_reason = 'Breakeven (Fee Protected)'
                    else:
                        exit_reason = 'Stop Loss'
                return pos, True, exit_p, exit_reason, event

        else: # SHORT
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high)
            gain_pts = entry_p - pos['lowest_p']

            # 1. Breakeven Step-up
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ *BREAKEVEN LOCKED*\n• Side: *SHORT*\n• Locked SL: `${new_sl:,.2f}` (-15 pts below entry `${entry_p:,.2f}`)"
                    }

            # 2. 5-Stage Dynamic Profit Locks
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 *TRAIL LOCK STAGE {stage_num} ACTIVATED*\n• Gain: `+{gain_pts:.1f} pts` (Trigger: +{trig_pts:.0f} pts)\n• Trailing SL moved to: `${new_trail_sl:,.2f}` (+{lock_pts:.0f} pts locked profit)"
                        }

            # 3. Check Exits
            hit_tp = low <= tp_p
            hit_sl = high >= pos['sl_price']

            if hit_tp or hit_sl:
                if hit_tp:
                    exit_p = tp_p
                    exit_reason = 'TAKE_PROFIT'
                else:
                    exit_p = pos['sl_price']
                    if pos.get('current_trail_stage', 0) > 0:
                        exit_reason = f"Trail SL (Stage {pos['current_trail_stage']})"
                    elif pos.get('is_be_locked', False):
                        exit_reason = 'Breakeven (Fee Protected)'
                    else:
                        exit_reason = 'Stop Loss'
                return pos, True, exit_p, exit_reason, event

        return pos, False, 0.0, "", event

# Backward compatibility alias
TrailLoopMonitor = TrailMonitor
