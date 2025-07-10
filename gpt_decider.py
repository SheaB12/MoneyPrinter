import os
import json
import openai
import pandas as pd
from datetime import datetime
from logger import get_sheet, log_trade_decision, get_recent_logs
from alerts import send_discord_alert

openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df):
    sheet = get_sheet()
    required_columns = ["Open", "High", "Low", "Close", "Volume"]

    # Validate dataframe is not empty
    if df.empty:
        reason = "SPY data is empty. Market may be closed or API failed."
        print(f"⚠️ {reason}")
        send_discord_alert(f"⛔ Skipping due to data issue: {reason}", color=0xFF3333)
        decision = {"action": "skip", "confidence": 0, "reason": reason}
        log_trade_decision(sheet, decision, strategy_name="Data Validation")
        return decision

    # Validate required columns exist
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        reason = f"Missing required columns: {missing_cols}"
        print(f"⚠️ {reason}")
        send_discord_alert(f"⛔ Skipping due to data issue: {reason}", color=0xFF3333)
        decision = {"action": "skip", "confidence": 0, "reason": reason}
        log_trade_decision(sheet, decision, strategy_name="Data Validation")
        return decision

    # Prepare and clean data
    df = df.tail(30).copy()
    df = df.dropna(subset=required_columns)
    df[required_columns] = df[required_columns].apply(pd.to_numeric, errors="coerce")

    # Re-check for NaNs after type coercion
    if df[required_columns].isnull().values.any():
        reason = "SPY data has NaNs in required columns after coercion."
        print(f"⚠️ {reason}")
        send_discord_alert(f"⛔ Skipping due to data issue: {reason}", color=0xFF3333)
        decision = {"action": "skip", "confidence": 0, "reason": reason}
        log_trade_decision(sheet, decision, strategy_name="Data Validation")
        return decision

    # Format data for GPT
    candle_records = []
    for timestamp, row in df.iterrows():
        candle_records.append({
            "time": timestamp.strftime("%H:%M"),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": int(row["Volume"])
        })

    # Fetch recent results for GPT context
    try:
        recent_logs = get_recent_logs(sheet, tab="Results", limit=5)
        recent_summary = "\n".join([f"{x['date']}: {x['result']} ({x['strategy']})" for x in recent_logs])
    except Exception as e:
        recent_summary = "Recent performance data unavailable."
        print(f"Error fetching recent logs: {e}")

    # Prepare GPT prompt
    prompt = (
        "You're an expert SPY options trader. Based on the last 30 minutes of 1-minute candle data, "
        "decide whether to BUY a CALL, PUT, or SKIP trading today. Only choose one of the three. "
        "Respond in this exact JSON format: "
        '{ "action": "call" | "put" | "skip", "confidence": %, "reason": "" }\n\n'
        f"Recent trades summary:\n{recent_summary}\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}"
    )

    # Call OpenAI
    print("📡 Sending prompt to GPT...")
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a financial trading assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4
    )

    content = response["choices"][0]["message"]["content"]
    print(f"🤖 GPT replied:\n\n{content}\n")

    try:
        decision = json.loads(content)
        if decision["action"] not in ["call", "put", "skip"]:
            raise ValueError("Invalid action in GPT response.")
    except Exception as e:
        print(f"⚠️ Failed to parse GPT response: {e}")
        decision = {"action": "skip", "confidence": 0, "reason": "Invalid or malformed GPT response."}
        send_discord_alert(f"⚠️ GPT failed to reply correctly: {e}", color=0xFF0000)

    # Log and return decision
    log_trade_decision(sheet, decision, strategy_name="GPT Strategy")
    return decision
