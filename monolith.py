import os
import time
import yfinance as yf
from gpt_decider import gpt_decision
from execution import execute_trade
from alerts import send_trade_alert
from logger import log_trade_result

def run():
    print("\n📈 Fetching SPY...\n")
    df = yf.download("SPY", interval="1m", period="1d", progress=False)

    if df.empty:
        raise ValueError("No data fetched for SPY. Check internet or API limits.")

    print("\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    action = decision_data.get("action", "").lower()
    confidence = float(decision_data.get("confidence", 0.0))
    reason = decision_data.get("reason", "No reason provided.")

    if action in ["call", "put"]:
        print(f"\n🚀 Executing {action.upper()} trade...")
        result = execute_trade(action=action, confidence=confidence)

        # Log and alert the trade
        log_trade_result(result)
        send_trade_alert(
            action=result["action"],
            confidence=result["confidence"],
            status=result["status"],
            pnl=result["pnl"],
            reason=reason
        )

    else:
        print("⛔ No trade executed. GPT recommended to SKIP.")

if __name__ == "__main__":
    run()
