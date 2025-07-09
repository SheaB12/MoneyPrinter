import os
import json
import pandas as pd
from openai import OpenAI
from logger import get_recent_logs
from strategy import determine_market_regime, calculate_atr
from alerts import send_threshold_change_alert

# ✅ Initialize OpenAI client using environment variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Confidence tracking
last_threshold_path = "last_confidence_threshold.txt"

def get_last_confidence_threshold():
    try:
        with open(last_threshold_path, "r") as f:
            return float(f.read())
    except:
        return 0.60  # Default threshold

def save_confidence_threshold(threshold):
    with open(last_threshold_path, "w") as f:
        f.write(str(threshold))

def calculate_dynamic_threshold(recent_logs_df, atr, conf_list):
    win_rate = (
        recent_logs_df['Status'].str.lower().eq("win").sum()
        / len(recent_logs_df)
        if len(recent_logs_df) > 0 else 0.5
    )
    avg_conf = sum(conf_list) / len(conf_list) if conf_list else 0.6
    base = 0.6

    # Scale based on win rate and volatility
    threshold = base + ((win_rate - 0.5) * 0.2) + ((atr - 1.5) * 0.02) + ((avg_conf - 0.6) * 0.1)
    return max(0.5, min(threshold, 0.85))

def gpt_decision(df: pd.DataFrame):
    # ✅ Prepare DataFrame
    df = df.copy()
    df.reset_index(inplace=True)
    
    # Handle datetime
    if "index" in df.columns:
        df.rename(columns={"index": "Datetime"}, inplace=True)
    elif "Datetime" not in df.columns:
        df.insert(0, "Datetime", pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='T'))

    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')

    # Flatten all column names to strings
    df.columns = [str(c) for c in df.columns]

    # Ensure required columns
    required_cols = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing expected columns: {missing_cols}")

    recent_data = df.tail(30)
    candle_data = recent_data[required_cols].to_dict(orient="records")

    # ✅ Determine market regime and indicators
    market_regime = determine_market_regime(df)
    atr = calculate_atr(df)

    try:
        logs_df = get_recent_logs()
    except Exception as e:
        print("Error fetching recent logs:", e)
        logs_df = pd.DataFrame(columns=["Confidence", "Status"])

    recent_confs = logs_df['Confidence'].astype(float).tolist() if not logs_df.empty else []
    dynamic_threshold = calculate_dynamic_threshold(logs_df, atr, recent_confs)
    last_threshold = get_last_confidence_threshold()

    # ✅ Alert on significant threshold change
    if abs(dynamic_threshold - last_threshold) >= 0.05:
        send_threshold_change_alert(dynamic_threshold, last_threshold)
        save_confidence_threshold(dynamic_threshold)

    # ✅ Compose GPT prompt
    prompt = (
        "You're a stock trading AI that analyzes SPY chart data. "
        f"The current market regime is: {market_regime}. "
        "Decide whether to BUY CALL, BUY PUT, or SKIP, and explain your reasoning clearly.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\n"
        "Your answer must be JSON formatted like this:\n"
        '{ "decision": "CALL", "confidence": 0.78, "reason": "Clear uptrend with strong volume" }'
    )

    # ✅ Get GPT response
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)

        # Validate response fields
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
            "threshold": dynamic_threshold
        }
