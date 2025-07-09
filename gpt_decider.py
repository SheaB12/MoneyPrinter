import os
import json
import pandas as pd
from openai import OpenAI
from logger import get_recent_logs
from strategy import detect_market_regime, calculate_atr
from alerts import send_threshold_change_alert

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Path for saving the last confidence threshold
last_threshold_path = "last_confidence_threshold.txt"

def get_last_confidence_threshold():
    try:
        with open(last_threshold_path, "r") as f:
            return float(f.read())
    except:
        return 0.60  # Default fallback

def save_confidence_threshold(threshold):
    with open(last_threshold_path, "w") as f:
        f.write(str(threshold))

def calculate_dynamic_threshold(recent_logs_df, atr, conf_list):
    win_rate = (
        recent_logs_df['Status'].str.lower().eq("win").sum() / len(recent_logs_df)
        if len(recent_logs_df) > 0 else 0.5
    )
    avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.6
    base = 0.6
    threshold = base + ((win_rate - 0.5) * 0.2) + ((atr - 1.5) * 0.02) + ((avg_conf - 0.6) * 0.1)
    return max(0.5, min(threshold, 0.85))

def gpt_decision(df: pd.DataFrame):
    df = df.reset_index()

    # Handle datetime column safely
    datetime_col = df.columns[0]
    if datetime_col not in df.columns:
        raise ValueError("Datetime column is missing after reset_index.")

    df = df.rename(columns={datetime_col: "Datetime"})
    df["Datetime"] = pd.to_datetime(df["Datetime"])

    # Prepare data for GPT prompt
    recent_data = df.tail(30)
    candle_data = recent_data[["Datetime", "Open", "High", "Low", "Close", "Volume"]].copy()
    candle_data["Datetime"] = candle_data["Datetime"].astype(str)
    candle_records = candle_data.to_dict(orient="records")

    market_regime = detect_market_regime(df)
    atr = calculate_atr(df)

    logs_df = get_recent_logs()  # No limit arg needed now
    recent_confs = logs_df['Confidence'].astype(float).tolist() if not logs_df.empty else []
    dynamic_threshold = calculate_dynamic_threshold(logs_df, atr, recent_confs)
    last_threshold = get_last_confidence_threshold()

    # Send alert if threshold changes significantly
    if abs(dynamic_threshold - last_threshold) >= 0.05:
        send_threshold_change_alert(dynamic_threshold, last_threshold)
        save_confidence_threshold(dynamic_threshold)

    prompt = (
        "You're a stock trading AI that analyzes SPY chart data. "
        f"The current market regime is: {market_regime}. "
        "Decide whether to BUY CALL, BUY PUT, or SKIP, and explain your reasoning clearly.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
        "Your answer must be JSON formatted like this:\n"
        '{ "decision": "CALL", "confidence": 0.78, "reason": "Clear uptrend with strong volume" }'
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)

        if all(k in parsed for k in ["decision", "confidence", "reason"]):
            parsed["threshold"] = round(dynamic_threshold, 2)
            return parsed
        else:
            raise ValueError("Missing keys in GPT response.")

    except Exception as e:
        return {
            "decision": "SKIP",
            "confidence": 0.0,
            "reason": f"Failed to parse GPT output. Error: {str(e)}",
            "threshold": round(dynamic_threshold, 2)
        }
