import openai
import pandas as pd
import json
import os
from datetime import datetime
from alerts import send_trade_alert, send_threshold_change_alert
from logger import log_trade_decision, get_recent_logs
from strategy import detect_market_regime, calculate_atr

openai.api_key = os.getenv("OPENAI_API_KEY")


def gpt_decision(df):
    try:
        recent_logs = get_recent_logs()  # ✅ No limit parameter
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    # Prepare recent SPY data for GPT
    recent_df = df.tail(30).copy()
    recent_df.reset_index(drop=True, inplace=True)  # ✅ Prevent tuple index keys
    candle_records = recent_df.to_dict(orient="records")  # ✅ JSON-safe

    prompt = (
        "You are a trading assistant. Your task is to analyze recent SPY 1-minute candles "
        "and determine whether to buy a CALL, PUT, or SKIP the trade. Only reply with a JSON object like this:\n\n"
        '{"action": "call", "confidence": 72, "reason": "brief explanation"}\n\n'
        "Your decision should be based on momentum, recent price movement, and possible trend continuation.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        f"Recent decisions: {recent_logs}"
    )

    print("📡 Sending prompt to GPT...")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a smart trading assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=300,
        )

        reply = response.choices[0].message['content']
        print("🤖 GPT replied:\n")
        print(reply)

        decision = json.loads(reply)

        # Validate structure
        action = decision.get("action", "").lower()
        confidence = int(decision.get("confidence", 0))
        reason = decision.get("reason", "")

        if action not in ["call", "put", "skip"]:
            raise ValueError(f"Invalid action: {action}")

        decision_data = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "confidence": confidence,
            "reason": reason,
        }

        # Log and alert
        log_trade_decision(decision_data)
        send_trade_alert(decision_data)

        return decision_data

    except Exception as e:
        print(f"❌ GPT decision error: {e}")
        return {"action": "skip", "confidence": 0, "reason": "GPT error fallback"}
