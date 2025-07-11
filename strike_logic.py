def recommend_strike_type(df, action):
    """
    Recommends strike type based on price distance from recent range.
    Uses heuristics and historical bias.
    """
    try:
        close = df["Close"].iloc[-1]
        low = df["Low"].min()
        high = df["High"].max()
        range_pct = (high - low) / close * 100

        # Example logic: lower volatility = ITM, higher volatility = OTM
        if range_pct < 0.6:
            return "ITM"
        elif range_pct < 1.2:
            return "ATM"
        else:
            return "OTM"
    except Exception as e:
        print(f"Error in strike recommendation: {e}")
        return "ATM"
