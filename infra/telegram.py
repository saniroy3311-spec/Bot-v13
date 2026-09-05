from __future__ import annotations
"""
infra/telegram.py — Bot v13  [FIXED 2026-09-05]

WHAT WAS WRONG (and is now fixed)
─────────────────────────────────
The old formatter used a chain of kwargs.get()/trade.get() lookups whose names
did NOT match what main.py actually sends. Every lookup silently fell through
to a default, so:

  * main.py sent  is_long=      -> formatter wanted  side=   -> printed "LONG" always
  * main.py sent  real_pl=      -> formatter wanted  gross=  -> recomputed with the
                                                                LONG formula, so every
                                                                SHORT was reported with
                                                                the P&L sign REVERSED
  * main.py sent  entry_price=  -> formatter wanted  fill=   -> got 0.0, then invented
                                                                a price from
                                                                (3.65*SL + TP)/4.65
  * main.py sent  qty=          -> formatter wanted  lots=   -> hardcoded 100
  * R:R was a hardcoded 3.65, not the trade's measured reward ratio

Result: the alert stream was fiction. 35 SHORT trades were displayed as LONG
with inverted P&L, turning a real -$368 session into a displayed +$139.

THE FIX
───────
1. Read the names main.py actually sends (is_long, real_pl, entry_price, qty),
   while still accepting the alternative names for backward compatibility.
2. NEVER invent a fill price. If it is missing, print "unavailable" and log an
   error. A wrong number is far worse than no number.
3. Derive direction from is_long and compute points with the correct formula.
4. Show real R:R measured from the actual SL/TP levels.
5. Explicit IST timezone instead of naive datetime.now().
6. Warn on the message itself when bracket geometry contradicts the direction,
   or when an exit price is a stop level rather than a confirmed fill.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger("Telegram")

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _pick(kwargs: dict, trade, *names, default=None):
    """
    Look for any of `names` in kwargs first, then on the trade dict/object.
    Returns (value, found) so "missing" can be told apart from "zero".
    """
    for n in names:
        if n in kwargs and kwargs[n] is not None:
            return kwargs[n], True
    if isinstance(trade, dict):
        for n in names:
            if n in trade and trade[n] is not None:
                return trade[n], True
    elif trade is not None:
        for n in names:
            v = getattr(trade, n, None)
            if v is not None:
                return v, True
    return default, False


def _f(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _money(v: float) -> str:
    return f"${v:,.2f}"


class Telegram:
    def __init__(self):
        self.enabled   = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url  = f"https://api.telegram.org/bot{self.bot_token}"

    # ── transport ─────────────────────────────────────────────────────────────

    def _send_sync(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode},
                timeout=8,
            )
            if resp.status_code != 200:
                logger.error(f"Telegram HTTP {resp.status_code}: {resp.text[:200]}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    async def send(self, text: str, parse_mode: str = "HTML") -> bool:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._send_sync, text, parse_mode)
        except RuntimeError:
            return self._send_sync(text, parse_mode)

    # ── entry alert ───────────────────────────────────────────────────────────

    async def notify_entry(self, *args, **kwargs) -> bool:
        trade = args[0] if args and not isinstance(args[0], str) else None

        is_long, have_dir = _pick(kwargs, trade, "is_long")
        if not have_dir:
            side_txt, have_side = _pick(kwargs, trade, "side", "direction")
            if have_side:
                s = str(side_txt).upper()
                is_long, have_dir = ("LONG" in s or "BUY" in s), True

        fill,  have_fill = _pick(kwargs, trade, "entry_price", "fill", "fill_price")
        sl,    _         = _pick(kwargs, trade, "sl", "sl_price", default=0.0)
        tp,    _         = _pick(kwargs, trade, "tp", "tp_price", default=0.0)
        atr,   _         = _pick(kwargs, trade, "atr", default=0.0)
        qty,   have_qty  = _pick(kwargs, trade, "qty", "lots", "contracts")
        sigt,  _         = _pick(kwargs, trade, "signal_type", default="")

        fill, sl, tp, atr = _f(fill), _f(sl), _f(tp), _f(atr)

        if not have_dir:
            logger.error("[TG] notify_entry: direction missing — refusing to guess.")
        if not have_fill or fill <= 0:
            logger.error("[TG] notify_entry: entry price missing. NOT fabricating one.")

        # A LONG must have SL below and TP above. Anything else is a real problem.
        geometry_ok = True
        if have_dir and fill > 0 and sl > 0 and tp > 0:
            geometry_ok = (sl < fill < tp) if is_long else (tp < fill < sl)

        side_label = ("LONG" if is_long else "SHORT") if have_dir else "UNKNOWN"
        emoji      = "🟢" if (have_dir and is_long) else ("🔴" if have_dir else "⚪")

        # Measured, never assumed.
        risk_pts   = abs(fill - sl) if (fill > 0 and sl > 0) else 0.0
        reward_pts = abs(tp - fill) if (fill > 0 and tp > 0) else 0.0
        rr         = (reward_pts / risk_pts) if risk_pts > 0 else 0.0

        btc     = _f(qty) * 0.001 if have_qty else 0.0
        qty_str = f"{int(_f(qty))} lots ({btc:.4f} BTC)" if have_qty else "size unknown"

        lines = [
            f"{emoji} <b>ENTRY — {side_label}</b> | {qty_str}",
            f"<code>{_now_ist()} IST</code>",
            "",
            f"<b>Fill</b>  : {_money(fill) if fill > 0 else 'unavailable'}",
            f"<b>SL</b>    : {_money(sl)}  ({'-' if is_long else '+'}{risk_pts:.2f})",
            f"<b>TP</b>    : {_money(tp)}  ({'+' if is_long else '-'}{reward_pts:.2f})",
            f"<b>ATR</b>   : {atr:.2f}  |  R:R {rr:.2f}",
        ]
        if sigt:
            lines.append(f"<b>Signal</b>: {sigt}")
        if not geometry_ok:
            lines += ["", "⚠️ <b>BRACKET GEOMETRY MISMATCH — CHECK IMMEDIATELY</b>"]
            logger.error(
                f"[TG] Bracket geometry wrong: is_long={is_long} "
                f"fill={fill} sl={sl} tp={tp}"
            )
        if not have_dir or fill <= 0:
            lines += ["", "⚠️ <b>Incomplete data — verify on the exchange</b>"]

        return await self.send("\n".join(lines))

    # ── exit alert ────────────────────────────────────────────────────────────

    async def notify_exit(self, *args, **kwargs) -> bool:
        trade = args[0] if args and not isinstance(args[0], str) else None

        is_long, have_dir = _pick(kwargs, trade, "is_long")
        if not have_dir:
            side_txt, have_side = _pick(kwargs, trade, "side", "direction")
            if have_side:
                s = str(side_txt).upper()
                is_long, have_dir = ("LONG" in s or "BUY" in s), True

        entry,  _        = _pick(kwargs, trade, "entry_price", "entry", default=0.0)
        exit_p, _        = _pick(kwargs, trade, "exit_price", "exit", default=0.0)
        qty,    have_qty = _pick(kwargs, trade, "qty", "lots", "contracts")
        reason, _        = _pick(kwargs, trade, "reason", "exit_reason", default="Closed")

        # main.py sends real_pl — already computed correctly by calc_gross_pl().
        pl, have_pl = _pick(kwargs, trade, "real_pl", "gross", "gross_pnl", "pnl")

        entry, exit_p = _f(entry), _f(exit_p)

        # Points ALWAYS use the direction-correct formula.
        if have_dir and entry > 0 and exit_p > 0:
            points = (exit_p - entry) if is_long else (entry - exit_p)
        else:
            points = 0.0
            logger.error(
                "[TG] notify_exit: cannot compute points — direction or prices missing."
            )

        if have_pl:
            gross = _f(pl)
        elif have_qty:
            # Delta inverse perp: 1 lot = 0.001 BTC
            gross = points * _f(qty) * 0.001
            logger.warning("[TG] notify_exit: real_pl not supplied, recomputed locally.")
        else:
            gross = 0.0
            logger.error("[TG] notify_exit: no P&L and no qty — cannot report gross.")

        emoji      = "💰" if gross > 0 else ("🔻" if gross < 0 else "⚪")
        side_label = ("LONG" if is_long else "SHORT") if have_dir else "UNKNOWN"
        p_sign     = "+" if points > 0 else ""
        g_sign     = "+" if gross > 0 else ""

        # The sign of points and the sign of gross must agree. If they do not,
        # the direction contract has broken again — shout about it.
        if points and gross and ((points > 0) != (gross > 0)):
            logger.error(
                f"[TG] SIGN MISMATCH points={points:+.2f} gross={gross:+.4f} "
                f"is_long={is_long} — this is the bug class that caused the "
                f"2026-09-04 reporting failure."
            )

        recovered = "recovered" in str(reason).lower()

        lines = [
            f"{emoji} <b>EXIT — {side_label}</b> | "
            f"{int(_f(qty)) if have_qty else '?'} lots",
            f"<code>{_now_ist()} IST</code>",
            "",
            f"<b>Entry</b>     : {_money(entry) if entry > 0 else 'unavailable'}",
            f"<b>Exit</b>      : {_money(exit_p) if exit_p > 0 else 'unavailable'}",
            f"<b>Points</b>    : {p_sign}{points:.2f}",
            f"<b>Gross P&amp;L</b> : {g_sign}${gross:.4f} USD",
            f"<b>Reason</b>    : {reason}",
        ]
        if recovered:
            lines += [
                "",
                "ℹ️ <i>Exit price is the stop level, not a confirmed fill. "
                "Verify against exchange fill history.</i>",
            ]
        if not have_dir:
            lines += ["", "⚠️ <b>Direction unknown — verify on the exchange</b>"]

        return await self.send("\n".join(lines))

    # ── compatibility helpers ─────────────────────────────────────────────────

    async def notify_shutdown(self, *args, **kwargs) -> bool:
        return await self.send("🔴 <b>Bot v13 Stopped</b>")

    def close(self) -> None:
        return None
