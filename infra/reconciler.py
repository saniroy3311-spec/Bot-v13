"""Position reconciler."""
import asyncio
import logging
logger = logging.getLogger("infra.reconciler")

class PositionReconciler:
    def __init__(self, bot_instance, interval=60):
        self.bot = bot_instance
        self.interval = interval
        self.running = False
        self.mismatch_count = 0

    async def run_forever(self):
        self.running = True
        logger.info(f"[RECONCILER] Started - checking every {self.interval}s")
        await asyncio.sleep(self.interval)
        while self.running:
            try:
                await self.reconcile_once()
            except Exception as e:
                logger.error(f"[RECONCILER] Error: {e}", exc_info=True)
            await asyncio.sleep(self.interval)

    async def reconcile_once(self):
        try:
            exchange_positions = await self.bot.exchange.fetch_positions()
            exchange_pos_map = {p["symbol"]: p for p in exchange_positions}
            bot_positions = self.bot.get_internal_positions() if hasattr(self.bot, "get_internal_positions") else {}
            mismatches = 0
            for symbol in set(exchange_pos_map.keys()) | set(bot_positions.keys()):
                ex_pos = exchange_pos_map.get(symbol)
                bot_pos = bot_positions.get(symbol)
                if ex_pos and not bot_pos:
                    logger.warning(f"[RECONCILER] Exchange has {symbol}, bot doesn't - syncing")
                    if hasattr(self.bot, "sync_position_from_exchange"):
                        await self.bot.sync_position_from_exchange(symbol, ex_pos)
                    mismatches += 1
                elif bot_pos and not ex_pos:
                    logger.warning(f"[RECONCILER] Bot has {symbol}, exchange doesn't - clearing")
                    if hasattr(self.bot, "clear_position"):
                        await self.bot.clear_position(symbol)
                    mismatches += 1
            if mismatches > 0:
                self.mismatch_count += mismatches
        except Exception as e:
            logger.error(f"[RECONCILER] Error: {e}")

    def stop(self):
        self.running = False
