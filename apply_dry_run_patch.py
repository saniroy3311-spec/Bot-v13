"""
One-time patch: gate all live order calls in orders/manager.py behind DRY_RUN.
Run once on the VPS: python3 apply_dry_run_patch.py
Then: pm2 restart bot-v13
"""
import pathlib

TARGET = pathlib.Path("orders/manager.py")

REPLACEMENTS = [
    (
        'from config import (\n'
        '    DELTA_API_KEY, DELTA_API_SECRET, DELTA_TESTNET,\n'
        '    SYMBOL, ALERT_QTY,\n'
        ')',
        'from config import (\n'
        '    DELTA_API_KEY, DELTA_API_SECRET, DELTA_TESTNET,\n'
        '    SYMBOL, ALERT_QTY, DRY_RUN,\n'
        ')'
    ),
    (
        '        # ── 1. Market entry ──────────────────────────────────────────────────\n'
        '        order = await _retry(lambda: self.exchange.create_order(\n'
        '            symbol = SYMBOL,\n'
        '            type   = "market",\n'
        '            side   = side,\n'
        '            amount = ALERT_QTY,\n'
        '        ))\n'
        '        fill = float(order.get("average") or order.get("price") or 0.0)\n'
        '        logger.info(\n'
        '            f"[OM] Entry filled | id={order.get(\'id\')}  fill={fill:.2f}"\n'
        '        )',
        '        # ── 1. Market entry ──────────────────────────────────────────────────\n'
        '        if DRY_RUN:\n'
        '            ticker = await self.fetch_ticker()\n'
        '            fill = float(\n'
        '                (ticker or {}).get("last")\n'
        '                or (ticker or {}).get("markPrice")\n'
        '                or 0.0\n'
        '            )\n'
        '            order = {\n'
        '                "id": f"paper-{int(time.time() * 1000)}",\n'
        '                "average": fill,\n'
        '                "price": fill,\n'
        '                "info": {"paper_trade": True},\n'
        '            }\n'
        '            logger.info(\n'
        '                f"[OM] 📝 PAPER entry (no live order sent) | "\n'
        '                f"id={order[\'id\']}  fill={fill:.2f}"\n'
        '            )\n'
        '        else:\n'
        '            order = await _retry(lambda: self.exchange.create_order(\n'
        '                symbol = SYMBOL,\n'
        '                type   = "market",\n'
        '                side   = side,\n'
        '                amount = ALERT_QTY,\n'
        '            ))\n'
        '            fill = float(order.get("average") or order.get("price") or 0.0)\n'
        '            logger.info(\n'
        '                f"[OM] Entry filled | id={order.get(\'id\')}  fill={fill:.2f}"\n'
        '            )'
    ),
    (
        '        # ── 3. Emergency bracket SL (placed once, never amended) ─────────────\n'
        '        if self._product_id is None:',
        '        # ── 3. Emergency bracket SL (placed once, never amended) ─────────────\n'
        '        if DRY_RUN:\n'
        '            logger.info("[OM] 📝 PAPER mode — skipping live bracket placement.")\n'
        '            return order\n'
        '\n'
        '        if self._product_id is None:'
    ),
    (
        '        side = "sell" if is_long else "buy"\n'
        '        logger.info(\n'
        '            f"[OM] Closing position | side={side}  reason={reason}"\n'
        '        )\n'
        '        try:',
        '        side = "sell" if is_long else "buy"\n'
        '        logger.info(\n'
        '            f"[OM] Closing position | side={side}  reason={reason}"\n'
        '        )\n'
        '\n'
        '        if DRY_RUN:\n'
        '            ticker = await self.fetch_ticker()\n'
        '            fill = float(\n'
        '                (ticker or {}).get("last")\n'
        '                or (ticker or {}).get("markPrice")\n'
        '                or 0.0\n'
        '            )\n'
        '            order = {\n'
        '                "id": f"paper-{int(time.time() * 1000)}",\n'
        '                "average": fill,\n'
        '                "price": fill,\n'
        '                "info": {"paper_trade": True},\n'
        '            }\n'
        '            logger.info(\n'
        '                f"[OM] 📝 PAPER close (no live order sent) | "\n'
        '                f"id={order[\'id\']}  fill={fill:.2f}"\n'
        '            )\n'
        '            return order\n'
        '\n'
        '        try:'
    ),
    (
        '        FIX-CANCEL-01: replaced ccxt.cancel_all_orders() with a direct Delta\n'
        '        REST DELETE /v2/orders call. The ccxt async version internally called\n'
        '        Exchange.request() without awaiting it, producing a RuntimeWarning\n'
        '        every time this method ran. The signed REST path is already used\n'
        '        throughout this file for bracket operations and is reliable.\n'
        '        """\n'
        '        try:',
        '        FIX-CANCEL-01: replaced ccxt.cancel_all_orders() with a direct Delta\n'
        '        REST DELETE /v2/orders call. The ccxt async version internally called\n'
        '        Exchange.request() without awaiting it, producing a RuntimeWarning\n'
        '        every time this method ran. The signed REST path is already used\n'
        '        throughout this file for bracket operations and is reliable.\n'
        '        """\n'
        '        if DRY_RUN:\n'
        '            logger.debug("[OM] PAPER mode — skipping live cancel_all_orders.")\n'
        '            await self.cancel_bracket()\n'
        '            return\n'
        '        try:'
    ),
]

src = TARGET.read_text()
for old, new in REPLACEMENTS:
    if old not in src:
        raise SystemExit(f"❌ Pattern not found (file may already be patched, or differs from expected):\n{old[:80]}...")
    if src.count(old) > 1:
        raise SystemExit(f"❌ Pattern matched more than once, aborting for safety:\n{old[:80]}...")
    src = src.replace(old, new)

TARGET.write_text(src)
print("✅ Patched orders/manager.py — DRY_RUN now gates all live order calls.")
