# logger.py

import os
import datetime
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# --- Constants ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = "10iX_0DoMMmgMdWPWH8EUOs19wphOIfqybloG_KRvo9U"  # Replace with your actual ID
DECISIONS_TAB = "Decisions"
RESULTS_TAB = "Results"

# --- Setup Credentials ---
def get_client():
    creds_path = "google_sheets.json"
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client

def ensure_tab_exists(sheet, tab_name):
    try:
        return sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        return sheet.add_worksheet(title=tab_name, rows="1000", cols="20")

# --- Logger for GPT Decisions ---
def log_trade_decision(decision_data):
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = ensure_tab_exists(sheet, DECISIONS_TAB)

        date = datetime.datetime.now().strftime("%Y-%m-%d")
        strategy = decision_data.get("strategy", "Default")
        row = [
            date,
            strategy,
            decision_data["action"],
            decision_data["confidence"],
            decision_data["reason"]
        ]

        ws.append_row(row)
        auto_resize(ws)
    except Exception as e:
        print(f"Logging decision failed: {e}")

# --- Logger for Trade Results ---
def log_trade_result(result_data):
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = ensure_tab_exists(sheet, RESULTS_TAB)

        now = datetime.datetime.now()
        date = now.strftime("%Y-%m-%d")
        month = now.strftime("%B")
        strategy = result_data.get("strategy", "Default")
        pnl = result_data["pnl"]
        win = result_data["win"]
        row = [
            date,
            month,
            strategy,
            result_data["action"],
            result_data["confidence"],
            result_data["entry"],
            result_data["exit"],
            result_data["pnl"],
            "WIN" if win else "LOSS"
        ]

        ws.append_row(row)
        auto_resize(ws)

        # Apply color
        format_win_loss(ws)

        # Generate monthly summary
        summarize_month(ws, month)

    except Exception as e:
        print(f"Logging result failed: {e}")

# --- Format win/loss rows ---
def format_win_loss(ws):
    records = ws.get_all_values()
    for i, row in enumerate(records[1:], start=2):  # skip header
        try:
            result = row[-1].upper()
            fmt = CellFormat(
                backgroundColor={"red": 0.8, "green": 1.0, "blue": 0.8} if result == "WIN"
                else {"red": 1.0, "green": 0.8, "blue": 0.8}
            )
            format_cell_range(ws, f"A{i}:I{i}", fmt)
        except Exception:
            continue

# --- Resize all columns ---
def auto_resize(ws):
    sheet_id = ws._properties['sheetId']
    requests = [{
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": 0,
                "endIndex": 10
            }
        }
    }]
    ws.spreadsheet.batch_update({"requests": requests})

# --- Generate Monthly Summary ---
def summarize_month(ws, month):
    data = ws.get_all_records()
    monthly = [r for r in data if r["Month"] == month]

    if not monthly:
        return

    wins = sum(1 for r in monthly if r["Result"] == "WIN")
    losses = sum(1 for r in monthly if r["Result"] == "LOSS")
    total = len(monthly)
    avg_pnl = round(sum(float(r["PnL"]) for r in monthly) / total, 2)

    summary_row = [f"SUMMARY for {month}", "", "", "", "", "", "", f"Avg PnL: {avg_pnl}", f"Wins: {wins} / {total}"]
    ws.append_row([""] * len(summary_row))  # Empty row
    ws.append_row(summary_row)

# --- Daily Summary for Discord ---
def get_daily_summary():
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID)
        ws = ensure_tab_exists(sheet, RESULTS_TAB)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        records = ws.get_all_records()

        today_logs = [r for r in records if r["Date"] == today]
        if not today_logs:
            return "📉 No trades logged for today."

        wins = sum(1 for r in today_logs if r["Result"] == "WIN")
        total = len(today_logs)
        avg_pnl = round(sum(float(r["PnL"]) for r in today_logs) / total, 2)

        return (
            f"📊 **Daily Summary ({today})**\n"
            f"Trades: {total}\n"
            f"Wins: {wins}\n"
            f"Avg PnL: {avg_pnl}\n"
        )
    except Exception as e:
        return f"Error generating daily summary: {e}"
