import os
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import *

# Google Sheets setup
def get_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_sheets.json", [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    return client.open_by_key("10iX_0DoMMmgMdWPWH8EUOs19wphOIfqybloG_KRvo9U")

# Auto-resize columns
def autosize(worksheet):
    try:
        set_column_width(worksheet, 'A', 200)
        auto_resize_columns(worksheet, 1, worksheet.col_count)
    except Exception:
        pass

# Create worksheet if it doesn't exist
def ensure_tab(sheet, tab_name, headers):
    try:
        worksheet = sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab_name, rows="1000", cols="20")
        worksheet.append_row(headers)
    return worksheet

# Log decision with confidence and GPT output
def log_trade_decision(data):
    sheet = get_sheet()
    tab_name = "Decisions"
    headers = ["Timestamp", "Strategy", "Action", "Confidence", "Reason"]

    ws = ensure_tab(sheet, tab_name, headers)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = [now, data.get("strategy", "Unknown"), data["action"], data["confidence"], data["reason"]]
    ws.append_row(row)
    autosize(ws)

# Log final trade outcome with result and performance
def log_trade_result(result_data):
    sheet = get_sheet()
    tab_name = "Results"
    headers = ["Timestamp", "Strategy", "Action", "Confidence", "Win/Loss", "PnL%", "Comment"]

    ws = ensure_tab(sheet, tab_name, headers)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = [
        now,
        result_data.get("strategy", "Unknown"),
        result_data["action"],
        result_data["confidence"],
        result_data["outcome"],
        result_data.get("pnl", ""),
        result_data.get("comment", "")
    ]
    ws.append_row(row)

    # Color-code win/loss
    row_index = len(ws.get_all_values())
    color = {
        "WIN": (0.8, 1.0, 0.8),
        "LOSS": (1.0, 0.8, 0.8)
    }.get(result_data["outcome"].upper(), (1, 1, 1))

    fmt = cellFormat(backgroundColor=color)
    format_cell_range(ws, f"A{row_index}:G{row_index}", fmt)
    autosize(ws)

# Return recent logs (last 30)
def get_recent_logs(sheet, tab_name="Results", num_rows=30):
    try:
        ws = sheet.worksheet(tab_name)
        records = ws.get_all_records()
        return records[-num_rows:] if len(records) >= num_rows else records
    except Exception as e:
        print("Error fetching logs:", e)
        return []

# Generate daily performance summary
def get_daily_summary():
    sheet = get_sheet()
    ws = ensure_tab(sheet, "Results", [])
    today = datetime.now().strftime("%Y-%m-%d")

    records = ws.get_all_records()
    daily = [r for r in records if r["Timestamp"].startswith(today)]

    wins = sum(1 for r in daily if r["Win/Loss"].upper() == "WIN")
    losses = sum(1 for r in daily if r["Win/Loss"].upper() == "LOSS")
    total = wins + losses
    avg_pnl = round(sum(float(r["PnL%"]) for r in daily if r["PnL%"]) / total, 2) if total > 0 else 0

    return (
        f"📊 **Daily Summary for {today}**\n"
        f"✅ Wins: {wins}\n"
        f"❌ Losses: {losses}\n"
        f"💰 Avg PnL: {avg_pnl}%\n"
        f"📈 Total Trades: {total}"
    )
