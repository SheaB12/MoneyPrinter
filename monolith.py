import os
import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from logger import log_to_sheet
from alerts import send_discord_alert
from datetime import datetime

def log_gpt_decision(decision, status):
    log_to_sheet([
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        decision["decision"],
        round(decision["confidence"], 2),
        status,
        decision["reason"]  # ✅ Include GPT commentary
    ])

def format_discord_message(decision, status):
    return (
        f"**🎯 GPT Trade Decision**\n\n"
        f"**Action**: `{decision['decision']}`\n"
        f"**Confidence**: `{round(decision['confidence'] * 100)}%`\n"
        f"**Status**: `{status}`\n"
        f"**Threshold**: `{round(decision['threshold'] * 100)}%`\n"
        f"**Reason**: {decision['reason']}"
    )

def run():
    print("\n📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    if df.empty:
        print("⚠️ No data fetched.")
        return

    df = df.reset_index().rename(columns={"index": "Datetime"})
    df["Datetime"] = pd.to_datetime(df["Datetime"])

    print("\n🧠 GPT making decision...")
    decision = gpt_decision(df)

    if decision["decision"].upper() not in ["CALL", "PUT"]:
        status = "SKIPPED"
    else:
        status = "PENDING"

    print(f"\n🪩 Decision: {decision['decision'].upper()} @ {round(decision['confidence'] * 100)}%")
    log_gpt_decision(decision, status)
    send_discord_alert(format_discord_message(decision, status))

if __name__ == "__main__":
    run()
