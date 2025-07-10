import os
import json
import openai
import pandas as pd
from logger import (
    get_sheet,
    log_trade_decision,
    get_recent_logs
)
from alerts import send_discord_alert

openai.api_key = os.getenv("OPENAI_API_KEY")


def gpt_decision(df: pd.DataFrame) -> dict:
    # Normalize column capitalization
    df.columns = [col.lower().capitalize() for col in df.columns]

    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    missing_cols = [col for col in required_columns if col not in df.columns]

    if df.empty or missing_cols:
        reason = f"Missing or invalid columns from data: {missing_cols or 'DataFrame is empty'}"
        print(f"⛔ {reason}")
        send_discord_alert(f"⛔ Skipping due to data issue: {reason}", color=0xFF3333)
        sheet = get_sheet()
        decision = {"action": "skip", "confidence": 0, "reason": reason}
        log_trade_decision(sheet, decision, strategy_name="Data Validation")
        return decision

    df = df.dropna(subset=required_columns)
    df = df.tail(30)

    # Convert data to safe format for GPT
    candle_records = []
    for i, row in df.iterrows():
        try:
            candle_records.append({
                "time": i.strftime("%H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"])
            })
        except Exception as e:
            print(f"⚠️ Skipping row due to error: {e}")
            continue

    # Fetch recent decisions for context (optional)
    try:
        sheet = get_sheet()
        recent_logs = get_recent_logs(sheet)
        context = "\n".join(recent_logs)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        context = "Recent log data unavailable."

    prompt = (
        f"You are an expert SPY options trading analyst. Based on the 1-minute candlestick data below, "
        f"decide whether to BUY CALL, BUY PUT, or SKIP. Only choose one action. Return JSON like:\n"
        f'{{"action": "call" or "put" or "skip", "confidence": 0-100, "reason": "your explanation"}}\n\n'
        f"{context}\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_records)}\n\n"
    )

    print("📡 Sending prompt to GPT...")
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional SPY options trader."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        reply = completion.choices[0].message.content
        print("🤖 GPT replied:\n")
        print(reply)
        decision = json.loads(reply)

        # Log decision and alert
        log_trade_decision(sheet, decision, strategy_name="GPT Strategy")
        send_discord_alert(
            f"📊 **GPT Decision:** {decision['action'].upper()} | 🎯 Confidence: {decision['confidence']}%\n🧠 {decision['reason']}",
            color=0x3366FF if decision["action"] != "skip" else 0xCCCCCC
        )

        return decision

    except Exception as e:
        print(f"Error during GPT decision: {e}")
        send_discord_alert(f"❌ GPT decision failed: {e}", color=0xFF0000)
        decision = {"action": "skip", "confidence": 0, "reason": "GPT error"}
        log_trade_decision(sheet, decision, strategy_name="GPT Error")
        return decision
