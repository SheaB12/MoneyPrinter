import yfinance as yf
from gpt_decider import gpt_decision
from alerts import send_daily_summary

def run():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=False)

    # Handle MultiIndex column format
    if isinstance(df.columns, tuple) or hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(-1)
    df = df.reset_index()

    print("🧠 GPT making decision...")
    decision_data = gpt_decision(df)

    if decision_data and decision_data.get("action") != "skip":
        print("✅ Trade decision logged.")
    else:
        print("🚫 No trade taken.")

    print("📅 Sending EOD summary...")
    send_daily_summary()

if __name__ == "__main__":
    run()
