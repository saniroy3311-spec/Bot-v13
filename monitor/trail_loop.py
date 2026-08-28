from typing import Optional, Tuple, Dict, Any

class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config

    async def initialize(self):
        """Async lifecycle hook required by main.py"""
        return True

    def evaluate_trailing_and_exits(self, pos: dict, current_price: float, high: float, low: float) -> Tuple[dict, bool, Optional[float], Optional[str], Optional[dict]]:
        """
        Evaluates position high/low tracking, breakeven step-up, 5-stage progressive trailing,
        and stop loss / take profit exits.
        Returns: (pos, exit_occurred, exit_price, exit_reason, event)
        """
        if not pos or not pos.get('in_pos', False):
            return pos, False, None, None, None

        side = str(pos.get('side', 'LONG')).upper().strip()
        entry_p = float(pos.get('entry_price', current_price))
        tp_p = float(pos.get('tp_price', entry_p))
        initial_sl_pts = float(pos.get('initial_sl_pts', 115.0))
        is_be_locked = pos.get('is_be_locked', False)
        current_stage = pos.get('current_trail_stage', 0)

        # 5-Stage Trailing Thresholds (Trigger Pts, Lock Pts)
        trail_stages = [
            (140.0, 30.0),
            (220.0, 100.0),
            (300.0, 180.0),
            (380.0, 260.0),
            (450.0, 340.0)
        ]

        event = None

        if side in ('LONG', 'BUY'):
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high, current_price)
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low, current_price)
            gain_pts = pos['highest_p'] - entry_p

            # 1. Breakeven Lock (Triggered when gain >= 1.0x initial SL risk)
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p + 15.0, 2)
                if new_sl > pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ <b>BREAKEVEN LOCKED</b> (LONG)\n• Locked SL: <code>${new_sl:,.2f}</code> (+15 pts above entry <code>${entry_p:,.2f}</code>)"
                    }

            # 2. Asymmetric 5-Stage Profit Locks
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p + lock_pts, 2)
                    if new_trail_sl > pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 <b>TRAIL STAGE {stage_num} ACTIVATED</b>\n• Gain: <code>+{gain_pts:.1f} pts</code>\n• SL moved to: <code>${new_trail_sl:,.2f}</code> (+{lock_pts:.0f} pts locked)"
                        }

            # 3. Check Exits (Take Profit or Stop Loss / Trail SL)
            if high >= tp_p:
                pos['in_pos'] = False
                return pos, True, tp_p, 'TAKE_PROFIT', event

            curr_sl = pos['sl_price']
            if low <= curr_sl:
                pos['in_pos'] = False
                stage = pos.get('current_trail_stage', 0)
                reason = f'Trail SL (Stage {stage})' if stage > 0 else ('Breakeven SL' if pos.get('is_be_locked') else 'STOP_LOSS')
                return pos, True, curr_sl, reason, event

        else:  # SHORT / SELL
            pos['lowest_p'] = min(pos.get('lowest_p', entry_p), low, current_price)
            pos['highest_p'] = max(pos.get('highest_p', entry_p), high, current_price)
            gain_pts = entry_p - pos['lowest_p']

            # 1. Breakeven Lock (Triggered when drop >= 1.0x initial SL risk)
            if not is_be_locked and gain_pts >= initial_sl_pts:
                pos['is_be_locked'] = True
                new_sl = round(entry_p - 15.0, 2)
                if new_sl < pos['sl_price']:
                    pos['sl_price'] = new_sl
                    event = {
                        'type': 'BREAKEVEN_LOCK',
                        'text': f"🛡️ <b>BREAKEVEN LOCKED</b> (SHORT)\n• Locked SL: <code>${new_sl:,.2f}</code> (-15 pts below entry <code>${entry_p:,.2f}</code>)"
                    }

            # 2. Asymmetric 5-Stage Profit Locks
            for s_idx, (trig_pts, lock_pts) in enumerate(trail_stages):
                stage_num = s_idx + 1
                if gain_pts >= trig_pts and current_stage < stage_num:
                    pos['current_trail_stage'] = stage_num
                    new_trail_sl = round(entry_p - lock_pts, 2)
                    if new_trail_sl < pos['sl_price']:
                        pos['sl_price'] = new_trail_sl
                        event = {
                            'type': f'TRAIL_STAGE_{stage_num}',
                            'text': f"🔒 <b>TRAIL STAGE {stage_num} ACTIVATED</b>\n• Gain: <code>+{gain_pts:.1f} pts</code>\n• SL moved to: <code>${new_trail_sl:,.2f}</code> (-{lock_pts:.0f} pts locked)"
                        }

            # 3. Check Exits (Take Profit or Stop Loss / Trail SL)
            if low <= tp_p:
                pos['in_pos'] = False
                return pos, True, tp_p, 'TAKE_PROFIT', event

            curr_sl = pos['sl_price']
            if high >= curr_sl:
                pos['in_pos'] = False
                stage = pos.get('current_trail_stage', 0)
                reason = f'Trail SL (Stage {stage})' if stage > 0 else ('Breakeven SL' if pos.get('is_be_locked') else 'STOP_LOSS')
                return pos, True, curr_sl, reason, event

        return pos, False, None, None, event

TrailLoopMonitor = TrailMonitor
