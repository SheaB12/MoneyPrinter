import os
import time
import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from alerts import send_discord_alert
from logger import log_to_sheet

def run():
    print("\n📈 Fetching SPY...\n")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    if df.empty:
        print("❌ No SPY data fetched.")
        return

    df = df.copy()
    df.reset_index(inplace=True)

    # Rename the datetime column to match expectations
    if 'Datetime' not in df.columns and 'index' in df.columns:
        df.rename(columns={"index": "Datetime"}, inplace=True)
    elif 'Date' in df.columns:
        df.rename(columns={"Date": "Datetime"}, inplace=True)

    # Ensure all required columns exist
    required_columns = ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
    for col in required_columns:
        if col not in df.columns:
            print(f"❌ Missing column: {col}")
            return

    print("\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    direction = decision_data.get("decision", "SKIP").upper()
    confidence = round(float(decision_data.get("confidence", 0.0)), 2)
    reason = decision_data.get("reason", "No reasoning provided.")
    threshold = round(float(decision_data.get("threshold", 0.6)), 2)

    timestamp = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # Assign trade status (simulate result for now)
    if direction in ["CALL", "PUT"]:
        status = "PENDING"  # Placeholder for live result later
        color = 0x3498db
    else:
        status = "SKIPPED"
        color = 0x95a5a6

    # Log to Google Sheets
    log_to_sheet([timestamp, direction, confidence, status, reason])

    # Send Discord alert
    send_discord_alert(
        title=f"🤖 GPT Decision: {direction}",
        description=(
            f"**Confidence:** {confidence:.2f} (Threshold: {threshold:.2f})\n"
            f"**Status:** {status}\n"
            f"**Reason:** {reason}"
        ),
        color=color
    )

if __name__ == "__main__":
    run()
