import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# Setup for Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("google_sheets.json", scope)
client = gspread.authorize(credentials)

# ENV sheet name, default fallback
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "MoneyPrinter Logs")

# ⬇️ Function for logging general GPT decisions
def log_to_sheet(row_data: list):
    tab = "GPT Decisions"
    try:
        sheet = client.open(SHEET_NAME).worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open(SHEET_NAME).add_worksheet(title=tab, rows="1000", cols="10")
        sheet.append_row(["Timestamp", "Decision", "Confidence", "Reason", "Action Taken"])
    sheet.append_row(row_data)

# ⬇️ Function for logging trades (example schema)
def log_trade_to_sheets(ticker, entry_price, exit_price, pnl, status):
    tab = "Trade Log"
    try:
        sheet = client.open(SHEET_NAME).worksheet(tab)
    except gspread.exceptions.WorksheetNotFound:
        sheet = client.open(SHEET_NAME).add_worksheet(title=tab, rows="1000", cols="10")
        sheet.append_row(["Ticker", "Entry", "Exit", "PnL", "Status"])

    sheet.append_row([ticker, entry_price, exit_price, pnl, status])
