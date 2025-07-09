import os
import pandas as pd
import yfinance as yf
from gpt_decider import gpt_decision
from logger import log_to_sheet
from alerts import send_discord_alert

def fetch_spy_data():
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df.reset_index(inplace=True)
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df["timestamp"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')
    return df

def log_gpt_decision(decision, status):
    log_to_sheet([
        pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        decision.get("decision", "N/A"),
        decision.get("confidence", "N/A"),
        decision.get("reason", "N/A"),
        status
    ])

def format_discord_message(decision, status):
    status_label = "✅ Trade Executed" if status == "TRADED" else "⚠️ No Trade"
    emoji = "🟩" if decision.get("decision") == "CALL" else "🟥"

    return (
        f"**📈 GPT Options Decision**\n\n"
        f"{emoji} **Decision**: `{decision.get('decision', 'N/A')}`\n"
        f"📊 **Confidence**: `{round(decision.get('confidence', 0) * 100, 2)}%`\n"
        f"🧠 **Reason**:\n> {decision.get('reason', 'N/A')}\n\n"
        f"{status_label}"
    )

def run():
    print("\n📈 Fetching SPY...\n")
    data = fetch_spy_data()

    print("🧠 GPT making decision...\n")
    decision = gpt_decision(data)

    confidence = decision.get("confidence", 0)
    decision_direction = decision.get("decision", "").upper()
    status = "SKIPPED"

    if confidence >= 0.6 and decision_direction in ["CALL", "PUT"]:
        # Here is where a trade would be placed.
        status = "TRADED"

    log_gpt_decision(decision, status)
    send_discord_alert(format_discord_message(decision, status))

    print(f"\n🪩 Decision: {decision_direction}")
    print(f"✅ Confidence: {round(confidence * 100, 2)}%")
    print(f"💬 Reason: {decision.get('reason')}")
    print(f"{'✅ Trade Executed' if status == 'TRADED' else '⚠️ No Trade'}")

if __name__ == "__main__":
    run()
