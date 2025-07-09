import pandas as pd

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    df = df.copy()
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    atr = df['TR'].rolling(window=period).mean().iloc[-1]
    return round(atr, 2) if pd.notna(atr) else 1.5  # Fallback if NaN

def determine_market_regime(df: pd.DataFrame) -> str:
    df = df.copy()
    df['Returns'] = df['Close'].pct_change()
    std_dev = df['Returns'].rolling(window=20).std().iloc[-1]

    if std_dev is None or pd.isna(std_dev):
        return "unknown"

    if std_dev > 0.015:
        return "trending"
    elif std_dev < 0.005:
        return "choppy"
    else:
        return "neutral"
