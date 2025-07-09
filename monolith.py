import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from trade_executor import execute_trade
from logger import log_to_sheet
from discord_alerts import send_discord_alert

def fetch_spy_data():
    print("\n📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d")
    df.reset_index(inplace=True)
    df['timestamp'] = df['Datetime'].dt.strftime('%Y-%m-%d %H:%M')
    return df.tail(30)

def log_gpt_decision(decision, trade_status):
    log_to_sheet([
        pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        decision['decision'],
        decision['confidence'],
        decision['reason'],
        trade_status
    ], sheet_name="GPT Decisions", tab="GPT Decisions", headers=[
        "Timestamp", "Decision", "Confidence", "Reason", "Trade Status"
    ])

def run():
    data = fetch_spy_data()
    print("\n🧠 GPT making decision...")
    decision = gpt_decision(data)

    print(f"\n🪩 Decision: {decision['decision'].upper()}")
    print(f"✅ Confidence: {decision['confidence'] * 100:.2f}%")
    print(f"💬 Reason: {decision['reason']}")

    if decision["confidence"] >= 0.60:
        send_discord_alert(
            title="📈 GPT Trade Signal",
            description=f"**{decision['decision'].upper()}** | Confidence: `{decision['confidence'] * 100:.2f}%`\n\n💡 {decision['reason']}",
            status="EXECUTED"
        )
        execute_trade(direction=decision["decision"])
        log_gpt_decision(decision, "EXECUTED")
    else:
        send_discord_alert(
            title="⚠️ GPT Skipped Trade",
            description=f"**{decision['decision'].upper()}** | Confidence: `{decision['confidence'] * 100:.2f}%`\n\n💡 {decision['reason']}",
            status="SKIPPED"
        )
        log_gpt_decision(decision, "SKIPPED")

if __name__ == "__main__":
    run()
