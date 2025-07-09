import os
import json
import openai
import pandas as pd
from datetime import datetime
from logger import get_recent_logs, log_trade_decision
from alerts import send_threshold_change_alert

# Set up OpenAI key
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df: pd.DataFrame) -> dict:
    # Ensure 'Datetime' exists and is properly formatted
    if df.index.name is not None:
        df = df.reset_index()

    if "Datetime" not in df.columns:
        raise ValueError("Datetime column is missing after reset_index.")

    df["Datetime"] = pd.to_datetime(df["Datetime"])

    # Get last 30 minutes of data
    recent_data = df.tail(30).copy()
    recent_data.reset_index(drop=True, inplace=True)
    candle_records = recent_data[["Datetime", "Open", "High", "Low", "Close", "Volume"]].copy()
    candle_records["Datetime"] = candle_records["Datetime"].astype(str)
    candle_json = candle_records.to_dict(orient="records")

    try:
        recent_logs = get_recent_logs(limit=10)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    prompt = (
        "You are a trading assistant. Based on recent SPY 1-minute candles, decide whether to enter a call, put, or skip.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_json)}\n\n"
        f"Recent decisions and outcomes:\n\n{recent_logs}\n\n"
        "Return your decision in this JSON format ONLY:\n"
        '{"action": "call" | "put" | "skip", "confidence": float from 0 to 100, "reason": "..."}'
    )

    print("📡 Sending prompt to GPT...")

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a disciplined financial trading assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    reply = response.choices[0].message['content'].strip()

    print("🤖 GPT replied:")
    print(reply)

    try:
        decision_data = json.loads(reply)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse GPT response: {reply}") from e

    # Log decision
    log_trade_decision(decision_data)

    return decision_data
