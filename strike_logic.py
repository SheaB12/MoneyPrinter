# strike_logic.py

def recommend_strike_type(action: str, confidence: int) -> str:
    """
    Recommends a strike type based on action and confidence level.
    Returns: "ATM", "ITM", or "OTM"
    """
    action = action.lower()

    if action not in ['call', 'put']:
        return "N/A"

    # 🔧 Custom rules based on confidence
    if confidence >= 80:
        return "ITM"  # safer bet
    elif 60 <= confidence < 80:
        return "ATM"  # balanced risk
    else:
        return "OTM"  # high-risk, high-reward
