"""Graceful shutdown handler."""
import asyncio
import logging
import signal
import sys
logger = logging.getLogger("infra.shutdown")

class GracefulShutdown:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.shutdown_initiated = False
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        def _handler(signum, frame):
            logger.warning(f"[SHUTDOWN] Received signal {signum}")
            asyncio.ensure_future(self.initiate_shutdown())
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, _handler)
        logger.info("[SHUTDOWN] Signal handlers registered")

    async def initiate_shutdown(self):
        if self.shutdown_initiated:
            return
        self.shutdown_initiated = True
        logger.info("[SHUTDOWN] ========== GRACEFUL SHUTDOWN STARTED ==========")
        try:
            if hasattr(self.bot, "orders_manager") and self.bot.orders_manager:
                try:
                    await self.bot.orders_manager.cancel_all_orders()
                    logger.info("[SHUTDOWN] All orders cancelled")
                except Exception as e:
                    logger.error(f"[SHUTDOWN] Error: {e}")
            if hasattr(self.bot, "telegram") and self.bot.telegram:
                try:
                    await self.bot.telegram.notify_shutdown()
                except Exception as e:
                    logger.error(f"[SHUTDOWN] Error: {e}")
            if hasattr(self.bot, "exchange") and self.bot.exchange:
                try:
                    await self.bot.exchange.close()
                except Exception as e:
                    logger.error(f"[SHUTDOWN] Error: {e}")
            logger.info("[SHUTDOWN] ========== COMPLETE ==========")
        except Exception as e:
            logger.critical(f"[SHUTDOWN] Error: {e}", exc_info=True)
        finally:
            asyncio.get_event_loop().call_later(30, lambda: sys.exit(0))
            sys.exit(0)
