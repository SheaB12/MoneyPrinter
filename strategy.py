import pandas as pd

def detect_market_regime(df: pd.DataFrame) -> str:
    """
    Classifies the market regime as 'trending' or 'choppy' based on rolling returns.
    """
    df = df.copy()
    df["returns"] = df["Close"].pct_change()
    rolling_std = df["returns"].rolling(window=20).std()

    recent_volatility = rolling_std.iloc[-1]
    if recent_volatility > 0.005:
        return "trending"
    else:
        return "choppy"

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculates the Average True Range (ATR) for the given DataFrame.
    """
    df = df.copy()
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=period).mean()
    
    return round(df['ATR'].iloc[-1], 4)
