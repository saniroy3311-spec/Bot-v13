"""WebSocket auto-reconnect."""
import asyncio
import logging
import random
import time
logger = logging.getLogger("feed.ws_autoreconnect")

class AutoReconnectingWS:
    def __init__(self, config):
        self.config = config
        self.ws = None
        self.running = False
        self.reconnect_count = 0
        self.reconnect_times = []

    async def run_forever(self, connect_fn, listen_fn):
        self.running = True
        consecutive_failures = 0
        while self.running:
            try:
                logger.info("[WS] Connecting...")
                self.ws = await connect_fn()
                self.reconnect_count += 1
                self.reconnect_times.append(time.time())
                cutoff = time.time() - 3600
                self.reconnect_times = [t for t in self.reconnect_times if t > cutoff]
                if len(self.reconnect_times) > self.config.WS_MAX_RECONNECTS_PER_HOUR:
                    logger.critical(f"[WS] Too many reconnects: {len(self.reconnect_times)}/hour")
                logger.info(f"[WS] Connected (reconnect #{self.reconnect_count})")
                consecutive_failures = 0
                await listen_fn(self.ws)
            except asyncio.CancelledError:
                self.running = False
                break
            except (ConnectionError, TimeoutError, OSError) as e:
                consecutive_failures += 1
                delay = self._backoff(consecutive_failures)
                logger.warning(f"[WS] Error: {e}. Reconnecting in {delay}s")
                await asyncio.sleep(delay)
            except Exception as e:
                consecutive_failures += 1
                delay = self._backoff(consecutive_failures) * 2
                logger.error(f"[WS] Unexpected: {e}. Reconnecting in {delay}s", exc_info=True)
                await asyncio.sleep(delay)

    def _backoff(self, failures):
        base = self.config.WS_RECONNECT_MIN_DELAY
        max_d = self.config.WS_RECONNECT_MAX_DELAY
        delay = min(base * (2 ** (failures - 1)), max_d)
        jitter = random.uniform(0, delay * 0.25)
        return int(delay + jitter)

    def stop(self):
        self.running = False
