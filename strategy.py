import numpy as np
import pandas as pd

def detect_market_regime(df):
    """
    Detects if the market is trending or choppy based on SPY 1-minute candles.

    Returns:
        str: 'TRENDING' or 'CHOPPY'
    """

    df = df.copy()
    df['returns'] = df['Close'].pct_change()
    rolling_vol = df['returns'].rolling(window=10).std()

    volatility_threshold = 0.002  # Can be tuned

    # Compute trend strength
    df['trend_strength'] = np.abs(df['Close'].diff().rolling(window=10).mean())

    trend_threshold = df['Close'].mean() * 0.0015  # Relative to price

    is_trending = (
        df['trend_strength'].iloc[-1] > trend_threshold
        and rolling_vol.iloc[-1] > volatility_threshold
    )

    return "TRENDING" if is_trending else "CHOPPY"
