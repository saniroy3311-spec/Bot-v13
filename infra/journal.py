import os
import sqlite3
import requests
import json
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
        row = f"{trade_data.get("trade_id","")},{trade_data.get("timestamp","")},{trade_data.get("symbol","")},{trade_data.get("engine","")},{trade_data.get("side","")},{trade_data.get("entry_price","")},{trade_data.get("exit_price","")},{trade_data.get("points_captured","")},{trade_data.get("lots","")},{trade_data.get("gross_pnl","")},{trade_data.get("fees","")},{trade_data.get("net_pnl","")},{trade_data.get("net_inr","")},{trade_data.get("balance","")},{trade_data.get("status","")},{trade_data.get("notes","")}\n"
        with open(csv_file, "a") as f:
            f.write(row)
    except Exception:
        pass

class Journal:
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
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    risk_points REAL,
                    pnl_points REAL,
                    gross_pnl REAL,
                    fees REAL,
                    net_pnl REAL,
                    lots INTEGER,
                    engine TEXT,
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
            self._conn.commit()
        except Exception as e:
            logger.error(f"Journal DB init error: {e}")

    def log_trade(self, trade_dict):
        try:
            c = self._conn.cursor()
            c.execute("""
                INSERT INTO trades (timestamp, symbol, side, entry_price, exit_price, risk_points, pnl_points, gross_pnl, fees, net_pnl, lots, engine, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_dict.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                trade_dict.get("symbol", "BTC/USD:USD"),
                trade_dict.get("side", "BUY"),
                trade_dict.get("entry_price", 0.0),
                trade_dict.get("exit_price", 0.0),
                trade_dict.get("risk_points", 0.0),
                trade_dict.get("pnl_points", 0.0),
                trade_dict.get("gross_pnl", 0.0),
                trade_dict.get("fees", 0.0),
                trade_dict.get("net_pnl", 0.0),
                trade_dict.get("lots", 100),
                trade_dict.get("engine", "E1_TREND_PULLBACK"),
                trade_dict.get("status", "CLOSED")
            ))
            self._conn.commit()
        except Exception as e:
            logger.error(f"Failed to log trade to DB: {e}")
        auto_sync_trade(trade_dict)
