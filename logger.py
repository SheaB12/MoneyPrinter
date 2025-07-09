import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import traceback

# Define your sheet ID and sheet/tab name here
SHEET_ID = MoneyPrinter Logs  # <- Replace this with your actual Sheet ID
SHEET_NAME = "Logs"

def get_credentials():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("google_sheets.json", scopes=scopes)
    return creds

def log_trade_decision(decision_data):
    try:
        creds = get_credentials()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

        # Prepare row to append
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        row = [
            now,
            decision_data.get("action", ""),
            decision_data.get("confidence", ""),
            decision_data.get("reason", ""),
        ]

        sheet.append_row(row)
        print("✅ Decision logged to Google Sheets.")

    except Exception as e:
        print("📛 Error while logging to Google Sheets.")
        traceback.print_exc()
        print(f"📛 Raw error: {e}")

def get_recent_logs():
    try:
        creds = get_credentials()
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

        rows = sheet.get_all_values()
        print(f"📋 Fetched {len(rows)} rows from the log.")
        return rows[-5:] if len(rows) >= 5 else rows

    except Exception as e:
        print("📛 Error fetching logs:")
        traceback.print_exc()
        print(f"📛 Raw error: {e}")
        return []
