import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import os

# Setup Google Sheets connection
def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "google_sheets.json")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    return gspread.authorize(creds)

# Log a trade result to the Google Sheet
def log_trade_result(result: dict):
    try:
        client = get_gsheet_client()
        sheet = client.open("MoneyPrinter Log").worksheet("Trades")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            now,
            result.get("action", ""),
            result.get("confidence", 0),
            result.get("status", ""),
            result.get("pnl", 0),
            result.get("reason", "")
        ]
        sheet.append_row(row)
    except Exception as e:
        print(f"Logging Error: {e}")

# ✅ NEW: Log GPT decision separately
def log_trade_decision(decision: dict):
    try:
        client = get_gsheet_client()
        sheet = client.open("MoneyPrinter Log").worksheet("Decisions")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            now,
            decision.get("action", ""),
            decision.get("confidence", 0),
            decision.get("reason", "")
        ]
        sheet.append_row(row)
    except Exception as e:
        print(f"Decision Logging Error: {e}")

# Optional: Fetch recent logs if needed by GPT or stats
def get_recent_logs(limit=10):
    try:
        client = get_gsheet_client()
        sheet = client.open("MoneyPrinter Log").worksheet("Trades")
        records = sheet.get_all_records()
        return records[-limit:]
    except Exception as e:
        print(f"Error fetching logs: {e}")
        return []
