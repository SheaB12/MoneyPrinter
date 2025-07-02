import pandas as pd
import requests
from config import TRADIER_TOKEN, ACCOUNT_ID

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json"
}

def get_spy_price():
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    params = {"symbols": "SPY"}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return float(data["quotes"]["quote"]["last"])

def check_trailing_and_update():
    try:
        df = pd.read_csv("trade_log.csv")
        open_trades = df[df["Status"] == "OPEN"]

        if open_trades.empty:
            print("📭 No open trades to monitor.")
            return

        current_price = get_spy_price()
        print(f"🔍 Current SPY price: {current_price:.2f}")

        for idx, row in open_trades.iterrows():
            direction = row["Direction"].lower()
            entry = float(row["EntryPrice"])
            stop_pct = float(row["StopLoss%"]) / 100
            target_pct = float(row["Target%"]) / 100

            if direction == "call":
                gain = (current_price - entry) / entry
            else:  # put
                gain = (entry - current_price) / entry

            pnl_percent = round(gain * 100, 2)

            # Check for exit conditions
            if gain <= -stop_pct:
                df.at[idx, "Status"] = "CLOSED"
                df.at[idx, "PnL"] = pnl_percent
                print(f"🛑 STOP HIT: {direction.upper()} closed at {pnl_percent}%")
            elif gain >= target_pct:
                df.at[idx, "Status"] = "CLOSED"
                df.at[idx, "PnL"] = pnl_percent
                print(f"🎯 TARGET HIT: {direction.upper()} closed at {pnl_percent}%")
            else:
                # Still open, update unrealized PnL
                df.at[idx, "PnL"] = pnl_percent

        df.to_csv("trade_log.csv", index=False)

    except Exception as e:
        print(f"❌ Trailing stop logic error: {e}")
