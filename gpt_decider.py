import os
import json
import openai
import pandas as pd
from datetime import datetime
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def gpt_decision(df):
    df = df.tail(30).copy()
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')

    candle_data = df[["Datetime", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")

    prompt = (
        "You are a financial analyst.\n"
        "Given the last 30 minutes of SPY 1-minute candles, decide whether to BUY CALL, BUY PUT, or DO NOTHING.\n"
        "Respond with a JSON dict containing keys: 'decision' (CALL, PUT, NONE), 'confidence' (0 to 1), 'reason'.\n"
        f"Here is the data:\n{json.dumps(candle_data)}"
    )

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        content = response.choices[0].message["content"]
        parsed = json.loads(content)
        return {
            "decision": parsed.get("decision", "NONE").upper(),
            "confidence": float(parsed.get("confidence", 0)),
            "reason": parsed.get("reason", "No reason provided."),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "decision": "NONE",
            "confidence": 0.0,
            "reason": f"Error: {str(e)}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
