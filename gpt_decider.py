import openai
import os
import json
from datetime import datetime
from logger import get_sheet, get_recent_logs, log_trade_decision
from alerts import send_trade_alert
import pandas as pd

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    # Normalize columns
    df.columns = [str(col).strip().capitalize() for col in df.columns]
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    df = df.dropna(subset=required_columns)
    if df.empty or len(df) < 30:
        print("⚠️ Not enough data for decision.")
        return {"action": "skip", "confidence": 0, "reason": "Not enough valid candles."}

    sheet = get_sheet()
    try:
        recent_logs = get_recent_logs(sheet, tab="Results")
    except Exception as e:
        print(f"Error fetching logs: {e}")
        recent_logs = []

    # Get last 30 candles
    last_30 = df.tail(30)
    candle_records = [
        {
            "time": row["Datetime"].strftime("%H:%M"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"]),
        }
        for _, row in last_30.iterrows()
    ]

    prompt = (
        "You are a professional SPY options trader. Based on the last 30 one-minute candles, "
        "decide if you would BUY CALL, BUY PUT, or SKIP. Include a confidence score (0-100) and brief reason.\n\n"
        f"{json.dumps(candle_records)}"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    reply = response['choices'][0]['message']['content']
    try:
        decision_data = json.loads(reply)
    except json.JSONDecodeError:
        print("❌ GPT response not valid JSON.")
        return {"action": "skip", "confidence": 0, "reason": "Invalid JSON response"}

    # Log and send alert
    log_trade_decision(decision_data)
    send_trade_alert(
        action=decision_data.get("action", "skip"),
        confidence=decision_data.get("confidence", 0),
        reason=decision_data.get("reason", "No reason provided.")
    )

    return decision_data
