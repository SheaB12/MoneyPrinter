# strike_logic.py

def recommend_strike_type(action: str, confidence: int, logs: list = None) -> str:
    """
    Recommends a strike type (ITM/ATM/OTM) based on confidence and optionally recent logs.
    """
    action = action.lower()

    if action not in ['call', 'put']:
        return "N/A"

    # ✅ Future-proof: Adjust based on logs (placeholder logic for now)
    # You can enhance this to analyze actual log performance by strike type

    # 📊 Simple rule-based logic
    if confidence >= 80:
        return "ITM"
    elif confidence >= 60:
        return "ATM"
    else:
        return "OTM"
