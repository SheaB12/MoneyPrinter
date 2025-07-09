import os
import openai
import pandas as pd
import json

# Ensure the OpenAI API key is loaded
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise EnvironmentError("Missing OPENAI_API_KEY in environment variables.")

openai.api_key = OPENAI_API_KEY


def gpt_decision(df: pd.DataFrame) -> dict:
    """
    Make a trade decision using GPT based on the last 30 minutes of SPY 1-minute candle data.

    Args:
        df (pd.DataFrame): SPY 1-minute data with columns like Datetime, Open, High, Low, Close, Volume.

    Returns:
        dict: A dictionary with 'direction', 'confidence', and 'reason' keys.
    """
    # Use only the last 30 minutes
    df = df.tail(30)

    # Reset index to include datetime in each row
    df.reset_index(inplace=True)

    # Convert timestamps to string for JSON serialization
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')

    # Convert to list of records (dicts), which is JSON-safe
    candle_data = df.to_dict(orient="records")

    # Build the prompt
    prompt = (
        "You're a professional SPY options trader assistant. Given the last 30 minutes of 1-minute SPY price data "
        "(each with datetime, open, high, low, close, and volume), decide whether to BUY a CALL or PUT option. "
        "Also estimate a confidence level (0 to 1) and briefly explain your reasoning.\n\n"
        f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\n"
        "Respond in JSON format like this:\n"
        '{\n'
        '  "direction": "CALL" or "PUT",\n'
        '  "confidence": 0.xx,\n'
        '  "reason": "Your explanation here"\n'
        '}'
    )

    try:
        # Send the prompt to OpenAI ChatCompletion (GPT-4)
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()

        # Try parsing the JSON content
        decision = json.loads(content)

        # Validate response
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

        raise ValueError("Incomplete or invalid GPT decision format")

    except Exception as e:
        print(f"⚠️ GPT decision error: {e}")
        return {
            "direction": "none",
            "confidence": 0.0,
            "reason": str(e),
        }
