import os
import json
import openai
import pandas as pd
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs, log_trade_decision

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    # 🧼 Fix column formatting if yfinance returns MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 📋 Ensure required columns exist
    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    # 🧹 Drop rows with NaNs in required columns
    df = df.dropna(subset=required_columns)

    # 🕒 Use last 30 minutes of data
    df_recent = df.tail(30)

    # 🔁 Reformat candles
    candle_records = []
    for timestamp, row in df_recent.iterrows():
        candle_records.append({
            "time": timestamp.strftime("%H:%M"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })

    # 📚 Context prompt
    try:
        sheet = get_sheet()
        recent_logs = get_recent_logs(sheet, limit=5)
    except Exception as e:
        recent_logs = []
        print(f"Error fetching logs: {e}")

    recent_log_text = "\n".join(
        [f"{log['date']}: {log['action']} ({log['confidence']}%) → {log['result']}" for log in recent_logs]
    ) if recent_logs else "None"

    system_msg = {
        "role": "system",
        "content": (
            "You are an expert SPY options trading assistant. Your job is to decide whether to trade "
            "a CALL, PUT, or SKIP based on the recent 1-minute candle data. "
            "Only recommend trades when confident in a strong directional move."
        )
    }

    user_msg = {
        "role": "user",
        "content": (
            f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
            f"Here are recent GPT decisions and their outcomes:\n{recent_log_text}\n\n"
            "Please reply ONLY in JSON format like this:\n"
            "{\"action\": \"call\" | \"put\" | \"skip\", \"confidence\": %, \"reason\": \"your logic\"}"
        )
    }

    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[system_msg, user_msg],
        temperature=0.2,
        max_tokens=300
    )

    reply = response.choices[0].message["content"].strip()
    print("🤖 GPT replied:\n", reply)

    try:
        decision_data = json.loads(reply)
    except Exception as e:
        print("❌ Failed to parse GPT reply:", e)
        return {"action": "skip", "confidence": 0, "reason": "Invalid GPT response format."}

    log_trade_decision(decision_data)
    send_trade_alert(decision_data["action"], decision_data["confidence"], decision_data["reason"])
    return decision_data
