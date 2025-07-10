import openai
import os
import json
import pandas as pd
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs, log_trade_decision
from strike_logic import recommend_strike_type

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df: pd.DataFrame) -> dict:
    # 🧼 Flatten MultiIndex columns if needed
    if isinstance(df.columns[0], tuple):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]

    # 🧾 Normalize column names
    df.columns = [col.strip().capitalize() for col in df.columns]

    # ✅ Ensure required columns exist
    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    # 🧹 Clean + Convert
    df = df.dropna(subset=required)
    if df.empty:
        raise ValueError("SPY data is empty after cleaning.")
    df = df.astype({col: 'float' for col in required})

    # ⏳ Last 30 minutes
    recent_df = df.tail(30)

    # 🧱 Format candles
    candles = [
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

    # 🧠 GPT prompt setup
    try:
        sheet = get_sheet()
        logs = get_recent_logs(sheet=sheet)
    except Exception as e:
        print(f"Error fetching logs: {e}")
        logs = []

    system_prompt = (
        "You're a trading assistant analyzing SPY 1-minute candles. "
        "Decide to BUY CALL, BUY PUT, or SKIP. Respond with JSON: "
        "{\"action\": \"call\", \"confidence\": 76, \"reason\": \"...\"}"
    )
    user_prompt = (
        f"Last 30m candles:\n{json.dumps(candles)}\n\n"
        f"Recent logs:\n{json.dumps(logs)}\n\nWhat’s the decision?"
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=500
        )
        reply = response.choices[0].message.content.strip()
        print(f"🤖 GPT Reply:\n{reply}")

        data = json.loads(reply)
        action = data.get("action", "").lower()
        confidence = int(data.get("confidence", 0))
        reason = data.get("reason", "No reason provided.")

        if action not in ['call', 'put']:
            print("No trade taken.")
            return {"action": "none", "confidence": 0, "reason": "Skipped"}

        # ⏰ Expiration + Strike
        expiration = "End of Day"
        strike = recommend_strike_type(action, confidence, df)

        # 📢 Send Discord alert
        send_trade_alert(action, confidence, reason, expiration, strike)

        # 🧾 Log to Google Sheets
        log_trade_decision({
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "expiration": expiration,
            "strike": strike,
            "raw": reply
        })

        return {
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "expiration": expiration,
            "strike": strike
        }

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        raise
