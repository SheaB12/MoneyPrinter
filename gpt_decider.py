import openai
import pandas as pd
import json
import os
from datetime import datetime
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs, log_trade_decision

openai.api_key = os.getenv("OPENAI_API_KEY")


def gpt_decision(df):
    sheet = get_sheet()

    try:
        recent_logs = get_recent_logs(sheet)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    # Format recent 30-min candles
    recent_df = df.tail(30).copy()
    recent_df = recent_df.reset_index()
    if "Datetime" in recent_df.columns:
        recent_df["Datetime"] = recent_df["Datetime"].astype(str)
    else:
        raise ValueError("Missing 'Datetime' column after reset_index().")

    candle_records = recent_df.to_dict(orient="records")

    prompt = (
        "You are a disciplined SPY options day trading assistant. "
        "Given the last 30 minutes of 1-minute SPY candles and recent decisions, respond in JSON ONLY:\n"
        "{\n"
        '  "action": "call" or "put" or "skip",\n'
        '  "confidence": 0–100,\n'
        '  "reason": "one-line rationale"\n'
        "}\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        f"Recent trade logs: {recent_logs}\n"
    )

    try:
        print("📡 Sending prompt to GPT...")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional trading assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        reply = response.choices[0].message.content.strip()
        print(f"🤖 GPT replied:\n\n{reply}\n")

        decision_data = json.loads(reply)
        decision_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Log and alert the decision
        log_trade_decision(sheet, decision_data)
        send_trade_alert(decision_data)

        return decision_data

    except Exception as e:
        print(f"Error during GPT decision or logging: {e}")
        return {
            "action": "skip",
            "confidence": 0,
            "reason": f"GPT error: {str(e)}"
        }
