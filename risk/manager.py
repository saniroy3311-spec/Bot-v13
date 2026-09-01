"""Production risk manager with kill switches."""
import logging
from datetime import datetime
logger = logging.getLogger("risk.manager")

class RiskManager:
    def __init__(self, config, exchange):
        self.config = config
        self.exchange = exchange
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self.last_reset_date = None
        self.last_week_reset = None
        self.trading_paused = False
        self.pause_reason = None
        self.kill_switch_triggered = False

    async def update_equity(self):
        try:
            account = await self.exchange.fetch_account()
            self.current_equity = float(account.get("equity", 0))
            if self.current_equity > self.peak_equity:
                self.peak_equity = self.current_equity
            today = datetime.utcnow().date()
            if self.last_reset_date != today:
                self.daily_pnl = 0.0
                self.last_reset_date = today
            if datetime.utcnow().weekday() == 0 and self.last_week_reset != today:
                self.weekly_pnl = 0.0
                self.last_week_reset = today
        except Exception as e:
            logger.error(f"[RISK] Failed to update equity: {e}")

    def record_trade_pnl(self, pnl):
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        logger.info(f"[RISK] Trade PnL: {pnl:+.2f} (daily: {self.daily_pnl:+.2f})")

    async def check_all_limits(self):
        await self.update_equity()
        if self.kill_switch_triggered:
            return False, "KILL_SWITCH_ACTIVE"
        if self.current_equity <= 0:
            return False, "NO_EQUITY"
        if self.peak_equity > 0:
            daily_loss_pct = (self.daily_pnl / self.peak_equity) * 100
            if daily_loss_pct <= -self.config.MAX_DAILY_LOSS_PCT:
                self.trading_paused = True
                self.pause_reason = "daily_loss_limit"
                return False, f"DAILY_LOSS_LIMIT: {daily_loss_pct:.2f}%"
            weekly_loss_pct = (self.weekly_pnl / self.peak_equity) * 100
            if weekly_loss_pct <= -self.config.MAX_WEEKLY_LOSS_PCT:
                self.trading_paused = True
                return False, f"WEEKLY_LOSS_LIMIT: {weekly_loss_pct:.2f}%"
            drawdown_pct = ((self.peak_equity - self.current_equity) / self.peak_equity) * 100
            if drawdown_pct >= self.config.MAX_DRAWDOWN_PCT:
                self.kill_switch_triggered = True
                self.trading_paused = True
                logger.critical(f"[RISK] KILL SWITCH: drawdown {drawdown_pct:.2f}%")
                return False, f"MAX_DRAWDOWN: {drawdown_pct:.2f}%"
        return True, "OK"

    def manual_reset_kill_switch(self):
        self.kill_switch_triggered = False
        self.trading_paused = False
        self.pause_reason = None
        logger.warning("[RISK] Kill switch manually reset")

    def get_status(self):
        return {"trading_paused": self.trading_paused, "pause_reason": self.pause_reason,
                "kill_switch_triggered": self.kill_switch_triggered, "current_equity": self.current_equity,
                "peak_equity": self.peak_equity, "daily_pnl": self.daily_pnl}
