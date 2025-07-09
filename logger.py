import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from datetime import datetime

# Set up Google Sheets credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("google_sheets.json", scope)
client = gspread.authorize(credentials)

SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "MoneyPrinter Logs")

# Auto-create sheet if not found
def get_or_create_sheet(sheet_name: str, tab: str, headers: list):
    try:
        sheet = client.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        sheet = client.create(sheet_name)
        sheet.share(credentials.service_account_email, perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab, rows="1000", cols="20")
        worksheet.append_row(headers)

    return worksheet

# GPT Decision logger
def log_to_sheet(row_data: list):
    headers = ["Timestamp", "Decision", "Confidence", "Reason", "Action Taken"]
    sheet = get_or_create_sheet(SHEET_NAME, "GPT Decisions", headers)
    sheet.append_row(row_data)

# Trade logger
def log_trade_to_sheets(ticker, entry_price, exit_price, pnl, status):
    headers = ["Timestamp", "Ticker", "Entry", "Exit", "PnL", "Status"]
    sheet = get_or_create_sheet(SHEET_NAME, "Trade Log", headers)
    sheet.append_row([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ticker, entry_price, exit_price, pnl, status
    ])
