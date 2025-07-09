import pandas as pd

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculates the Average True Range (ATR) for the given DataFrame.
    """
    df["H-L"] = df["High"] - df["Low"]
    df["H-PC"] = abs(df["High"] - df["Close"].shift(1))
    df["L-PC"] = abs(df["Low"] - df["Close"].shift(1))
    df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1)
    atr = df["TR"].rolling(window=period).mean().iloc[-1]
    return round(atr, 2)

def detect_market_regime(df: pd.DataFrame, short_window=9, long_window=21) -> str:
    """
    Determines if the market is trending or choppy based on EMA crossovers.
    """
    df["EMA_short"] = df["Close"].ewm(span=short_window, adjust=False).mean()
    df["EMA_long"] = df["Close"].ewm(span=long_window, adjust=False).mean()

    recent = df.tail(3)
    trending_up = all(recent["EMA_short"] > recent["EMA_long"])
    trending_down = all(recent["EMA_short"] < recent["EMA_long"])

    if trending_up:
        return "uptrend"
    elif trending_down:
        return "downtrend"
    else:
        return "choppy"
