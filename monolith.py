import os
import time
import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from execution import execute_trade
from alerts import send_trade_alert
from logger import log_to_sheet

def run():
    print("\n📈 Fetching SPY...\n")

    # Download 1-minute data for SPY
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    if df.empty:
        print("❌ No data retrieved.")
        return

    # ✅ Ensure Datetime column exists and is clean
    df = df.reset_index()
    df = df.rename(columns={"index": "Datetime"}) if "index" in df.columns else df
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]  # Only keep needed columns

    print("\n\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    direction = decision_data.get("decision", "SKIP")
    confidence = decision_data.get("confidence", 0.0)
    reason = decision_data.get("reason", "No reason provided")
    threshold = decision_data.get("threshold", 0.6)

    print(f"\n🤖 GPT Decision: {direction} | Confidence: {confidence:.2f} | Threshold: {threshold:.2f}")
    print(f"📌 Reason: {reason}")

    if direction in ["CALL", "PUT"] and confidence >= threshold:
        status = execute_trade(direction)
    else:
        status = "SKIPPED"

    # Log the result
    timestamp = pd.Timestamp.now(tz='US/Eastern').strftime("%Y-%m-%d %H:%M:%S")
    log_to_sheet([timestamp, direction, confidence, status, reason])

    # Send alert to Discord
    send_trade_alert(
        direction=direction,
        confidence=confidence,
        threshold=threshold,
        reason=reason,
        status=status
    )

if __name__ == "__main__":
    run()
