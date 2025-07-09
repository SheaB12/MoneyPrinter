import os
import json
import pandas as pd
from openai import OpenAI
from config import OPENAI_API_KEY

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def gpt_decision(df: pd.DataFrame) -> dict:
    """
    Pass last 30 minutes of SPY data to GPT and return trade decision.
    Expected GPT response (JSON format):
    {
        "decision": "call" or "put" or "skip",
        "confidence": 0–100,
        "reason": "...",
        "stop_loss_pct": 30,
        "target_pct": 60
    }
    """

    # Format price action data for prompt
    candle_data = df.tail(30).to_dict(orient="records")

    # Construct system + user messages
    system_msg = {
        "role": "system",
        "content": (
            "You are an expert SPY options trader helping decide trades based on short-term momentum, "
            "technical indicators, and market structure. Always reply in JSON with keys: "
            "decision (call/put/skip), confidence, reason, stop_loss_pct, target_pct."
        )
    }

    user_msg = {
        "role": "user",
        "content": (
            f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\n"
            "Make a trade decision for the next 30 minutes."
        )
    }

    # Call GPT-4
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[system_msg, user_msg],
            temperature=0.4
        )

        gpt_raw = response.choices[0].message.content.strip()

        # Try parsing GPT response to JSON
        decision = json.loads(gpt_raw)
        return decision

    except Exception as e:
        print("⚠️ GPT error:", e)
        return {
            "decision": "skip",
            "confidence": 0,
            "reason": f"GPT error: {e}",
            "stop_loss_pct": 30,
            "target_pct": 60
        }
