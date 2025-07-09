import os
import json
import openai
import pandas as pd
from dotenv import load_dotenv
from logger import get_recent_logs, log_trade_decision
from strategy import detect_market_regime, calculate_atr

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    if "Datetime" not in df.columns:
        df = df.reset_index()
    if "Datetime" not in df.columns:
        raise ValueError("Datetime column is missing after reset_index.")

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.sort_values("Datetime")

    # Add technical context
    market_regime = detect_market_regime(df)
    atr = calculate_atr(df)

    # Use the last 30 minutes of data
    recent_df = df.tail(30)
    candle_records = recent_df.to_dict(orient="records")  # ✅ JSON-safe format

    try:
        recent_logs = get_recent_logs(limit=50)  # Use logs to influence decisions
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    # GPT prompt construction
    prompt = (
        f"You are an options trading assistant. Based on recent SPY 1-minute candles, provide a trade decision.\n"
        f"Current market regime: {market_regime}\n"
        f"ATR (14): {atr:.2f}\n"
        f"Recent trade outcomes: {recent_logs}\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        "Respond in JSON with keys: action (call/put/skip), confidence (0–100), reason (short text)."
    )

    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial assistant that helps with options trade decisions."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300,
        temperature=0.4
    )

    reply = response.choices[0].message['content']
    print(f"🤖 GPT replied:\n\n{reply}\n")

    try:
        decision_data = json.loads(reply)
        decision_data["market_regime"] = market_regime
        decision_data["atr"] = atr
        decision_data["raw_prompt"] = prompt
        log_trade_decision(decision_data)
        return decision_data
    except Exception as e:
        print(f"❌ Error parsing GPT response: {e}")
        return {"action": "skip", "confidence": 0, "reason": "Error parsing GPT response"}
