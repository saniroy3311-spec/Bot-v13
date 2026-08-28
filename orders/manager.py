import inspect
import datetime
import logging

logger = logging.getLogger(__name__)

try:
    import execution
    _BaseOrderManager = getattr(execution, 'OrderManager', object)
    build_exchange = getattr(execution, 'build_exchange', None)
except ImportError:
    _BaseOrderManager = object
    build_exchange = None


class OrderManager(_BaseOrderManager):
    def __init__(self, config=None, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(_BaseOrderManager, '__init__'):
            try:
                super().__init__(config=config, *args, **kwargs)
            except TypeError:
                try:
                    super().__init__(*args, **kwargs)
                except Exception:
                    pass
        if config is None:
            try:
                from config import Config
                self.config = Config()
            except Exception:
                self.config = None
        else:
            self.config = config

        if not hasattr(self, 'product_id'):
            self.product_id = 27
        if not hasattr(self, 'product_symbol'):
            self.product_symbol = 'BTCUSD'

    async def initialize(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'initialize'):
            try:
                res = super().initialize(*args, **kwargs)
                if inspect.isawaitable(res):
                    return await res
                return res
            except Exception as e:
                logger.warning(f"[OM] Base initialize warning: {e}")
        return True

    async def fetch_open_position(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'fetch_open_position'):
            try:
                res = super().fetch_open_position(*args, **kwargs)
                if inspect.isawaitable(res):
                    return await res
                return res
            except Exception as e:
                logger.warning(f"[OM] Base fetch_open_position warning: {e}")
        return None

    async def cancel_all_orders(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'cancel_all_orders'):
            try:
                res = super().cancel_all_orders(*args, **kwargs)
                if inspect.isawaitable(res):
                    return await res
                return res
            except Exception as e:
                logger.warning(f"[OM] Base cancel_all_orders warning: {e}")
        return []

    async def place_entry(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'place_entry'):
            res = super().place_entry(*args, **kwargs)
            if inspect.isawaitable(res):
                return await res
            return res
        return None

    async def close_position(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'close_position'):
            res = super().close_position(*args, **kwargs)
            if inspect.isawaitable(res):
                return await res
            return res
        return None

    async def update_bracket_sl(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'update_bracket_sl'):
            res = super().update_bracket_sl(*args, **kwargs)
            if inspect.isawaitable(res):
                return await res
            return res
        return None

    async def cancel_bracket(self, *args, **kwargs):
        if _BaseOrderManager is not object and hasattr(super(), 'cancel_bracket'):
            res = super().cancel_bracket(*args, **kwargs)
            if inspect.isawaitable(res):
                return await res
            return res
        return None

    def create_bracket_order(self, side: str, strategy: str, current_price: float, sl_pts: float, tp_pts: float, lots: int, btc_size: float) -> dict:
        slippage_pts = getattr(self.config, 'SLIPPAGE_PTS', 5.0) if self.config else 5.0
        paper_trading = getattr(self.config, 'PAPER_TRADING', False) if self.config else False
        
        slippage = slippage_pts if side == 'LONG' else -slippage_pts
        fill_price = round(current_price + (slippage if paper_trading else 0.0), 2)
        
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
