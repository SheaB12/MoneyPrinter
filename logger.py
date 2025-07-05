import base64
import os
import json
import gspread
from datetime import datetime
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

SHEET_NAME = "Money Printer Logs"
TAB_NAME = datetime.now().strftime("%Y-%m-%d")  # One tab per day (optional: change to monthly)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_gsheets_client():
    key_b64 = os.getenv("GOOGLE_SHEETS_KEY_B64")
    if not key_b64:
        raise Exception("Missing GOOGLE_SHEETS_KEY_B64 in environment variables")
    
    key_json = base64.b64decode(key_b64).decode("utf-8")
    creds_dict = json.loads(key_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)

def log_trade_to_sheets(trade_data: dict):
    client = get_gsheets_client()
    try:
        sheet = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(SHEET_NAME)
        sheet.share(creds_dict["client_email"], perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(TAB_NAME)
    except WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=TAB_NAME, rows="1000", cols="20")
        worksheet.append_row([
            "timestamp", "trade_id", "direction", "entry_price", "exit_price",
            "percent_gain", "stop_triggered", "target_hit",
            "model_confidence", "signal_reason"
        ])

    row = [
        trade_data.get("timestamp", datetime.utcnow().isoformat()),
        trade_data.get("trade_id"),
        trade_data.get("direction"),
        trade_data.get("entry_price"),
        trade_data.get("exit_price"),
        trade_data.get("percent_gain"),
        trade_data.get("stop_triggered"),
        trade_data.get("target_hit"),
        trade_data.get("model_confidence"),
        trade_data.get("signal_reason")
    ]
    worksheet.append_row(row)

# Example usage
if __name__ == "__main__":
    sample_trade = {
        "trade_id": "SPY_20250705_CALL_123",
        "direction": "CALL",
        "entry_price": 445.32,
        "exit_price": 453.11,
        "percent_gain": 1.75,
        "stop_triggered": False,
        "target_hit": True,
        "model_confidence": 0.91,
        "signal_reason": "VWAP bounce + MACD crossover"
    }
    log_trade_to_sheets(sample_trade)
