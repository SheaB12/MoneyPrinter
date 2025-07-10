import json
import openai
import os
import pandas as pd
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs

openai.api_key = os.getenv("OPENAI_API_KEY")

def determine_strike_type(action: str) -> str:
    """
    Determines whether the option should be ATM, ITM, or OTM
    based on backtested performance for the given action.
    """
    strike_lookup = {
        "call": "ATM",
        "put": "ITM"
    }
    return strike_lookup.get(action.lower(), "ATM")

def gpt_decision(df: pd.DataFrame) -> dict:
    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    df.columns = [str(col).capitalize() for col in df.columns]

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    df = df.dropna(subset=required_columns)
    df = df.tail(30)

    candle_records = []
    for index, row in df.iterrows():
        candle_records.append({
            "timestamp": str(index),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        })

    prompt = (
        f"You are a financial trading assistant. Based on the last 30 minutes of SPY 1-minute candle data, "
        f"recommend a CALL or PUT options trade. Also provide confidence (0-100) and a brief reason.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        f"Reply ONLY in JSON format with keys: action, confidence, reason."
    )

    try:
        print("📡 Sending prompt to GPT...")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        reply = response.choices[0].message.content.strip()
        print("🤖 GPT Reply:\n", reply)

        decision_data = json.loads(reply)
        action = decision_data.get("action", "").lower()
        confidence = int(decision_data.get("confidence", 0))
        reason = decision_data.get("reason", "")

        strike_type = determine_strike_type(action)
        decision_data["strike_type"] = strike_type
        decision_data["expiration"] = "End of Day"

        send_trade_alert(action, confidence, reason, strike_type)

        return decision_data

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        return {"error": str(e)}
