import datetime

class OrderManager:
    def __init__(self, config=None):
        if config is None:
            try:
                from config import Config
                self.config = Config()
            except Exception:
                try:
                    import config
                    self.config = config
                except Exception:
                    self.config = None
        else:
            self.config = config

    async def initialize(self):
        """Async lifecycle hook required by main.py"""
        return True

    def create_bracket_order(self, side: str, strategy: str, current_price: float, sl_pts: float, tp_pts: float, lots: int, btc_size: float) -> dict:
        """
        Creates an initialized position state with proper fill, SL, and TP brackets.
        LONG:  SL = fill - sl_pts, TP = fill + tp_pts
        SHORT: SL = fill + sl_pts, TP = fill - tp_pts
        """
        is_paper = getattr(self.config, 'PAPER_TRADING', False) if self.config else False
        slippage = getattr(self.config, 'SLIPPAGE_PTS', 0.0) if self.config else 0.0

        side_upper = str(side).upper().strip()
        if side_upper in ('LONG', 'BUY'):
            pos_side = 'LONG'
            fill_price = round(current_price + (slippage if is_paper else 0.0), 2)
            sl_price = round(fill_price - sl_pts, 2)
            tp_price = round(fill_price + tp_pts, 2)
        else:
            pos_side = 'SHORT'
            fill_price = round(current_price - (slippage if is_paper else 0.0), 2)
            sl_price = round(fill_price + sl_pts, 2)
            tp_price = round(fill_price - tp_pts, 2)

        return {
            'in_pos': True,
            'side': pos_side,
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
