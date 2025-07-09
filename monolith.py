import os
import pandas as pd
from gpt_decider import gpt_decision
from data_loader import load_spy_data  # Assumes you have a data loader function
from trade_executor import execute_trade  # Optional: used if you want to act on decision

CONFIDENCE_THRESHOLD = 60

def run():
    print("📈 Fetching SPY...")

    try:
        df = load_spy_data()  # This function should return a pandas DataFrame
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

    # Optional: call execute_trade if you're ready to place trades directly
    # print("\n🚀 Executing trade...")
    # execute_trade(action, decision)

if __name__ == "__main__":
    run()
