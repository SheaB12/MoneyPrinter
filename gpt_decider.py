import openai
import os
import json
import pandas as pd
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def gpt_decision(data: pd.DataFrame) -> dict:
    # Convert timestamp to string for serialization
    data["timestamp"] = data["Datetime"].dt.strftime("%Y-%m-%d %H:%M")
    candle_data = data[["timestamp", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")

    prompt = (
        "You are an expert SPY options day trader. Analyze the market data and decide whether to buy a CALL or PUT "
        "option based on the short-term trend.\n\n"
        "Instructions:\n"
        "- Use ONLY the following 1-minute candle data from the last 30 minutes.\n"
        "- Determine if there's a clear uptrend or downtrend.\n"
        "- If an uptrend, choose CALL. If a downtrend, choose PUT. If uncertain, say NO TRADE.\n"
        "- Provide your decision, a confidence score from 0 to 1, and a reason.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\n"
        "Respond with a JSON object in the following format:\n"
        "{ \"decision\": \"CALL\", \"confidence\": 0.85, \"reason\": \"brief reason here\" }"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        content = response["choices"][0]["message"]["content"]
        result = json.loads(content)

        decision = result.get("decision", "NO TRADE").upper()
        confidence = float(result.get("confidence", 0.0))
        reason = result.get("reason", "")

        return {
            "decision": decision,
            "confidence": confidence,
            "reason": reason
        }

    except Exception as e:
        return {
            "decision": "NO TRADE",
            "confidence": 0.0,
            "reason": f"Error communicating with GPT: {str(e)}"
        }
