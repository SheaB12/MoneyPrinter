import os
import yfinance as yf
from gpt_decider import gpt_decision
from alerts import send_discord_alert, format_discord_message, alert_threshold_change
from logger import log_to_sheet, SHEET_NAME, get_recent_stats

def fetch_spy_data():
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df.reset_index(inplace=True)
    df['timestamp'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df.tail(30)

def log_gpt_decision(decision, status):
    log_to_sheet([
        decision["timestamp"],
        decision["decision"],
        decision["confidence"],
        decision["reason"],
        status
    ], "GPT Decisions")

def run():
    print("\n📈 Fetching SPY...")
    data = fetch_spy_data()

    print("\n🧠 GPT making decision...")
    recent_stats = get_recent_stats()
    decision, threshold, old_threshold = gpt_decision(data, recent_stats)

    status = "EXECUTED" if decision["confidence"] >= threshold else "SKIPPED"
    print(f"\n🪩 Decision: {decision['decision'].upper()}")
    print(f"✅ Confidence: {decision['confidence']*100:.2f}%")
    print(f"💬 Reason: {decision['reason']}")
    print(f"{'📈 Trade Executed' if status == 'EXECUTED' else '⚠️ No Trade'}")

    log_gpt_decision(decision, status)
    send_discord_alert(format_discord_message(decision, status))

    if abs(threshold - old_threshold) >= 0.05:
        alert_threshold_change(threshold, old_threshold)

if __name__ == "__main__":
    run()
