import os
import pandas as pd
import datetime as dt
import random
from gpt_decider import gpt_decision

CONFIDENCE_THRESHOLD = 60

def load_spy_data():
    """
    Mock function to simulate last 30 minutes of SPY 1-minute candles.
    Replace with real data fetching later.
    """
    now = dt.datetime.now()
    data = []

    for i in range(30):
        time = now - dt.timedelta(minutes=30 - i)
        price = 445 + random.uniform(-1, 1)
        candle = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": price - 0.1,
            "high": price + 0.2,
            "low": price - 0.2,
            "close": price,
            "volume": random.randint(500000, 1000000)
        }
        data.append(candle)

    return pd.DataFrame(data)

def run():
    print("📈 Fetching SPY...")

    try:
        df = load_spy_data()
    except Exception as e:
        print(f"❌ Error loading SPY data: {e}")
        return

    print("\n🧠 GPT making decision...")

    decision = gpt_decision(df)

    action = decision.get("decision", "skip")
    confidence = decision.get("confidence", 0)
    reason = decision.get("reason", "No reason provided")

    print(f"\n🪩 Decision: {action.upper()}")
    print(f"✅ Confidence: {confidence}%")
    print(f"💬 Reason: {reason}")

    if action.lower() == "skip" or confidence < CONFIDENCE_THRESHOLD:
        print("\n⚠️ No Trade")
        return

    print("\n🚀 Trade would be placed here (mocked).")
    # Optional: call execute_trade(action, decision) if you want real trading logic

if __name__ == "__main__":
    run()
