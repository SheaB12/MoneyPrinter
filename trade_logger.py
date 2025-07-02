import csv
from datetime import datetime
import os

LOG_FILE = "trade_log.csv"

def log_header():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Direction", "Option", "Entry Price", "Exit Price",
                "PnL", "Source", "Time Held", "Stop Hit", "Profit Target Hit",
                "Confidence", "Reason", "Stop %", "Target %"
            ])

def log_trade(data):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(data)
