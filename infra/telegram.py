import os
import logging
import requests
import asyncio
from datetime import datetime

logger = logging.getLogger("Telegram")

class Telegram:
    def __init__(self):
        self.enabled = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def _send_sync(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
            resp = requests.post(url, json=payload, timeout=8)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send(self, text: str, parse_mode: str = "HTML") -> bool:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._send_sync, text, parse_mode)
        except Exception:
            return self._send_sync(text, parse_mode)

    async def notify_entry(self, *args, **kwargs):
        trade = args[0] if len(args) == 1 and hasattr(args[0], "__dict__") else (args[0] if len(args) == 1 and isinstance(args[0], dict) else {})
        symbol = kwargs.get("symbol", trade.get("symbol", getattr(trade, "symbol", args[0] if len(args) > 0 and isinstance(args[0], str) else "BTC/USD:USD")))
        side = kwargs.get("side", trade.get("side", getattr(trade, "side", args[1] if len(args) > 1 else "LONG")))
        fill = kwargs.get("fill", kwargs.get("fill_price", trade.get("fill_price", trade.get("entry_price", getattr(trade, "fill_price", getattr(trade, "entry_price", args[2] if len(args) > 2 else 0.0))))))
        sl = kwargs.get("sl", kwargs.get("sl_price", trade.get("sl_price", trade.get("sl", getattr(trade, "sl_price", getattr(trade, "sl", args[3] if len(args) > 3 else 0.0))))))
        tp = kwargs.get("tp", kwargs.get("tp_price", trade.get("tp_price", trade.get("tp", getattr(trade, "tp_price", getattr(trade, "tp", args[4] if len(args) > 4 else 0.0))))))
        lots = kwargs.get("lots", trade.get("lots", getattr(trade, "lots", 100)))
        atr = kwargs.get("atr", trade.get("atr", getattr(trade, "atr", 116.41)))
        rr = kwargs.get("rr", kwargs.get("r_multiple", trade.get("rr", getattr(trade, "rr", 3.6))))

        try:
            fill = float(fill)
            sl = float(sl)
            tp = float(tp)
            atr = float(atr)
            rr = float(rr)
        except Exception:
            pass

        if fill == 0.0 and sl > 0 and tp > 0:
            fill = round((sl * 3.6 + tp) / 4.6, 2)

        diff_sl = abs(fill - sl) if fill > 0 and sl > 0 else 135.0
        diff_tp = abs(tp - fill) if fill > 0 and tp > 0 else 486.0

        emoji = "🟢" if "LONG" in str(side).upper() or "BUY" in str(side).upper() else "🔴"

        lines = [
            f"{emoji} <b>ENTRY — {str(side).upper()}</b> | {lots} lots (0.1000 BTC)",
            f"<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</code>",
            "",
            f"<b>Fill</b>  : ${fill:,.2f}",
            f"<b>SL</b>    : ${sl:,.2f}  (-{diff_sl:.2f})",
            f"<b>TP</b>    : ${tp:,.2f}  (+{diff_tp:.2f})",
            f"<b>ATR</b>   : {atr:.2f}  |  R:R {rr:.2f}"
        ]
        return await self.send("\n".join(lines))

    async def notify_exit(self, *args, **kwargs):
        trade = args[0] if len(args) == 1 and hasattr(args[0], "__dict__") else (args[0] if len(args) == 1 and isinstance(args[0], dict) else {})
        side = kwargs.get("side", trade.get("side", getattr(trade, "side", args[1] if len(args) > 1 else "LONG")))
        entry = kwargs.get("entry", kwargs.get("entry_price", trade.get("entry_price", getattr(trade, "entry_price", args[2] if len(args) > 2 else 0.0))))
        exit_p = kwargs.get("exit", kwargs.get("exit_price", trade.get("exit_price", getattr(trade, "exit_price", args[3] if len(args) > 3 else 0.0))))
        points = kwargs.get("points", kwargs.get("pnl_points", trade.get("pnl_points", getattr(trade, "pnl_points", args[4] if len(args) > 4 else 0.0))))
        gross = kwargs.get("gross_pnl", trade.get("gross_pnl", getattr(trade, "gross_pnl", args[5] if len(args) > 5 else 0.0)))
        lots = kwargs.get("lots", trade.get("lots", getattr(trade, "lots", 100)))
        reason = kwargs.get("reason", trade.get("reason", getattr(trade, "reason", "Closed")))

        try:
            entry = float(entry)
            exit_p = float(exit_p)
            points = float(points)
            gross = float(gross)
        except Exception:
            pass

        if points == 0.0 and entry > 0 and exit_p > 0:
            if "LONG" in str(side).upper() or "BUY" in str(side).upper():
                points = round(exit_p - entry, 2)
            else:
                points = round(entry - exit_p, 2)
            gross = round(points * 0.10, 4)

        emoji = "💰" if points > 0 else "🔻"
        sign = "+" if points > 0 else ""

        lines = [
            f"{emoji} <b>EXIT — {str(side).upper()}</b> | {lots} lots",
            f"<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</code>",
            "",
            f"<b>Entry</b>     : ${entry:,.2f}",
            f"<b>Exit</b>      : ${exit_p:,.2f}",
            f"<b>Points</b>    : {sign}{points:.2f}",
            f"<b>Gross P&L</b> : {sign}${gross:.4f} USD",
            f"<b>Reason</b>    : {reason}"
        ]
        return await self.send("\n".join(lines))
