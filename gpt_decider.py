import openai
import os
import json
import pandas as pd
from alerts import send_trade_alert, send_profit_alert
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

    # 📊 Fetch logs
    try:
        sheet = get_sheet()
        logs = get_recent_logs(sheet=sheet)
    except Exception as e:
        print(f"Error fetching logs: {e}")
        logs = []

    # 🧠 GPT prompt setup
    system_prompt = (
        "You're a trading assistant analyzing SPY 1-minute candles. "
        "Decide to BUY CALL, BUY PUT, or SKIP. Respond in JSON: "
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
        confidence_raw = data.get("confidence", 0)
        confidence = int(confidence_raw[0]) if isinstance(confidence_raw, list) else int(confidence_raw)
        reason = data.get("reason", "No reason provided.")

        # 🧠 Strike recommendation logic
        strike_type = recommend_strike_type(df, action)

        # 🧮 Entry = last candle close, High = intraday high
        entry_price = df["Close"].iloc[-1]
        high_price = df["High"].max()
        profit_pct = ((high_price - entry_price) / entry_price * 100) if action == "call" else ((entry_price - df["Low"].min()) / entry_price * 100)
        profit_pct = round(profit_pct, 2)
        win = profit_pct >= 0  # Simplified win logic for alert

        # 🚨 Alert
        send_trade_alert(action, confidence, reason, strike_type)
        send_profit_alert(profit_pct, win)

        # 📓 Log
        log_trade_decision({
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "strike_type": strike_type,
            "profit_pct": profit_pct,
            "raw": reply
        })

        return {
            "action": action,
            "confidence": confidence,
            "reason": reason,
            "strike_type": strike_type,
            "profit_pct": profit_pct
        }

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        raise
