import os
import json
import openai
import pandas as pd
from logger import get_sheet, get_recent_logs, log_trade_decision
from alerts import send_threshold_change_alert
from strategy import detect_market_regime, calculate_atr

openai.api_key = os.getenv("OPENAI_API_KEY")

# Confidence threshold (dynamically modifiable)
CONFIDENCE_THRESHOLD = 60

def gpt_decision(df):
    df = df.copy()
    df.reset_index(inplace=True)
    
    if "Datetime" not in df.columns:
        raise ValueError("Datetime column is missing after reset_index.")

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df = df.tail(30)

    # Convert index to str for JSON serialization
    df.set_index("Datetime", inplace=True)
    df.index = df.index.strftime("%Y-%m-%d %H:%M")
    candle_records = df.to_dict(orient="index")

    # Try to fetch logs
    try:
        sheet = get_sheet()
        logs = get_recent_logs(sheet, tab_name="Results", num_rows=30)
    except Exception as e:
        print("Error fetching recent logs:", e)
        logs = []

    # Determine market regime and ATR
    regime = detect_market_regime(df)
    atr = calculate_atr(df)

    prompt = (
        "You are a SPY options trading bot using price action and volume data.\n"
        f"Market regime: {regime}\n"
        f"Current ATR: {atr:.2f}\n"
    )

    if logs:
        prompt += f"\nHere are recent decisions and their outcomes:\n{logs}\n"

    prompt += (
        f"\nHere is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        "Decide whether to trade a CALL, PUT, or SKIP. "
        "Respond ONLY with a JSON object using this format:\n"
        '{"action": "call|put|skip", "confidence": 0-100, "reason": "..."}\n'
    )

    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )

    content = response['choices'][0]['message']['content']
    print("🤖 GPT replied:\n")
    print(content)

    try:
        decision_data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("GPT response could not be parsed as JSON.")

    # Add logging metadata
    decision_data["regime"] = regime
    decision_data["atr"] = atr
    decision_data["datetime"] = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M")

    # Log to Google Sheets
    try:
        log_trade_decision(decision_data)
    except Exception as e:
        print("Decision Logging Error:", e)

    # Dynamic threshold alert (optional advanced feature)
    global CONFIDENCE_THRESHOLD
    if decision_data["confidence"] < CONFIDENCE_THRESHOLD:
        print("⚠️ Confidence below threshold. Skipping.")
    else:
        print(f"✅ Decision meets confidence threshold ({CONFIDENCE_THRESHOLD}+)")

    return decision_data
