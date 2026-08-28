
def calculate_directional_brackets(side, fill_price, risk_points, rr_multiple=3.65):
    fill_price = float(fill_price)
    risk_points = min(115.0, max(95.0, float(risk_points)))
    target_points = round(risk_points * float(rr_multiple), 1)
    
    if "LONG" in str(side).upper() or "BUY" in str(side).upper():
        sl = round(fill_price - risk_points, 1)
        tp = round(fill_price + target_points, 1)
    else:
        sl = round(fill_price + risk_points, 1)
        tp = round(fill_price - target_points, 1)
    return sl, tp

import datetime

class OrderManager:
    def __init__(self, config):
        self.config = config

    def create_bracket_order(self, side: str, strategy: str, current_price: float, sl_pts: float, tp_pts: float, lots: int, btc_size: float) -> dict:
        slippage = self.config.SLIPPAGE_PTS if side == 'LONG' else -self.config.SLIPPAGE_PTS
        fill_price = round(current_price + (slippage if self.config.PAPER_TRADING else 0.0), 2)
        
        # FIX: Correct SL/TP direction
        if side == 'LONG':
            sl_price = round(fill_price - sl_pts, 2)
            tp_price = round(fill_price + tp_pts, 2)
        else:
            sl_price = round(fill_price + sl_pts, 2)
            tp_price = round(fill_price - tp_pts, 2)

        return {
            'in_pos': True,
            'side': side,
            'strategy': strategy,
            'entry_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'),
            'entry_price': fill_price,
            'sl_price': sl_price,
            'tp_price': tp_price,
            'initial_sl_pts': sl_pts,
            'initial_tp_pts': tp_pts,
            'lots': lots,
            'size_btc': btc_size,
            'highest_p': fill_price,
            'lowest_p': fill_price,
            'is_be_locked': False,
            'current_trail_stage': 0
        }
