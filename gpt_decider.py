import os
import json
import openai
import pandas as pd
from logger import get_sheet, get_recent_logs, log_trade_decision

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")


def gpt_decision(df, strategy_name="Default Strategy"):
    try:
        sheet = get_sheet()
        recent_logs = get_recent_logs(sheet)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        recent_logs = []

    # ✅ Handle empty DataFrame or missing columns
    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    if df.empty or not all(col in df.columns for col in required_columns):
        print("⚠️ DataFrame is empty or missing expected columns. Skipping decision.")
        return {
            "action": "skip",
            "confidence": 0,
            "reason": "SPY data unavailable or invalid."
        }

    df = df.tail(30).copy()
    df = df.dropna(subset=required_columns)
    df["Open"] = pd.to_numeric(df["Open"], errors="coerce")
    df["High"] = pd.to_numeric(df["High"], errors="coerce")
    df["Low"] = pd.to_numeric(df["Low"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
    df = df.dropna()

    candles = []
    for _, row in df.reset_index().iterrows():
        candles.append({
            "timestamp": str(row["Datetime"]),
            "open": round(row["Open"], 2),
            "high": round(row["High"], 2),
            "low": round(row["Low"], 2),
            "close": round(row["Close"], 2),
            "volume": int(row["Volume"])
        })

    # 🧠 Prompt
    prompt = (
        "You are an elite SPY options day trader.\n"
        "Make a decision: 'call', 'put', or 'skip'. Return JSON like:\n"
        '{"action": "call", "confidence": 80, "reason": "trend up"}\n\n'
        f"Last 30m SPY candles:\n{json.dumps(candles, indent=2)}\n\n"
        f"Recent trades:\n{json.dumps(recent_logs, indent=2)}"
    )

    print("📡 Sending prompt to GPT...")

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

        decision_data = json.loads(content)
        log_trade_decision(sheet, decision_data, strategy_name)
        return decision_data

    except Exception as e:
        print(f"❌ GPT response error: {e}")
        return {
            "action": "skip",
            "confidence": 0,
            "reason": f"GPT failure: {e}"
        }
