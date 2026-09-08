
def _to_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

import os
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("GSheet")
IST = timezone(timedelta(hours=5, minutes=30))

class GSheetSync:
    def __init__(self, tab_name="Bot-v13 (3m Scalper)"):
        self.spreadsheet_id = os.environ.get("GSHEET_SPREADSHEET_ID", "1kpXpRuGYeScm7DtNUT5ctDeR60ssj0aqcfRWjCpBFME")
        self.credentials_path = os.environ.get("GSHEET_CREDENTIALS_PATH", "/root/BTC_Bot_v13/credentials.json")
        self.tab_name = os.environ.get("GSHEET_TAB_NAME", tab_name)
        self.client = None
        self.sheet = None
        self._enabled = os.path.exists(self.credentials_path) and bool(self.spreadsheet_id)
        if not self._enabled:
            logger.info("GSheet sync disabled — credentials file or GSHEET_SPREADSHEET_ID missing.")

    def _connect(self):
        if self.sheet is not None:
            return
        if not self._enabled:
            return
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]
            with open(self.credentials_path, "r", encoding="utf-8") as f:
                creds_dict = json.load(f)
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            self.client = gspread.authorize(creds)
            ss = self.client.open_by_key(self.spreadsheet_id)
            
            # Match tab name exactly, or fall back to first available sheet
            existing_tabs = [ws.title for ws in ss.worksheets()]
            if self.tab_name in existing_tabs:
                self.sheet = ss.worksheet(self.tab_name)
            elif "Trades" in existing_tabs:
                self.sheet = ss.worksheet("Trades")
            else:
                self.sheet = ss.get_worksheet(0)
            logger.info(f"✅ GSheet connected directly to tab: '{self.sheet.title}' in '{ss.title}'")
        except Exception as e:
            logger.error(f"❌ GSheet connection failed: {e}")
            self.sheet = None

    def append_trade(self, trade_dict: dict) -> bool:
        if not self._enabled:
            return False
        try:
            self._connect()
            if not self.sheet:
                return False

            pts = float(trade_dict.get("points_captured", trade_dict.get("pnl_points", trade_dict.get("points", 0.0))))
            lots = int(trade_dict.get("lots", 1))
            btc_size = float(trade_dict.get("btc_size", lots * 0.001))
            gross = _to_float(trade_dict.get("gross_pnl", pts * btc_size))
            
            # Approximate taker fee if not explicitly passed
            fees = _to_float(trade_dict.get("fees", round(79000.0 * btc_size * 0.0005 * 1.18, 4)))
            net_u = _to_float(trade_dict.get("net_pnl", round(gross - fees, 4)))
            net_i = _to_float(trade_dict.get("net_inr", round(net_u * 94.40, 2)))
            status = trade_dict.get("status", "WIN (TP Hit)" if pts > 0 else "LOSS (SL Hit)")
            
            # Get current count for trade numbering
            try:
                all_vals = self.sheet.get_all_values()
                trade_num = len(all_vals) - 5 if len(all_vals) >= 6 else len(all_vals)
            except Exception:
                trade_num = trade_dict.get("trade_id", 1)

            ts = trade_dict.get("timestamp")
            if not ts:
                ts = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

            # 18-Column Schema for "Bot-v13 (3m Scalper)"
            row = [
                trade_dict.get("trade_id", trade_num),
                ts,
                trade_dict.get("symbol", "BTC/USD:USD"),
                trade_dict.get("engine", "E1_TREND_PULLBACK"),
                trade_dict.get("side", "BUY"),
                round(float(trade_dict.get("entry_price", 0.0)), 2),
                round(float(trade_dict.get("exit_price", 0.0)), 2),
                round(pts, 2),
                lots,
                round(btc_size, 4),
                round(gross, 4),
                round(fees, 4),
                round(net_u, 4),
                round(net_i, 2),
                trade_dict.get("balance_usd", ""),
                trade_dict.get("balance_inr", ""),
                status,
                trade_dict.get("exit_reason", trade_dict.get("notes", "Bot Execution"))
            ]
            
            self.sheet.append_row(row, value_input_option="USER_ENTERED")
            logger.info(f"✅ Successfully appended trade #{trade_num} to GSheet '{self.sheet.title}'")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to append trade to GSheet: {e}")
            return False

# Global singleton
gsheet_client = GSheetSync()
