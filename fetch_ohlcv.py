import requests, pandas as pd, time
from datetime import datetime, timedelta

print("Downloading 25 months of BTC 3m data...")
url = "https://api.binance.com/api/v3/klines"
all_data = []
end_ms = int(datetime.now().timestamp() * 1000)
start_ms = int((datetime.now() - timedelta(days=750)).timestamp() * 1000)

cur = start_ms
chunk = 7 * 24 * 60 * 60 * 1000

while cur < end_ms:
    chunk_end = min(cur + chunk, end_ms)
    try:
        r = requests.get(url, params={
            "symbol": "BTCUSDT", "interval": "3m",
            "startTime": cur, "endTime": chunk_end, "limit": 1000
        }, timeout=30)
        data = r.json()
        if not data or not isinstance(data, list):
            break
        for k in data:
            all_data.append({
                "timestamp": pd.to_datetime(k[0], unit="ms"),
                "open": float(k[1]), "high": float(k[2]),
                "low": float(k[3]), "close": float(k[4]),
                "volume": float(k[5])
            })
        cur = chunk_end
        time.sleep(0.2)
        if len(all_data) % 5000 < 1000:
            print(f"  Downloaded {len(all_data)} bars...")
    except Exception as e:
        print(f"  Error: {e}")
        time.sleep(5)

df = pd.DataFrame(all_data).drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
df.to_csv("ohlcv_3m.csv", index=False)
print(f"Saved {len(df)} bars from {df['timestamp'].min()} to {df['timestamp'].max()}")
