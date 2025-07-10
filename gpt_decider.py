import os
import json
import pandas as pd
from openai import OpenAI, OpenAIError
from alerts import send_trade_alert, send_discord_alert
from logger import get_sheet, log_trade_decision, get_recent_logs

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def gpt_decision(df: pd.DataFrame) -> dict:
    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_columns if col not in df.columns]

    if missing_cols:
        raise KeyError(f"Missing required columns: {missing_cols}")

    df = df.dropna(subset=required_columns)
    if df.empty:
        raise ValueError("Filtered DataFrame is empty after dropping NaNs.")

    df = df.astype({col: 'float' for col in required_columns})

    last_30 = df.tail(30)
    candle_records = []
    for i, row in last_30.iterrows():
        candle_records.append({
            "timestamp": i.strftime("%Y-%m-%d %H:%M"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"])
        })

    try:
        recent_logs = get_recent_logs(get_sheet(), 5)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    prompt = (
        "You are an expert SPY options trader.\n"
        "Based on the last 30 minutes of 1-minute candlestick data, decide whether to:\n"
        "`call`, `put`, or `skip`.\n"
        "Include your confidence (0-100) and a brief reason.\n"
        f"\nRecent trades:\n{recent_logs}\n\n"
        f"\nHere is the last 30 minutes of SPY data:\n\n{json.dumps(candle_records)}\n\n"
        "Respond only in JSON format like this:\n"
        '{"action": "call", "confidence": 75, "reason": "Momentum rising with bullish candles and high volume"}'
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip()
        print(f"🤖 GPT replied:\n\n{reply}\n")

        decision = json.loads(reply)
        action = decision.get("action", "skip").lower()
        confidence = int(decision.get("confidence", 0))
        reason = decision.get("reason", "No reason provided.")

        decision_data = {
            "action": action,
            "confidence": confidence,
            "reason": reason
        }

        send_trade_alert(action, confidence, reason)
        log_trade_decision(decision_data)
        return decision_data

    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"❌ GPT decision error: {e}")
        send_discord_alert(f"GPT decision error: {e}", color=0xe74c3c, title="⚠️ GPT Error")
        return {
            "action": "skip",
            "confidence": 0,
            "reason": f"Error: {e}"
        }
