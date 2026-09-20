"""Bot-v13 Realistic Backtest Engine."""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json, os, requests, time

TIMEFRAME = "3m"
SYMBOL = "BTCUSD"
STARTING_CAPITAL = 10000.0
RISK_PER_TRADE = 0.01
COMMISSION = 0.0005
SLIPPAGE = 0.0002
ADX_TREND_THRESHOLD = 22
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
EMA_FAST = 50
EMA_SLOW = 200
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5
ATR_TP_MULTIPLIER = 3.0
ATR_FILTER_MIN = 0.0001
BODY_FILTER_MIN = 0.30
VOL_FILTER_MIN = 0.5

TRAIL_STAGES = {
    1: {"activation_r": 0.5, "trail_atr_mult": 0.5},
    2: {"activation_r": 1.0, "trail_atr_mult": 1.0},
    3: {"activation_r": 1.5, "trail_atr_mult": 1.5},
    4: {"activation_r": 2.0, "trail_atr_mult": 2.0},
    5: {"activation_r": 3.0, "trail_atr_mult": 3.0},
}


class BotV13Backtest:
    def __init__(self):
        self.capital = STARTING_CAPITAL
        self.equity_curve = []
        self.trades = []
        self.positions = []
        self.peak_equity = STARTING_CAPITAL
        self.max_dd_pct = 0.0
        self.max_dd_usd = 0.0
        self.daily_pnl = {}
        self.monthly_pnl = {}
        self.wins = 0
        self.losses = 0
        self.commissions = 0.0
        self.filter_stats = {"ATR_FAIL": 0, "BODY_FAIL": 0, "VOL_FAIL": 0, "PASSED": 0}

    def calc_indicators(self, df):
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        df["tr"] = np.maximum(df["high"] - df["low"], np.maximum(
            abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))))
        df["atr"] = df["tr"].rolling(14).mean()
        df["atr_pct"] = df["atr"] / df["close"]
        df["up"] = df["high"] - df["high"].shift(1)
        df["dn"] = df["low"].shift(1) - df["low"]
        df["plus_dm"] = np.where((df["up"] > df["dn"]) & (df["up"] > 0), df["up"], 0)
        df["minus_dm"] = np.where((df["dn"] > df["up"]) & (df["dn"] > 0), df["dn"], 0)
        df["plus_di"] = 100 * (df["plus_dm"].rolling(14).mean() / df["atr"])
        df["minus_di"] = 100 * (df["minus_dm"].rolling(14).mean() / df["atr"])
        dx = 100 * abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"])
        df["adx"] = dx.rolling(14).mean()
        df["vol_sma"] = df["volume"].rolling(20).mean()
        df["vol_ratio"] = df["volume"] / df["vol_sma"]
        df["body"] = abs(df["close"] - df["open"])
        df["range"] = df["high"] - df["low"]
        df["body_ratio"] = df["body"] / df["range"].replace(0, np.nan)
        df["trend_up"] = (df["ema_50"] > df["ema_200"]) & (df["close"] > df["ema_50"])
        df["trend_down"] = (df["ema_50"] < df["ema_200"]) & (df["close"] < df["ema_50"])
        return df

    def check_filters(self, row):
        if pd.isna(row["atr_pct"]) or row["atr_pct"] < ATR_FILTER_MIN:
            return False, "ATR_FAIL"
        if pd.isna(row["body_ratio"]) or row["body_ratio"] < BODY_FILTER_MIN:
            return False, "BODY_FAIL"
        if pd.isna(row["vol_ratio"]) or row["vol_ratio"] < VOL_FILTER_MIN:
            return False, "VOL_FAIL"
        return True, "OK"

    def check_signal(self, row, prev):
        if pd.isna(row["adx"]) or row["adx"] < ADX_TREND_THRESHOLD:
            return None
        if row["trend_up"] and not prev["trend_up"]:
            return "LONG"
        if row["trend_down"] and not prev["trend_down"]:
            return "SHORT"
        if row["rsi"] < RSI_OVERSOLD and prev["rsi"] >= RSI_OVERSOLD and row["trend_up"]:
            return "LONG"
        if row["rsi"] > RSI_OVERBOUGHT and prev["rsi"] <= RSI_OVERBOUGHT and row["trend_down"]:
            return "SHORT"
        return None

    def apply_costs(self, price, side):
        if side == "BUY":
            return price * (1 + SLIPPAGE), price * COMMISSION
        return price * (1 - SLIPPAGE), price * COMMISSION

    def trail_update(self, pos, hi, lo, atr):
        if atr == 0:
            return
        if pos["side"] == "LONG":
            r = (hi - pos["entry"]) / (pos["entry"] - pos["sl"])
        else:
            r = (pos["entry"] - lo) / (pos["sl"] - pos["entry"])
        for stg, p in sorted(TRAIL_STAGES.items()):
            if r >= p["activation_r"] and stg > pos["stage"]:
                pos["stage"] = stg
                d = atr * p["trail_atr_mult"]
                if pos["side"] == "LONG":
                    ns = hi - d
                    if ns > pos["sl"]:
                        pos["sl"] = ns
                else:
                    ns = lo + d
                    if ns < pos["sl"]:
                        pos["sl"] = ns
                break

    def run(self, df):
        df = self.calc_indicators(df)
        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]
            if pd.isna(row["atr"]) or pd.isna(row["adx"]):
                continue

            if self.positions:
                p = self.positions[0]
                self.trail_update(p, row["high"], row["low"], row["atr"])
                ep, er = None, None
                if p["side"] == "LONG":
                    if row["low"] <= p["sl"]:
                        ep, er = p["sl"], "SL"
                    elif row["high"] >= p["tp"]:
                        ep, er = p["tp"], "TP"
                else:
                    if row["high"] >= p["sl"]:
                        ep, er = p["sl"], "SL"
                    elif row["low"] <= p["tp"]:
                        ep, er = p["tp"], "TP"
                if ep:
                    ep, c = self.apply_costs(ep, "SELL" if p["side"] == "LONG" else "BUY")
                    pnl = (ep - p["entry"]) * p["size"] if p["side"] == "LONG" else (p["entry"] - ep) * p["size"]
                    pnl -= c
                    self.capital += pnl
                    self.commissions += c
                    self.trades.append({
                        "entry_time": str(p["entry_time"]), "exit_time": str(row["timestamp"]),
                        "side": p["side"], "entry": round(p["entry"], 2), "exit": round(ep, 2),
                        "size": round(p["size"], 6), "pnl": round(pnl, 2),
                        "pnl_pct": round((pnl / p["ev"]) * 100, 2),
                        "reason": er, "bars": i - p["entry_bar"], "stage": p["stage"],
                    })
                    if pnl > 0:
                        self.wins += 1
                    else:
                        self.losses += 1
                    d = str(row["timestamp"].date())
                    m = row["timestamp"].strftime("%Y-%m")
                    self.daily_pnl[d] = self.daily_pnl.get(d, 0) + pnl
                    self.monthly_pnl[m] = self.monthly_pnl.get(m, 0) + pnl
                    self.positions = []

            if not self.positions:
                ok, st = self.check_filters(row)
                if not ok:
                    self.filter_stats[st] += 1
                    continue
                sig = self.check_signal(row, prev)
                if sig:
                    self.filter_stats["PASSED"] += 1
                    ep, c = self.apply_costs(row["close"], "BUY" if sig == "LONG" else "SELL")
                    if sig == "LONG":
                        sl, tp = ep - row["atr"] * 1.5, ep + row["atr"] * 3.0
                    else:
                        sl, tp = ep + row["atr"] * 1.5, ep - row["atr"] * 3.0
                    sz = (self.capital * RISK_PER_TRADE) / abs(ep - sl) if abs(ep - sl) > 0 else 0
                    if sz > 0:
                        self.positions.append({"side": sig, "entry": ep, "sl": sl, "tp": tp,
                            "size": sz, "entry_time": row["timestamp"], "entry_bar": i,
                            "stage": 0, "ev": self.capital * RISK_PER_TRADE})

            eq = self.capital
            if self.positions:
                p = self.positions[0]
                eq += (row["close"] - p["entry"]) * p["size"] if p["side"] == "LONG" else (p["entry"] - row["close"]) * p["size"]
            self.equity_curve.append({"t": str(row["timestamp"]), "e": round(eq, 2)})
            if eq > self.peak_equity:
                self.peak_equity = eq
            dd = ((self.peak_equity - eq) / self.peak_equity) * 100
            if dd > self.max_dd_pct:
                self.max_dd_pct = dd
                self.max_dd_usd = self.peak_equity - eq
        return self.report()

    def report(self):
        t = len(self.trades)
        wr = (self.wins / t * 100) if t else 0
        w = [x["pnl"] for x in self.trades if x["pnl"] > 0]
        l = [x["pnl"] for x in self.trades if x["pnl"] < 0]
        return {
            "summary": {
                "start": STARTING_CAPITAL, "end": round(self.capital, 2),
                "return_pct": round(((self.capital - STARTING_CAPITAL) / STARTING_CAPITAL) * 100, 2),
                "trades": t, "wins": self.wins, "losses": self.losses,
                "wr_pct": round(wr, 2), "avg_win": round(np.mean(w), 2) if w else 0,
                "avg_loss": round(np.mean(l), 2) if l else 0,
                "pf": round(abs(sum(w) / sum(l)), 2) if l else 99.99,
                "max_dd_pct": round(self.max_dd_pct, 2),
                "max_dd_usd": round(self.max_dd_usd, 2),
                "commissions": round(self.commissions, 2),
            },
            "filters": self.filter_stats,
            "trades": self.trades,
            "equity": self.equity_curve,
            "monthly": {k: round(v, 2) for k, v in self.monthly_pnl.items()},
        }


def dl(start, end):
    out = []
    cur = start
    while cur < end:
        e = min(cur + timedelta(days=7), end)
        r = requests.get("https://api.binance.com/api/v3/klines", params={
            "symbol": "BTCUSDT", "interval": "3m",
            "startTime": int(cur.timestamp() * 1000),
            "endTime": int(e.timestamp() * 1000), "limit": 1000}, timeout=30)
        d = r.json()
        if not d:
            break
        for c in d:
            out.append({"timestamp": pd.Timestamp(c[0], unit="ms"),
                        "open": float(c[1]), "high": float(c[2]),
                        "low": float(c[3]), "close": float(c[4]),
                        "volume": float(c[5])})
        cur = e
        time.sleep(0.2)
    return pd.DataFrame(out).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)


if __name__ == "__main__":
    end = datetime.now()
    start = end - timedelta(days=750)
    f = "/tmp/btc_3m.csv"
    print(f"Loading data...")
    df = pd.read_csv(f, parse_dates=["timestamp"]) if os.path.exists(f) else dl(start, end)
    if not os.path.exists(f):
        df.to_csv(f, index=False)
    print(f"Bars: {len(df)}")
    bt = BotV13Backtest()
    res = bt.run(df)
    with open("/root/Bot-v13/backtest_results.json", "w") as fp:
        json.dump(res, fp, indent=2)
    s = res["summary"]
    print(f"\nReturn: {s['return_pct']:+.2f}% | WR: {s['wr_pct']}% | Trades: {s['trades']} | PF: {s['pf']} | MaxDD: {s['max_dd_pct']}% (${s['max_dd_usd']})")
    print(f"Filters: {res['filters']}")
    print("\nMonthly:")
    for m in sorted(res["monthly"].keys()):
        print(f"  {m}: ${res['monthly'][m]:+,.2f}")
