import os
import gspread
import base64
import json
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_key = os.getenv("GOOGLE_SHEETS_KEY_B64")

if not google_key:
    raise ValueError("GOOGLE_SHEETS_KEY_B64 environment variable is not set. Check GitHub Actions config.")

creds_dict = json.loads(base64.b64decode(google_key))
credentials = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(credentials)

SHEET_NAME = "GPT_Trade_Log"

def get_or_create_sheet(sheet_name, tab_name, headers):
    try:
        sheet = client.open(sheet_name).worksheet(tab_name)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(sheet_name).sheet1
        sheet.update_title(tab_name)
        sheet.append_row(headers)
    except gspread.WorksheetNotFound:
        sheet = client.open(sheet_name).add_worksheet(title=tab_name, rows="1000", cols="20")
        sheet.append_row(headers)
    return sheet

def log_to_sheet(row_data):
    headers = ["Timestamp", "Direction", "Confidence", "Status", "Reason"]
    sheet = get_or_create_sheet(SHEET_NAME, "GPT Decisions", headers)
    sheet.append_row(row_data)

def get_recent_logs(n=30):
    """Fetch last n rows from the GPT Decisions tab."""
    try:
        sheet = client.open(SHEET_NAME).worksheet("GPT Decisions")
        records = sheet.get_all_records()
        return records[-n:] if len(records) >= n else records
    except Exception as e:
        print(f"Error fetching recent logs: {e}")
        return []
