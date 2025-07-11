import numpy as np

def calculate_confidence(indicators: dict, options_flow_strength: float, gpt_confidence: int) -> int:
    """
    Combine indicator signals, Tradier flow strength, and GPT score to compute a unified confidence score (0–100).
    """

    score = 0
    weight_total = 0

    # 📈 EMA Trend
    if indicators.get("ema9") > indicators.get("ema20"):
        score += 15
    weight_total += 15

    # 💥 Volume Spike
    if indicators.get("volume_spike"):
        score += 15
    weight_total += 15

    # 📊 RSI Strength
    rsi = indicators.get("rsi", 50)
    if rsi > 65:
        score += 10
    elif rsi < 35:
        score += 10
    weight_total += 10

    # 📉 MACD
    if indicators.get("macd") > 0:
        score += 10
    weight_total += 10

    # 🧭 VWAP Alignment
    if indicators.get("price") > indicators.get("vwap"):
        score += 10
    weight_total += 10

    # 📊 Tradier Options Flow Strength (0–100)
    flow_strength = min(max(options_flow_strength, 0), 100)
    score += flow_strength * 0.25
    weight_total += 25

    # 🧠 GPT Confidence (already 0–100)
    score += gpt_confidence * 0.25
    weight_total += 25

    final_score = round(score / weight_total * 100)
    return min(final_score, 100)
