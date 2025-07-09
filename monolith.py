import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from logger import log_to_sheet
from discord_webhook import send_discord_alert


def fetch_spy_data():
    df = yf.download("SPY", interval="1m", period="1d")
    df.reset_index(inplace=True)
    df['timestamp'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]


def log_gpt_decision(decision, trade_status):
    log_to_sheet([
        pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        decision.get("direction", "N/A"),
        decision.get("confidence", 0),
        decision.get("reason", ""),
        trade_status
    ], tab="GPT Decisions")


def run():
    print("\n📈 Fetching SPY...")
    data = fetch_spy_data()

    print("\n🧠 GPT making decision...")
    decision = gpt_decision(data)

    # Print GPT decision
    print(f"\n🪩 Decision: {decision['direction'].upper()}")
    print(f"\n✅ Confidence: {decision['confidence']:.2%}")
    print(f"\n💬 Reason: {decision['reason']}")

    if decision['confidence'] >= 0.60:
        trade_status = "TRADE"
        print("\n🚀 Trade signal confirmed!")
    else:
        trade_status = "SKIPPED"
        print("\n⚠️ No Trade")

    # Log and alert
    log_gpt_decision(decision, trade_status)
    send_discord_alert(decision, trade_status)


if __name__ == "__main__":
    run()
