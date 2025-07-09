import os
import yfinance as yf
import pandas as pd
from gpt_decider import gpt_decision
from logger import log_gpt_decision, get_past_gpt_logs
from alerts import send_discord_alert, format_discord_message

def fetch_spy_data():
    df = yf.download("SPY", interval="1m", period="1d", progress=False)
    df.reset_index(inplace=True)
    df["Datetime"] = df["Datetime"].dt.strftime('%Y-%m-%d %H:%M')
    return df

def calculate_atr(df, period=14):
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['Low'] - df['Close'].shift(1))
    tr = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    return tr.rolling(window=period).mean().iloc[-1]

def compute_dynamic_threshold():
    logs_df = get_past_gpt_logs()
    if logs_df.empty:
        return 0.6  # default threshold

    recent = logs_df.tail(20)
    win_rate = sum(recent['Result'].str.upper() == 'WIN') / len(recent)

    avg_conf = recent['Confidence'].astype(float).mean()
    market_volatility = recent['ATR'].astype(float).mean() if 'ATR' in recent else 1.5

    dynamic = 0.55 + (win_rate * 0.2) + ((market_volatility - 1) * 0.05)
    return round(min(max(dynamic, 0.5), 0.75), 2)

def run():
    print("\n📈 Fetching SPY...")
    data = fetch_spy_data()
    atr = calculate_atr(data)

    print("\n🧠 GPT making decision...")
    decision = gpt_decision(data)

    status = "SKIPPED"
    decision["ATR"] = round(atr, 2)

    threshold = compute_dynamic_threshold()
    print(f"\n⚙️ Dynamic Confidence Threshold: {threshold * 100:.1f}%")

    if decision["confidence"] >= threshold:
        status = "EXECUTED"

    log_gpt_decision(decision, status)
    send_discord_alert(format_discord_message(decision, status))

if __name__ == "__main__":
    run()
