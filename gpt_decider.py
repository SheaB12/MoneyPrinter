import json
from datetime import datetime
from openai import OpenAI
import pandas as pd
from strategy import detect_market_regime
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()
MODEL = "gpt-4"

def gpt_decision(df, recent_stats):
    df = df.copy()
    df["Datetime"] = pd.to_datetime(df["timestamp"])
    candle_data = df[["timestamp", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")

    system_prompt = (
        "You are a professional SPY options day trader. Based on the last 30 minutes of 1-minute candles, "
        "make a binary trade decision: CALL, PUT, or NONE. Respond in this JSON format:\n"
        "{ \"decision\": CALL|PUT|NONE, \"confidence\": float(0-1), \"reason\": string }"
    )

    regime = detect_market_regime(df)
    context_prompt = f"Market regime: {regime}.\n\nHere is the last 30 minutes of SPY data:\n{json.dumps(candle_data)}"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context_prompt}
        ]
    )

    try:
        reply = json.loads(response.choices[0].message.content)
    except Exception as e:
        reply = {
            "decision": "NONE",
            "confidence": 0.0,
            "reason": f"GPT response invalid: {e}"
        }

    reply["timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Dynamic threshold
    old_threshold = 0.60
    win_rate = recent_stats.get("win_rate", 0.60)
    atr = recent_stats.get("atr", 1.0)
    avg_conf = recent_stats.get("avg_confidence", 0.60)

    # Simple adaptive formula (tuneable)
    threshold = 0.55 + (win_rate - 0.5) * 0.5 + (avg_conf - 0.6) * 0.2
    threshold = max(0.50, min(threshold, 0.85))

    return reply, threshold, old_threshold
