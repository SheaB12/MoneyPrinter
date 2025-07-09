import os
import json
import pandas as pd
from openai import OpenAI
from logger import get_recent_logs
from strategy import determine_market_regime, calculate_atr
from alerts import send_threshold_change_alert

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Confidence threshold memory file
last_threshold_path = "last_confidence_threshold.txt"

def get_last_confidence_threshold():
    try:
        with open(last_threshold_path, "r") as f:
            return float(f.read())
    except:
        return 0.60  # Default

def save_confidence_threshold(threshold):
    with open(last_threshold_path, "w") as f:
        f.write(str(threshold))

def calculate_dynamic_threshold(logs_df, atr, conf_list):
    win_rate = (
        logs_df['Status'].str.lower().eq("win").sum() / len(logs_df)
        if len(logs_df) > 0 else 0.5
    )
    avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.6
    base = 0.6

    threshold = base + ((win_rate - 0.5) * 0.2) + ((atr - 1.5) * 0.02) + ((avg_conf - 0.6) * 0.1)
    return max(0.5, min(threshold, 0.85))

def gpt_decision(df: pd.DataFrame):
    df = df.copy()
    df.reset_index(inplace=True)

    # Ensure string-only column names
    df.columns = [str(col) for col in df.columns]

    # Rename index column to 'Datetime' if necessary
    if "index" in df.columns:
        df.rename(columns={"index": "Datetime"}, inplace=True)

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')

    # Use last 30 minutes of data
    recent_data = df.tail(30)
    candle_data = recent_data[["Datetime", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")

    market_regime = determine_market_regime(df)
    atr = calculate_atr(df)

    try:
        logs_df = get_recent_logs()
        conf_list = logs_df["Confidence"].astype(float).tolist() if not logs_df.empty else []
    except Exception as e:
        print("Error fetching recent logs:", e)
        logs_df = pd.DataFrame()
        conf_list = []

    dynamic_threshold = calculate_dynamic_threshold(logs_df, atr, conf_list)
    last_threshold = get_last_confidence_threshold()

    if abs(dynamic_threshold - last_threshold) >= 0.05:
        send_threshold_change_alert(dynamic_threshold, last_threshold)
        save_confidence_threshold(dynamic_threshold)

    prompt = (
        "You're a stock trading AI that analyzes SPY chart data. "
        f"The current market regime is: {market_regime}. "
        "Decide whether to BUY CALL, BUY PUT, or SKIP, and explain your reasoning clearly.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\n"
        "Your answer must be JSON formatted like this:\n"
        '{ "decision": "CALL", "confidence": 0.78, "reason": "Clear uptrend with strong volume" }'
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)

        if all(k in parsed for k in ["decision", "confidence", "reason"]):
            parsed["threshold"] = round(dynamic_threshold, 2)
            return parsed
        else:
            raise ValueError("Missing required keys in GPT response.")
    except Exception as e:
        return {
            "decision": "SKIP",
            "confidence": 0.0,
            "reason": f"Failed to parse GPT output. Error: {str(e)}",
            "threshold": dynamic_threshold
        }
