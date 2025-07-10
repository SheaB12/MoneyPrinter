import os
import json
import openai
from datetime import datetime
from logger import get_sheet, get_recent_logs, log_trade_decision

# Set OpenAI API key from environment
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df, strategy_name="Default Strategy"):
    try:
        sheet = get_sheet()

        # 🧠 Retrieve last 5 decisions from the sheet
        recent_logs = get_recent_logs(sheet, limit=5)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    # ✅ Convert the last 30 minutes of 1-minute bars into a JSON-safe format
    candles = []
    for idx, row in df.tail(30).reset_index().iterrows():
        candles.append({
            "timestamp": str(row["Datetime"]),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"])
        })

    # 🧠 GPT Prompt
    prompt = (
        "You are a disciplined SPY options day trader.\n"
        "Use the following data to decide if we should BUY a CALL, BUY a PUT, or SKIP the trade.\n"
        "Return only a valid JSON response like this:\n"
        '{"action": "call", "confidence": 78, "reason": "Brief explanation"}\n\n'
        f"Here is the last 30 minutes of SPY 1-minute candles:\n{json.dumps(candles, indent=2)}\n\n"
        f"Here are the past 5 trades:\n{json.dumps(recent_logs, indent=2)}\n"
    )

    print("📡 Sending prompt to GPT...")

    # 🔮 Get GPT response
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        content = response.choices[0].message["content"]
        print("🤖 GPT replied:\n")
        print(content)

        # ✅ Parse GPT's JSON reply
        decision_data = json.loads(content)

        # Log it to the sheet
        log_trade_decision(sheet, decision_data, strategy_name)

        return decision_data

    except Exception as e:
        print(f"Error parsing GPT response: {e}")
        return {"action": "skip", "confidence": 0, "reason": "GPT response error"}
