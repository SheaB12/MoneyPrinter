import os
import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from logger import log_to_sheet
from alerts import send_trade_alert
from execution import execute_trade
from datetime import datetime

def run():
    print("\n\n📈 Fetching SPY...\n")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    if df.empty:
        print("⚠️ Failed to fetch SPY data.")
        return

    print("\n\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    direction = decision_data["decision"]
    confidence = decision_data["confidence"]
    reason = decision_data["reason"]
    threshold = decision_data["threshold"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Skipped" if direction == "SKIP" or confidence < threshold else "Planned"

    log_to_sheet([now, direction, confidence, status, reason])
    send_trade_alert(direction, confidence, reason, threshold, status)

    if direction != "SKIP" and confidence >= threshold:
        print("🛠 Executing trade...\n")
        execute_trade(direction, confidence, reason)
    else:
        print("🚫 No trade executed due to low confidence or SKIP signal.\n")

if __name__ == "__main__":
    run()
