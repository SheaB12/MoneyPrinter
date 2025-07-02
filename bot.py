import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from config import OPENAI_API_KEY, TRADIER_TOKEN, ACCOUNT_ID
from trade_executor import place_option_trade
from gpt_decider import gpt_decision
from trailing_manager import check_trailing_and_update


def fetch_intraday_data():
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df = df.dropna().tail(30)
    return df

def run_bot():
    print("📈 Checking current trades...")
    check_trailing_and_update()

    print("🧠 Running GPT decision logic...")
    df = fetch_intraday_data()
    decision, confidence, reason, stop_pct, target_pct = gpt_decision(df)

    if confidence < 60 or decision == "skip":
        print(f"⚠️ SKIP: Confidence {confidence}% | Reason: {reason}")
        return

    print(f"✅ GPT Decision: {decision.upper()} | Confidence: {confidence}% | Reason: {reason}")

    result = place_option_trade(decision)
    if result["status"] == "success":
        log_trade(decision, result["symbol"], result["price"], stop_pct, target_pct, reason)
        print(f"📤 TRADE PLACED: {decision.upper()} {result['symbol']} @ ${result['price']:.2f}")
    else:
        print(f"❌ TRADE ERROR: {result['error']}")

def log_trade(direction, symbol, entry_price, stop_pct, target_pct, reason):
    trade = {
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Direction": direction,
        "Symbol": symbol,
        "EntryPrice": entry_price,
        "StopLoss%": stop_pct,
        "Target%": target_pct,
        "Reason": reason,
        "PnL": 0.0,
        "Status": "OPEN",
        "Tplus1": "Pending"
    }

    try:
        df = pd.read_csv("trade_log.csv")
        df = pd.concat([df, pd.DataFrame([trade])], ignore_index=True)
    except FileNotFoundError:
        df = pd.DataFrame([trade])

    df.to_csv("trade_log.csv", index=False)

def check_tplus1():
    try:
        df = pd.read_csv("trade_log.csv")
        open_trades = df[df["Status"] == "OPEN"]

        if open_trades.empty:
            return

        df_live = fetch_intraday_data()
        for idx, row in open_trades.iterrows():
            tstamp = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S")
            if datetime.now().date() > tstamp.date() and row.get("Tplus1", "") != "Checked":
                # Re-analyze with GPT
                decision, confidence, reason, _, _ = gpt_decision(df_live)

                if confidence < 60 or decision != row["Direction"]:
                    df.at[idx, "Status"] = "CLOSED"
                    df.at[idx, "PnL"] = 0.0
                    df.at[idx, "Tplus1"] = "Closed"
                    print(f"🔁 T+1 EXIT: Closed stale trade due to weak conviction.")
                else:
                    df.at[idx, "Tplus1"] = "Continued"
                    print(f"🔄 T+1 CONTINUED: Trade remains valid.")

        df.to_csv("trade_log.csv", index=False)

    except Exception as e:
        print(f"⚠️ T+1 logic error: {e}")

if __name__ == "__main__":
    run_bot()
    check_tplus1()
