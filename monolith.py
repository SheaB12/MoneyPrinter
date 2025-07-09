import os
import time
import yfinance as yf
import pandas as pd
from datetime import datetime
from gpt_decider import gpt_decision
from logger import log_to_sheet
from execution import execute_trade
from alerts import send_trade_alert
from strategy import determine_market_regime

def run():
    print("\n📈 Fetching SPY...\n")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df = df.copy()

    # Reset index and ensure datetime column is correctly named
    df.reset_index(inplace=True)
    if "index" in df.columns:
        df.rename(columns={"index": "Datetime"}, inplace=True)
    elif "Date" in df.columns:
        df.rename(columns={"Date": "Datetime"}, inplace=True)
    elif "Datetime" not in df.columns:
        raise ValueError("❌ Could not locate a datetime column after reset.")

    if df.empty:
        raise ValueError("❌ No SPY data returned from yfinance.")

    print("\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    direction = decision_data["decision"].upper()
    confidence = float(decision_data["confidence"])
    reason = decision_data.get("reason", "No reason provided.")
    threshold = decision_data.get("threshold", 0.60)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Log and alert GPT's decision
    status = "PENDING"
    row = [timestamp, direction, round(confidence, 2), status, reason]
    log_to_sheet(row)

    print(f"🤖 GPT Decision: {direction} (Confidence: {confidence:.2f}, Threshold: {threshold:.2f})")
    print(f"📌 Reason: {reason}")

    if direction == "SKIP" or confidence < threshold:
        print(f"\n⛔ Skipping trade (confidence {confidence:.2f} < threshold {threshold:.2f})")
        return

    # Execute simulated trade
    print("\n🚀 Executing trade...")
    result = execute_trade(direction)
    print(f"\n✅ Trade Executed: {result}")

    # Send Discord alert
    send_trade_alert(direction, confidence, reason, threshold)

if __name__ == "__main__":
    run()
