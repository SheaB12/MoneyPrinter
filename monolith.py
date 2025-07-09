import os
import json
import datetime
import yfinance as yf
from gpt_decider import gpt_decision
from logger import log_to_sheet
from alerts import send_discord_alert
from strategy import determine_market_regime
from threshold import calculate_dynamic_threshold

def fetch_spy_data():
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df.reset_index(inplace=True)
    df = df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
    return df.tail(30)

def format_discord_message(decision, status):
    return (
        f"🪩 **Decision:** {decision['direction'].upper()}\n"
        f"✅ **Confidence:** {decision['confidence'] * 100:.2f}%\n"
        f"💬 **Reason:** {decision['reason']}\n"
        f"📊 **Status:** {status}"
    )

def log_gpt_decision(decision, status):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_to_sheet([
        timestamp,
        decision["direction"],
        decision["confidence"],
        status,
        decision["reason"]  # ✅ GPT reasoning logged
    ])

def run():
    print("\n📈 Fetching SPY...\n")
    data = fetch_spy_data()

    print("🧠 GPT making decision...\n")
    decision = gpt_decision(data)

    market_regime = determine_market_regime(data)
    decision["market_regime"] = market_regime

    dynamic_threshold, threshold_changed = calculate_dynamic_threshold()

    confidence = decision["confidence"]
    status = "EXECUTED" if confidence >= dynamic_threshold else "SKIPPED"

    if threshold_changed:
        send_discord_alert(f"⚠️ **Confidence Threshold Updated:**\nNew threshold = {dynamic_threshold*100:.1f}%")

    print(f"\n🪩 Decision: {decision['direction'].upper()}")
    print(f"✅ Confidence: {confidence * 100:.2f}%")
    print(f"💬 Reason: {decision['reason']}")
    print(f"\n{'✅ TRADE PLACED' if status == 'EXECUTED' else '⚠️ No Trade'}")

    log_gpt_decision(decision, status)
    send_discord_alert(format_discord_message(decision, status))

if __name__ == "__main__":
    run()
