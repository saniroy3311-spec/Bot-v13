import logging
import asyncio

logger = logging.getLogger(__name__)

class TrailMonitor:
    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        self._running = False
        self.pos = None

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False

    def set_position(self, pos: dict):
        self.pos = pos

    def clear_position(self):
        self.pos = None

    def push_ws_candle(self, candle: dict):
        pass

    async def push_delta_tick(self, tick: dict):
        pass

    async def on_price_tick(self, price: float):
        pass

    async def _fire_exit(self, reason: str, exit_price: float):
        pass
