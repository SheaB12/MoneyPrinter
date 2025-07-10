# gpt_decider.py

import os
import json
import openai
import datetime as dt
import pandas as pd

from logger import get_sheet, get_recent_logs, log_trade_decision
from alerts import send_discord_decision_alert  # ✅ Make sure this is defined in alerts.py

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    sheet = get_sheet()

    # ✅ Flatten multi-index columns from yfinance if present
    if isinstance(df.columns[0], tuple):
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns]

    # ✅ Normalize column names
    df.columns = [col.lower().capitalize() for col in df.columns]

    # ✅ Ensure necessary columns exist
    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"Missing required columns: {required_columns}")

    # ✅ Clean and trim data
    df = df.dropna(subset=required_columns).tail(30)

    candle_records = []
    for timestamp, row in df.iterrows():
        candle_records.append({
            "time": str(timestamp),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })

    try:
        recent_logs = get_recent_logs(sheet)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    prompt = (
        "You are a trading assistant helping with SPY options decisions.\n"
        "Choose one: 'call', 'put', or 'skip'.\n"
        f"Here is the last 30 minutes of SPY 1-minute candles:\n\n{json.dumps(candle_records)}\n\n"
        f"Recent trade history:\n{json.dumps(recent_logs)}\n\n"
        "What should we do next and why? Respond ONLY in JSON like:\n"
        '{"action": "call", "confidence": 75, "reason": "Your reason here"}'
    )

    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert SPY trader using 1-min chart data."},
            {"role": "user", "content": prompt}
        ]
    )

    reply = response["choices"][0]["message"]["content"]
    print("🤖 GPT replied:\n")
    print(reply)

    try:
        decision_data = json.loads(reply)
    except json.JSONDecodeError:
        decision_data = {
            "action": "skip",
            "confidence": 0,
            "reason": "Unable to parse GPT reply."
        }

    decision_data["timestamp"] = dt.datetime.now().isoformat()
    decision_data["strategy"] = "GPT"

    # ✅ Log decision and send alert
    log_trade_decision(decision_data)
    send_discord_decision_alert(decision_data)

    return decision_data
