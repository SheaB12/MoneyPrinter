import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SHEET_NAME = "Money Printer Logs"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("google_sheets.json", scopes=SCOPES)
client = gspread.authorize(creds)

def get_or_create_sheet(sheet_name, tab, headers):
    try:
        sheet = client.open(sheet_name)
    except:
        sheet = client.create(sheet_name)
    try:
        worksheet = sheet.worksheet(tab)
    except:
        worksheet = sheet.add_worksheet(title=tab, rows="1000", cols="20")
        worksheet.append_row(headers)
    return worksheet

def log_to_sheet(row, tab):
    headers = ["Timestamp", "Decision", "Confidence", "Reason", "Status"]
    sheet = get_or_create_sheet(SHEET_NAME, tab, headers)
    sheet.append_row(row)

def get_recent_stats():
    try:
        worksheet = client.open(SHEET_NAME).worksheet("GPT Decisions")
        data = worksheet.get_all_records()
        if not data:
            return {}

        df = pd.DataFrame(data)
        recent = df.tail(20)

        win_rate = (recent["Status"] == "EXECUTED").mean()
        avg_conf = recent["Confidence"].mean()
        atr = (recent["Confidence"].max() - recent["Confidence"].min())  # crude proxy for volatility

        return {"win_rate": win_rate, "avg_confidence": avg_conf, "atr": atr}
    except:
        return {}
