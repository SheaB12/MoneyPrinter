import pandas as pd
import os
from datetime import datetime, timedelta
from logger import get_sheet
from alerts import send_threshold_change_alert

# Sheet and tab configuration
SHEET_NAME = "Results"
BASELINE_THRESHOLD = 65

# --- Threshold Modes ---
# Option 1: Static (baseline)
# Option 2: Adaptive (based on recent win rate, confidence, ATR)
# Option 3: ML classifier (future-ready plug-in)
THRESHOLD_MODE = os.getenv("THRESHOLD_MODE", "baseline")

# Strategy Modes
# 'conservative', 'baseline', 'aggressive' — switchable based on recent volatility or win rate
def classify_strategy(avg_atr, win_rate):
    if win_rate >= 80 or avg_atr >= 2.5:
        return "aggressive"
    elif win_rate < 50 or avg_atr < 1.2:
        return "conservative"
    return "baseline"

def get_recent_metrics(days=5):
    sheet = get_sheet()
    try:
        worksheet = sheet.worksheet(SHEET_NAME)
        data = worksheet.get_all_records()

        df = pd.DataFrame(data)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=["Date"])
        df = df.sort_values("Date", ascending=False).head(days)

        df['Win'] = df['Win'].astype(str).str.lower().isin(['true', '1', 'yes'])
        df['Confidence'] = pd.to_numeric(df['Confidence'], errors='coerce')
        df['ATR'] = pd.to_numeric(df['ATR'], errors='coerce')

        win_rate = df['Win'].mean() * 100 if not df.empty else 0
        avg_conf = df['Confidence'].mean() if not df.empty else BASELINE_THRESHOLD
        avg_atr = df['ATR'].mean() if not df.empty else 1.0

        return round(win_rate, 2), round(avg_conf, 2), round(avg_atr, 2)
    except Exception as e:
        print(f"❌ Error reading recent metrics: {e}")
        return 0, BASELINE_THRESHOLD, 1.0

def determine_threshold(prev_threshold=None):
    win_rate, avg_conf, avg_atr = get_recent_metrics()
    strategy = classify_strategy(avg_atr, win_rate)

    # Threshold logic by mode
    if THRESHOLD_MODE == "baseline":
        threshold = BASELINE_THRESHOLD
    elif THRESHOLD_MODE == "adaptive":
        threshold = int(avg_conf)
        # Clamp it within bounds
        threshold = max(60, min(80, threshold))
    else:
        # Option 3 (ML based) - placeholder
        threshold = BASELINE_THRESHOLD

    if prev_threshold is not None and abs(threshold - prev_threshold) >= 5:
        send_threshold_change_alert(prev_threshold, threshold)

    print(f"📊 Mode: `{THRESHOLD_MODE}` | Strategy: `{strategy}` | Win Rate: {win_rate}% | Conf: {avg_conf}% | ATR: {avg_atr}")
    return threshold, strategy

# Optional CLI usage
if __name__ == "__main__":
    prev = BASELINE_THRESHOLD
    new_threshold, selected_strategy = determine_threshold(prev)
    print(f"✅ New Threshold: {new_threshold}% | Strategy: {selected_strategy}")
