import os
import openai
import pandas as pd
import json

# Load OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("Missing OPENAI_API_KEY in environment variables.")

openai.api_key = OPENAI_API_KEY


def gpt_decision(df: pd.DataFrame) -> dict:
    """
    Send last 30 minutes of SPY 1-min candles to GPT for trade decision.
    Returns a dict with direction, confidence, and reason.
    """
    # Take last 30 minutes
    df = df.tail(30).copy()

    # Reset index to remove tuple/datetime indexing and treat timestamp as column
    df = df.reset_index()

    # Rename timestamp column for clarity and JSON safety
    if "Datetime" not in df.columns:
        df.rename(columns={"index": "Datetime"}, inplace=True)

    # Ensure timestamp is a string
    df["Datetime"] = df["Datetime"].astype(str)

    # Convert to list of dicts for safe JSON serialization
    candle_data = df.to_dict(orient="records")

    # Prompt to GPT
    prompt = (
        "You're a professional SPY options trading assistant. Based on the following 30 minutes of 1-minute SPY data "
        "(datetime, open, high, low, close, volume), determine if the next 30 minutes favor a CALL or PUT. "
        "Give a confidence score (0 to 1) and a 1-sentence explanation.\n\n"
        f"{json.dumps(candle_data)}\n\n"
        "Respond in this exact JSON format:\n"
        '{\n'
        '  "direction": "CALL" or "PUT",\n'
        '  "confidence": 0.xx,\n'
        '  "reason": "brief reasoning"\n'
        '}'
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()

        # Try parsing GPT response
        decision = json.loads(content)

        # Validate and return
        if (
            "direction" in decision
            and decision["direction"] in ("CALL", "PUT")
            and "confidence" in decision
            and isinstance(decision["confidence"], (float, int))
        ):
            return {
                "direction": decision["direction"],
                "confidence": float(decision["confidence"]),
                "reason": decision.get("reason", ""),
            }

        raise ValueError("GPT response missing required keys.")

    except Exception as e:
        print(f"⚠️ GPT decision error: {e}")
        return {
            "direction": "none",
            "confidence": 0.0,
            "reason": str(e),
        }
