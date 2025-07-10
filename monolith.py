import yfinance as yf
from gpt_decider import gpt_decision
from alerts import send_daily_summary
from datetime import datetime

def run():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    print("🧠 GPT making decision...")
    try:
        decision_data = gpt_decision(df)
        print("✅ Decision made:", decision_data)
    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        decision_data = None

    # Send EOD performance summary if after market close
    now = datetime.utcnow()
    if now.hour >= 20:  # 4 PM EST or later
        print("📤 Sending EOD summary...")
        try:
            send_daily_summary()
        except Exception as e:
            print(f"❌ Error sending summary: {e}")

if __name__ == "__main__":
    run()
