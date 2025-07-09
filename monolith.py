import os
import time
import yfinance as yf
import warnings
from dotenv import load_dotenv
from gpt_decider import gpt_decision
from execution import execute_trade
from alerts import send_trade_alert
from logger import log_trade_decision

# Load environment variables
load_dotenv()
warnings.simplefilter(action='ignore', category=FutureWarning)

def run():
    print("\n📈 Fetching SPY...\n")

    # ✅ Download SPY 1-min data for today
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    if df.empty:
        raise ValueError("SPY data fetch failed or returned empty.")

    print("\n\n🧠 GPT making decision...\n")
    decision_data = gpt_decision(df)

    decision = decision_data.get("decision", "SKIP")
    confidence = decision_data.get("confidence", 0.0)
    reason = decision_data.get("reason", "")
    threshold = decision_data.get("threshold", 0.6)

    print(f"✅ GPT Decision: {decision}")
    print(f"📊 Confidence: {confidence:.2f} (Threshold: {threshold:.2f})")
    print(f"🧠 Reason: {reason}")

    # ✅ Skip trade if confidence is below threshold
    if decision == "SKIP" or confidence < threshold:
        print("🚫 Trade skipped due to low confidence or GPT recommendation.")
        log_trade_decision("SKIP", confidence, threshold, reason, status="skipped")
        return

    # ✅ Execute paper trade using Tradier API
    print("🚀 Placing trade...")
    result = execute_trade(decision)

    # ✅ Log to Sheets and send Discord alert
    status = result.get("status", "error")
    trade_price = result.get("price", "N/A")
    trade_symbol = result.get("symbol", "N/A")

    log_trade_decision(decision, confidence, threshold, reason, status, symbol=trade_symbol, price=trade_price)
    send_trade_alert(decision, confidence, threshold, reason, status, symbol=trade_symbol, price=trade_price)

if __name__ == "__main__":
    run()
