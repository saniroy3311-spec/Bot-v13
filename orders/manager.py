"""
orders/manager.py — Bot v13
Shim that re-exports OrderManager from execution.py AND adds the methods
main.py expects but the pristine execution.py doesn't provide.

Bug this file fixes:
    main.py calls self._order_mgr.fetch_open_position() and .cancel_all_orders()
    but execution.py's OrderManager only defines fetch_position() and has no
    cancel-all method. This shim monkey-patches those two names onto the class
    so main.py imports work without touching execution.py or main.py.
"""
from execution import (
    OrderManager as _BaseOrderManager,
    build_exchange,
    calculate_directional_brackets,
    _retry,
)

try:
    from execution import TrailMonitor
except ImportError:
    TrailMonitor = None

# ─── Add the two missing methods main.py expects ──────────────────────────────

async def _fetch_open_position(self):
    """Alias main.py expects — delegates to pristine fetch_position()."""
    return await self.fetch_position()


async def _cancel_all_orders(self):
    """Cancel every open order for SYMBOL. Safe to call when there are none."""
    from config import SYMBOL
    try:
        orders = await _retry(lambda: self.exchange.fetch_open_orders(SYMBOL))
    except Exception:
        return
    for order in orders or []:
        oid = order.get("id")
        if not oid:
            continue
        try:
            await _retry(lambda oid=oid: self.exchange.cancel_order(oid, SYMBOL))
        except Exception:
            pass


# Attach onto the class so every instance has them
_BaseOrderManager.fetch_open_position = _fetch_open_position
_BaseOrderManager.cancel_all_orders   = _cancel_all_orders

# Re-export under the canonical name
OrderManager = _BaseOrderManager

__all__ = [
    "OrderManager",
    "build_exchange",
    "calculate_directional_brackets",
    "TrailMonitor",
]
