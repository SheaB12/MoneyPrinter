# gpt_decider.py

import os
import json
import openai
import datetime as dt
import pandas as pd
from logger import get_sheet, get_recent_logs, log_trade_decision
from alerts import send_discord_decision_alert

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    sheet = get_sheet()

    # ✅ Flatten MultiIndex columns if needed
    if isinstance(df.columns[0], tuple):
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns]

    # ✅ Normalize columns for consistency
    df.columns = [col.lower().capitalize() for col in df.columns]

    # ✅ Clean data
    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required_columns):
        raise KeyError(f"Missing required columns: {required_columns}")

    df = df.dropna(subset=required_columns)
    df = df.tail(30)

    # ✅ Build candle records for GPT input
    candle_records = []
    for timestamp, row in df.iterrows():
        candle = {
            "time": str(timestamp),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        }
        candle_records.append(candle)

    try:
        recent_logs = get_recent_logs(sheet)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    prompt = (
        "You are a trading assistant helping with SPY options decisions.\n"
        "Your choices are: 'call', 'put', or 'skip'.\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        f"Recent decisions: {json.dumps(recent_logs)}\n\n"
        "What should we do next and why? Respond with a JSON like:\n"
        '{"action": "call", "confidence": 75, "reason": "Your explanation here"}'
    )

    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial analyst making SPY trade decisions."},
            {"role": "user", "content": prompt}
        ]
    )

    reply = response["choices"][0]["message"]["content"]
    print("🤖 GPT replied:\n")
    print(reply)

    try:
        decision_data = json.loads(reply)
    except json.JSONDecodeError:
        decision_data = {"action": "skip", "confidence": 0, "reason": "Could not parse GPT response."}

    # ✅ Log decision
    decision_data["timestamp"] = dt.datetime.now().isoformat()
    decision_data["strategy"] = "GPT"
    log_trade_decision(decision_data)

    # ✅ Send Discord alert
    send_discord_decision_alert(decision_data)

    return decision_data
