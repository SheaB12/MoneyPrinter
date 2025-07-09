import os
import openai
import yfinance as yf
import pandas as pd
from datetime import datetime
from gpt_decider import gpt_decision
from logger import log_to_sheet
from notifier import send_discord_alert

CONFIDENCE_THRESHOLD = 0.60

def fetch_spy_data():
    print("\n📈 Fetching SPY...")
    spy = yf.Ticker("SPY")
    df = spy.history(interval="1m", period="1d")  # Get full day of 1-min data
    df = df.tail(30)  # Last 30 minutes
    df.reset_index(inplace=True)
    df['timestamp'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df

def log_gpt_decision(decision, action):
    log_to_sheet([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        decision["direction"],
        f"{decision['confidence']:.2%}",
        decision["reason"],
        action
    ])
    send_discord_alert(
        decision=decision["direction"],
        confidence=decision["confidence"],
        reason=decision["reason"],
        action=action
    )

def run():
    data = fetch_spy_data()
    print("\n🧠 GPT making decision...")
    decision = gpt_decision(data)

    print(f"\n🪩 Decision: {decision['direction'].upper()}")
    print(f"✅ Confidence: {decision['confidence']:.0%}")
    print(f"💬 Reason: {decision['reason']}\n")

    if decision["confidence"] >= CONFIDENCE_THRESHOLD:
        action = "TRADE"
        print("🚀 Executing trade... (not implemented here)")
    else:
        action = "SKIPPED"
        print("⚠️ No Trade")

    log_gpt_decision(decision, action)

if __name__ == "__main__":
    run()
