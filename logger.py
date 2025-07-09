import os
import base64
import json
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

SPREADSHEET_NAME = "Money Printer Logs"
SHEET_NAME = "Decisions"

def load_gsheets_client():
    key_b64 = os.getenv("GOOGLE_SHEETS_KEY_B64")
    if not key_b64:
        raise ValueError("GOOGLE_SHEETS_KEY_B64 environment variable is not set.")

    try:
        key_json = base64.b64decode(key_b64).decode()
        creds_dict = json.loads(key_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        raise RuntimeError(f"Error loading Google Sheets credentials: {e}")

def log_to_sheet(row):
    try:
        client = load_gsheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)
        sheet.append_row(row, value_input_option="USER_ENTERED")
        print("📄 Logged to Google Sheet.")
    except Exception as e:
        print(f"⚠️ Logging failed: {e}")

def get_recent_logs(limit=20):
    try:
        client = load_gsheets_client()
        sheet = client.open(SPREADSHEET_NAME).worksheet(SHEET_NAME)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df = df.tail(limit)
        return df
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        return pd.DataFrame()
