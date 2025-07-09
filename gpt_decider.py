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
    # Take last 30 rows
    df = df.tail(30).copy()

    # Fully reset index to flatten structure and avoid tuple keys
    df.reset_index(inplace=True)

    # Rename index to Datetime if needed
    if "Datetime" not in df.columns:
        if "index" in df.columns:
            df.rename(columns={"index": "Datetime"}, inplace=True)

    # Convert datetime to string format
    df["Datetime"] = pd.to_datetime(df["Datetime"]).dt.strftime('%Y-%m-%d %H:%M')

    # Drop any columns with tuple keys just in case
    df.columns = [str(col) if not isinstance(col, tuple) else "_".join(map(str, col)) for col in df.columns]

    # Convert to JSON-safe dict format
    candle_data = df.to_dict(orient="records")

    # GPT prompt
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
        decision = json.loads(content)

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
