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
        side = kwargs.get("side", args[1] if len(args) > 1 else "LONG")
        fill = kwargs.get("fill", kwargs.get("fill_price", args[2] if len(args) > 2 else 0.0))
        sl = kwargs.get("sl", kwargs.get("sl_price", args[3] if len(args) > 3 else 0.0))
        tp = kwargs.get("tp", kwargs.get("tp_price", args[4] if len(args) > 4 else 0.0))
        lots = kwargs.get("lots", 100)
        atr = kwargs.get("atr", 0.0)
        rr = kwargs.get("rr", kwargs.get("r_multiple", 3.6))
        
        emoji = "🟢" if "LONG" in str(side).upper() or "BUY" in str(side).upper() else "🔴"
        diff_sl = abs(float(fill) - float(sl))
        diff_tp = abs(float(tp) - float(fill))
        
        lines = [
            f"{emoji} <b>ENTRY — {str(side).upper()}</b> | {lots} lots (0.1000 BTC)",
            f"<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</code>",
            "",
            f"<b>Fill</b>  : ${float(fill):,.2f}",
            f"<b>SL</b>    : ${float(sl):,.2f}  (-{diff_sl:.2f})",
            f"<b>TP</b>    : ${float(tp):,.2f}  (+{diff_tp:.2f})",
            f"<b>ATR</b>   : {float(atr):.2f}  |  R:R {float(rr):.2f}"
        ]
        return await self.send("\n".join(lines))

    async def notify_exit(self, *args, **kwargs):
        side = kwargs.get("side", args[1] if len(args) > 1 else "LONG")
        entry = kwargs.get("entry", kwargs.get("entry_price", args[2] if len(args) > 2 else 0.0))
        exit_p = kwargs.get("exit", kwargs.get("exit_price", args[3] if len(args) > 3 else 0.0))
        points = kwargs.get("points", kwargs.get("pnl_points", args[4] if len(args) > 4 else 0.0))
        gross = kwargs.get("gross_pnl", args[5] if len(args) > 5 else float(points) * 0.10)
        lots = kwargs.get("lots", 100)
        reason = kwargs.get("reason", "Closed")
        
        emoji = "💰" if float(points) > 0 else "🔻"
        sign = "+" if float(points) > 0 else ""
        
        lines = [
            f"{emoji} <b>EXIT — {str(side).upper()}</b> | {lots} lots",
            f"<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST</code>",
            "",
            f"<b>Entry</b>     : ${float(entry):,.2f}",
            f"<b>Exit</b>      : ${float(exit_p):,.2f}",
            f"<b>Points</b>    : {sign}{float(points):.2f}",
            f"<b>Gross P&L</b> : {sign}${float(gross):.4f} USD",
            f"<b>Reason</b>    : {reason}"
        ]
        return await self.send("\n".join(lines))