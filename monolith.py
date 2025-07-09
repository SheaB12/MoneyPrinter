import os
import pandas as pd
import datetime
import random
from gpt_decider import gpt_decision
from logger import log_to_sheet

CONFIDENCE_THRESHOLD = 60

def load_spy_data():
    now = datetime.datetime.now()
    data = []
    for i in range(30):
        time = now - datetime.timedelta(minutes=30 - i)
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

def log_gpt_decision(decision: dict, action_taken: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_to_sheet([
        timestamp,
        decision.get("decision", "skip"),
        decision.get("confidence", 0),
        decision.get("reason", "No reason provided"),
        action_taken
    ])

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
        log_gpt_decision(decision, "SKIPPED")
        return

    print("\n🚀 Trade would be placed here (mocked).")
    log_gpt_decision(decision, "TRADE")

if __name__ == "__main__":
    run()
