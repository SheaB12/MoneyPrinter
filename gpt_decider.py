import openai
import os
import json
import pandas as pd
from alerts import send_trade_alert
from logger import get_sheet, get_recent_logs, log_trade_decision
from indicators import compute_indicators  # Custom file
from strike_logic import recommend_strike_type
from options_flow import fetch_tradier_flow_signal  # Optional module

openai.api_key = os.getenv("OPENAI_API_KEY")

def calculate_manual_score(df: pd.DataFrame) -> int:
    score = 0

    # Compute indicators
    df = compute_indicators(df)
    
    last = df.iloc[-1]

    if last['ema_9'] > last['ema_20']:
        score += 15
    if last['macd'] > last['macd_signal']:
        score += 10
    if last['rsi'] > 50:
        score += 10
    if last['vwap'] < last['Close']:
        score += 5
    if last['volume_surge']:
        score += 10

    return score

def gpt_decision(df: pd.DataFrame) -> dict:
    # 🧼 Flatten columns if needed
    if isinstance(df.columns[0], tuple):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df.columns = [col.strip().capitalize() for col in df.columns]

    required = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")

    df = df.dropna(subset=required)
    if df.empty:
        raise ValueError("SPY data is empty after cleaning.")
    df = df.astype({col: 'float' for col in required})

    # ⏳ Last 30m
    recent_df = df.tail(30)
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

    # 📊 Get logs for context
    try:
        sheet = get_sheet()
        logs = get_recent_logs(sheet=sheet)
    except Exception as e:
        print(f"⚠️ Error fetching logs: {e}")
        logs = []

    # 🧠 Prompt setup
    system_prompt = (
        "You are an options trading assistant. Analyze the SPY 1-minute candles "
        "and decide whether to BUY CALL, BUY PUT, or SKIP. Provide confidence (0–100) and a reason."
        "Use this format: {\"action\": \"call\", \"confidence\": 76, \"reason\": \"...\"}"
    )
    user_prompt = (
        f"Last 30m candles:\n{json.dumps(candles)}\n\n"
        f"Recent performance logs:\n{json.dumps(logs)}\n\nWhat’s the best decision?"
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

        gpt = json.loads(reply)
        action = gpt.get("action", "").lower()
        gpt_conf = int(gpt.get("confidence", 0))
        reason = gpt.get("reason", "No reason provided.")

        # 🧮 Manual score
        manual_score = calculate_manual_score(df)
        print(f"⚙️ Manual indicator score: {manual_score}")

        # 🧪 Options flow (if enabled)
        flow_score = fetch_tradier_flow_signal() if os.getenv("USE_FLOW") == "true" else 0

        # 🧷 Composite confidence
        composite_conf = int((gpt_conf + manual_score + flow_score) / 3)
        strike_type = recommend_strike_type(action, composite_conf)

        # ✅ Alert + Log
        send_trade_alert(action, composite_conf, reason, strike_type)
        log_trade_decision({
            "action": action,
            "confidence": composite_conf,
            "reason": reason,
            "strike_type": strike_type,
            "raw": reply
        })

        return {
            "action": action,
            "confidence": composite_conf,
            "reason": reason,
            "strike_type": strike_type
        }

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        raise
