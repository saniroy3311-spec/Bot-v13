"""
orders/manager.py — Bot v13
Re-exports OrderManager, build_exchange, and TrailMonitor from execution.py.

FIX: main.py imports `from orders.manager import OrderManager, build_exchange`.
The production OrderManager class (with initialize(), place_entry(),
fetch_open_position(), cancel_all_orders(), close_exchange()) lives in
execution.py. This shim exposes it under the expected import path so main.py
works without any changes.

DO NOT overwrite this file with a stub — main.py depends on the full class.
"""
from execution import (
    OrderManager,
    build_exchange,
    calculate_directional_brackets,
)

# TrailMonitor also lives in execution.py; expose it here for anything that
# still imports it from orders.manager.
try:
    from execution import TrailMonitor
except ImportError:
    pass

__all__ = [
    "OrderManager",
    "build_exchange",
    "calculate_directional_brackets",
    "TrailMonitor",
]
