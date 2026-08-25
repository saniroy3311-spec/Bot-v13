import os
import sqlite3
import requests
import logging
from datetime import datetime

logger = logging.getLogger("Journal")


def auto_sync_trade(trade_data):
    webhook_url = os.getenv("GSHEET_WEBHOOK_URL", "")
    if webhook_url:
        try:
            requests.post(webhook_url, json=trade_data, timeout=5)
        except Exception:
            pass

    try:
        csv_file = "/root/Bot-v13/live_trades_journal.csv"
        if not os.path.exists(csv_file):
            with open(csv_file, "w") as f:
                f.write("Trade_ID,Timestamp,Symbol,Engine,Side,Entry,Exit,Points,Lots,Gross_USD,Fees,Net_USD,Net_INR,Balance_USD,Status,Notes\n")
        row = "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n".format(
            trade_data.get("trade_id", ""),
            trade_data.get("timestamp", ""),
            trade_data.get("symbol", ""),
            trade_data.get("engine", ""),
            trade_data.get("side", ""),
            trade_data.get("entry_price", ""),
            trade_data.get("exit_price", ""),
            trade_data.get("points_captured", ""),
            trade_data.get("lots", ""),
            trade_data.get("gross_pnl", ""),
            trade_data.get("fees", ""),
            trade_data.get("net_pnl", ""),
            trade_data.get("net_inr", ""),
            trade_data.get("balance", ""),
            trade_data.get("status", ""),
            trade_data.get("notes", ""),
        )
        with open(csv_file, "a") as f:
            f.write(row)
    except Exception:
        pass


class Journal:
    """
    Trade journal backed by SQLite.

    Full contract expected by callers across the codebase (main.py,
    monitor/trail_loop.py, infra/whatsapp_controller.py,
    infra/telegram_controller.py, server.py, phase5/run_phase5.py):

        open_trade(signal_type, is_long, entry_price, sl, tp, atr, qty)
        get_open_trade() -> dict | None
        update_open_trade(**fields)      # trail_stage, current_sl, peak_price, sl, tp, atr
        clear_open_trade()               # purge a ghost OPEN row (no real position on exchange)
        close_open_trade()               # finalize the OPEN row to CLOSED
        log_trade(signal_type, is_long, entry_price, exit_price, sl, tp, atr,
                   qty, real_pl, exit_reason, trail_stage)
        get_summary() / get_daily_summary()
        get_trades(limit=50)
        log_event(event_type, detail="")
        close()

    All positional-arg calls (phase5 test harness) and keyword-arg calls
    (main.py) work identically since parameter names match exactly.
    """

    def __init__(self, db_path="journal.db"):
        self.db_path = os.getenv("LOG_FILE", db_path)
        self._connect()

    def _connect(self):
        try:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
            c = self._conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    signal_type TEXT,
                    side TEXT,
                    is_long INTEGER,
                    entry_price REAL,
                    exit_price REAL,
                    sl REAL,
                    tp REAL,
                    atr REAL,
                    current_sl REAL,
                    peak_price REAL,
                    trail_stage INTEGER,
                    pnl_points REAL,
                    gross_pnl REAL,
                    fees REAL,
                    net_pnl REAL,
                    lots INTEGER,
                    engine TEXT,
                    exit_reason TEXT,
                    status TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    balance REAL,
                    equity REAL,
                    open_positions INTEGER,
                    peak_balance REAL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    event_type TEXT,
                    detail TEXT
                )
            """)
            self._conn.commit()

            # Migration: add any columns missing on an older/existing trades table
            # (safe to re-run — duplicate-column errors are swallowed).
            for col_def in [
                "signal_type TEXT", "is_long INTEGER", "sl REAL", "tp REAL", "atr REAL",
                "current_sl REAL", "peak_price REAL", "trail_stage INTEGER", "exit_reason TEXT",
            ]:
                col_name = col_def.split()[0]
                try:
                    c.execute(f"ALTER TABLE trades ADD COLUMN {col_def}")
                    self._conn.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists
        except Exception as e:
            logger.error(f"Journal DB init error: {e}")

    # ── Open-trade lifecycle ──────────────────────────────────────────────────────────

    def open_trade(self, signal_type, is_long, entry_price, sl, tp, atr, qty):
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c = self._conn.cursor()
            c.execute("""
                INSERT INTO trades
                    (timestamp, symbol, signal_type, side, is_long, entry_price,
                     sl, tp, atr, current_sl, peak_price, trail_stage, lots, engine, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'OPEN')
            """, (
                ts, "BTC/USD:USD", signal_type,
                "LONG" if is_long else "SHORT", 1 if is_long else 0,
                entry_price, sl, tp, atr, sl, entry_price, qty, "E1_TREND_PULLBACK",
            ))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to open trade in DB: {e}")

    def get_open_trade(self):
        try:
            c = self._conn.cursor()
            c.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
            if not row:
                return None
            cols = [d[0] for d in c.description]
            d = dict(zip(cols, row))
            d["qty"] = d.get("lots")
            return d
        except Exception as e:
            logger.error(f"Failed to read open trade: {e}")
            return None

    def update_open_trade(self, **fields):
        allowed = {"trail_stage", "current_sl", "peak_price", "sl", "tp", "atr"}
        open_row = self.get_open_trade()
        if not open_row:
            return
        sets, vals = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                vals.append(v)
        if not sets:
            return
        vals.append(open_row["id"])
        try:
            c = self._conn.cursor()
            c.execute(f"UPDATE trades SET {', '.join(sets)} WHERE id = ?", vals)
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to update open trade: {e}")

    def clear_open_trade(self):
        try:
            c = self._conn.cursor()
            c.execute("UPDATE trades SET status='PURGED' WHERE status='OPEN'")
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear open trade: {e}")

    def close_open_trade(self):
        try:
            c = self._conn.cursor()
            c.execute("UPDATE trades SET status='CLOSED' WHERE status='OPEN'")
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to close open trade: {e}")

    # ── Closing a trade with exit data ──────────────────────────────────────

    def log_trade(self, signal_type, is_long, entry_price, exit_price, sl, tp, atr,
                   qty, real_pl, exit_reason, trail_stage):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            pnl_points = (exit_price - entry_price) if is_long else (entry_price - exit_price)
        except Exception:
            pnl_points = 0.0

        open_row = self.get_open_trade()
        try:
            c = self._conn.cursor()
            if open_row:
                c.execute("""
                    UPDATE trades
                    SET exit_price=?, pnl_points=?, gross_pnl=?, net_pnl=?, exit_reason=?, trail_stage=?
                    WHERE id=?
                """, (exit_price, pnl_points, real_pl, real_pl, exit_reason, trail_stage, open_row["id"]))
            else:
                # No matching OPEN row (e.g. journal was purged) — record it standalone.
                c.execute("""
                    INSERT INTO trades
                        (timestamp, symbol, signal_type, side, is_long, entry_price, exit_price,
                         sl, tp, atr, pnl_points, gross_pnl, net_pnl, lots, engine, exit_reason,
                         trail_stage, status)
                    VALUES (?, 'BTC/USD:USD', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'E1_TREND_PULLBACK', ?, ?, 'CLOSED')
                """, (
                    ts, signal_type, "LONG" if is_long else "SHORT", 1 if is_long else 0,
                    entry_price, exit_price, sl, tp, atr, pnl_points, real_pl, real_pl,
                    qty, exit_reason, trail_stage,
                ))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to log trade to DB: {e}")

        auto_sync_trade({
            "trade_id": open_row["id"] if open_row else "",
            "timestamp": ts,
            "symbol": "BTC/USD:USD",
            "engine": "E1_TREND_PULLBACK",
            "side": "LONG" if is_long else "SHORT",
            "entry_price": entry_price,
            "exit_price": exit_price,
            "points_captured": pnl_points,
            "lots": qty,
            "gross_pnl": real_pl,
            "fees": "",
            "net_pnl": real_pl,
            "net_inr": "",
            "balance": "",
            "status": "CLOSED",
            "notes": exit_reason,
        })

    # ── Reporting ────────────────────────────────────────────────────────────

    def get_summary(self):
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            c = self._conn.cursor()
            c.execute(
                "SELECT gross_pnl FROM trades WHERE status='CLOSED' AND date(timestamp)=?",
                (today,),
            )
            rows = [r[0] for r in c.fetchall() if r[0] is not None]
        except Exception as e:
            logger.error(f"Failed to compute summary: {e}")
            rows = []
        total = len(rows)
        wins = len([x for x in rows if x > 0])
        losses = len([x for x in rows if x <= 0])
        win_rate = (wins / total * 100) if total else 0.0
        return {
            "date": today,
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_pl": sum(rows),
        }

    def get_daily_summary(self):
        return self.get_summary()

    def get_trades(self, limit=50):
        try:
            c = self._conn.cursor()
            c.execute("SELECT * FROM trades WHERE status='CLOSED' ORDER BY id DESC LIMIT ?", (limit,))
            cols = [d[0] for d in c.description]
            return [dict(zip(cols, r)) for r in c.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []

    def log_event(self, event_type, detail=""):
        try:
            c = self._conn.cursor()
            c.execute(
                "INSERT INTO events (timestamp, event_type, detail) VALUES (?, ?, ?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), event_type, detail),
            )
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
