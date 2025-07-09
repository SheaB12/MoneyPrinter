import os
import json
import openai
import pandas as pd
from statistics import mean
from logger import read_sheet_column
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def gpt_decision(df, threshold):
    df = df.copy()
    df["Datetime"] = df.index
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')

    candle_data = df[["Datetime", "Open", "High", "Low", "Close", "Volume"]].to_dict(orient="records")

    messages = [
        {"role": "system", "content": "You are a stock market analyst that decides whether to buy CALL or PUT options."},
        {"role": "user", "content": f"Here is the last 30 minutes of 1-min SPY data:\n\n{json.dumps(candle_data)}\n\nReturn your decision as JSON with keys: decision (CALL or PUT), confidence (0.0–1.0), and reason (1-2 sentence explanation)."}
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.3
    )

    content = response.choices[0].message["content"]

    try:
        parsed = json.loads(content)
    except:
        parsed = {"decision": "NONE", "confidence": 0.0, "reason": "Parsing failed"}

    parsed["timestamp"] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    return parsed

def calculate_dynamic_threshold(sheet_name):
    conf_col = read_sheet_column(sheet_name, "GPT Decisions", "Confidence (%)")
    result_col = read_sheet_column(sheet_name, "GPT Decisions", "Status")

    if not conf_col or not result_col:
        return 0.6, ""

    try:
        recent_conf = conf_col[-30:]
        avg_conf = mean([float(x) for x in recent_conf if x])
    except:
        avg_conf = 0.6

    recent_results = result_col[-30:]
    wins = sum(1 for r in recent_results if r == "EXECUTED")
    win_rate = wins / len(recent_results) if recent_results else 0.5

    atr = abs(avg_conf - 0.6)
    new_threshold = 0.6 + (0.1 * (0.5 - win_rate)) + atr

    new_threshold = max(0.5, min(0.8, round(new_threshold, 2)))

    notes = ""
    if abs(new_threshold - 0.6) > 0.05:
        notes = f"📊 New adaptive confidence threshold: **{new_threshold * 100:.1f}%**\nWin rate: {win_rate:.2%}, Avg confidence: {avg_conf:.2f}"

    return new_threshold, notes
