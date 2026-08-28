import datetime

class OrderManager:
    def __init__(self, config=None):
        if config is None:
            from config import Config
            self.config = Config()
        else:
            self.config = config

    def create_bracket_order(self, side: str, strategy: str, current_price: float, sl_pts: float, tp_pts: float, lots: int, btc_size: float) -> dict:
        """
        Initializes position state with correct non-inverted SL/TP brackets.
        """
        slippage = self.config.SLIPPAGE_PTS if side == 'LONG' else -self.config.SLIPPAGE_PTS
        fill_price = round(current_price + (slippage if getattr(self.config, 'PAPER_TRADING', False) else 0.0), 2)
        
        if side == 'LONG':
            sl_price = round(fill_price - sl_pts, 2)
            tp_price = round(fill_price + tp_pts, 2)
        else: # SHORT
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
