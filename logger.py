import os
import json
import base64
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

# Load credentials from env variable
google_key = os.getenv("GOOGLE_SHEETS_KEY_B64")
if not google_key:
    raise ValueError("GOOGLE_SHEETS_KEY_B64 environment variable is not set.")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(base64.b64decode(google_key))
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(credentials)

SHEET_NAME = "GPT_Trade_Log"
TAB_NAME = "GPT Decisions"
HEADERS = ["Timestamp", "Direction", "Confidence", "Threshold", "Reason", "Status", "Symbol", "Price"]

def get_or_create_sheet():
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(SHEET_NAME).sheet1
        sheet.update_title(TAB_NAME)
        sheet.append_row(HEADERS)
    except gspread.WorksheetNotFound:
        sheet = client.open(SHEET_NAME).add_worksheet(title=TAB_NAME, rows="1000", cols="20")
        sheet.append_row(HEADERS)
    return sheet

def log_trade_decision(direction, confidence, threshold, reason, status, symbol="N/A", price="N/A"):
    sheet = get_or_create_sheet()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [timestamp, direction, round(confidence, 2), round(threshold, 2), reason, status, symbol, price]
    sheet.append_row(row)

def get_recent_logs():
    try:
        sheet = get_or_create_sheet()
        data = sheet.get_all_records()
        return pd.DataFrame(data).tail(20)
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        return pd.DataFrame()
