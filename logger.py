import os
import json
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from gspread_formatting import CellFormat, Color, format_cell_range

GOOGLE_SHEETS_KEY_B64 = os.getenv("GOOGLE_SHEETS_KEY_B64")
SHEET_ID = "10iX_0DoMMmgMdWPWH8EUOs19wphOIfqybloG_KRvo9U"

def get_sheet():
    # Decode service account key safely
    if not os.path.exists("google_sheets.json"):
        if not GOOGLE_SHEETS_KEY_B64:
            raise ValueError("Missing GOOGLE_SHEETS_KEY_B64 or google_sheets.json")
        with open("google_sheets.json", "w") as f:
            f.write(base64_decode(GOOGLE_SHEETS_KEY_B64))

    creds = ServiceAccountCredentials.from_json_keyfile_name("google_sheets.json", [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ])
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def base64_decode(b64_str):
    import base64
    return base64.b64decode(b64_str).decode("utf-8")

def get_results_tab(sheet):
    try:
        return sheet.worksheet("Results")
    except:
        return sheet.add_worksheet(title="Results", rows="1000", cols="20")

def log_trade_decision(data):
    sheet = get_sheet()
    ws = get_results_tab(sheet)

    now = datetime.utcnow()
    month = now.strftime("%Y-%m")
    strategy = "GPT"
    row_id = f"{month}-{strategy}"

    headers = ["date", "strategy", "action", "confidence", "reason", "result", "pnl"]
    try:
        existing = ws.row_values(1)
        if existing != headers:
            ws.resize(rows=1)
            ws.update("A1:G1", [headers])
    except:
        ws.update("A1:G1", [headers])

    row = [
        now.strftime("%Y-%m-%d"),
        strategy,
        data.get("action", "").lower(),
        data.get("confidence", 0),
        data.get("reason", ""),
        data.get("result", ""),
        data.get("pnl", "")
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")

    # Apply color to the result column
    format_result_colors(ws)

def format_result_colors(ws):
    try:
        import gspread_formatting as gsf
        records = ws.get_all_records()
        for i, row in enumerate(records, start=2):
            result = row.get("result", "").lower()
            if "win" in result:
                fmt = CellFormat(backgroundColor=Color(0.8, 1, 0.8))
            elif "loss" in result:
                fmt = CellFormat(backgroundColor=Color(1, 0.8, 0.8))
            else:
                continue
            format_cell_range(ws, f"A{i}:G{i}", fmt)
    except Exception as e:
        print(f"⚠️ Formatting failed: {e}")

def get_recent_logs(sheet, limit=5):
    ws = get_results_tab(sheet)
    records = ws.get_all_records()
    recent = records[-limit:] if records else []
    return recent

def get_daily_summary():
    try:
        sheet = get_sheet()
        ws = get_results_tab(sheet)
        records = ws.get_all_records()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_logs = [r for r in records if r["date"] == today]

        if not today_logs:
            return None

        total = len(today_logs)
        wins = sum(1 for r in today_logs if "win" in str(r.get("result", "")).lower())
        losses = total - wins
        avg_pnl = sum(float(r.get("pnl", 0) or 0) for r in today_logs) / total

        summary = (
            f"📅 Date: `{today}`\n"
            f"📊 Trades: `{total}` | ✅ Wins: `{wins}` | ❌ Losses: `{losses}`\n"
            f"💰 Avg PnL: `{avg_pnl:.2f}%`\n"
        )
        return summary
    except Exception as e:
        print(f"❌ Error generating daily summary: {e}")
        return None
