import openai
import os
import json
import pandas as pd
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs, log_trade_decision

# Set OpenAI API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df: pd.DataFrame) -> dict:
    # 🔧 Normalize and flatten column names
    df.columns = [col[1] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = [col.lower().capitalize() for col in df.columns]

    required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise KeyError(f"{missing_cols}")

    df = df.dropna(subset=required_columns)
    if df.empty:
        raise ValueError("Filtered DataFrame is empty after dropping NaNs.")

    df = df.astype({col: 'float' for col in required_columns})

    # 🕒 Extract last 30 minutes
    recent_df = df.tail(30)

    # 🧱 Format candles
    candle_records = [
        {
            "time": idx.strftime("%H:%M"),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"]),
        }
        for idx, row in recent_df.iterrows()
    ]

    # 🧠 Prepare prompt
    try:
        sheet = get_sheet()
        logs = get_recent_logs(sheet=sheet)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        logs = []

    system_prompt = (
        "You're a stock trading assistant analyzing SPY 1-minute candlestick data. "
        "You must choose whether to BUY CALL, BUY PUT, or SKIP. "
        "Only respond with JSON like {\"action\": \"call\", \"confidence\": 72, \"reason\": \"...\"}. "
        "Use the recent trade log and data for context."
    )

    user_prompt = (
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        f"Here is the recent trade log:\n\n{json.dumps(logs)}\n\n"
        "What action should we take?"
    )

    # 📡 Send to GPT
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=500,
        )
        reply = response.choices[0].message.content.strip()
        print(f"🤖 GPT replied:\n\n{reply}\n")

        decision_data = json.loads(reply)
        action = decision_data.get("action", "").lower()
        confidence = int(decision_data.get("confidence", 0))
        reason = decision_data.get("reason", "No reason provided.")

        # ✅ Send alert and log
        send_trade_alert(action, confidence, reason)
        log_trade_decision({
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "raw": reply
        })

        return decision_data

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        raise
