from flask import Flask, render_template_string
import pandas as pd
import requests
from config import TRADIER_TOKEN, ACCOUNT_ID

app = Flask(__name__)

def get_tradier_balance():
    url = f"https://sandbox.tradier.com/v1/accounts/{ACCOUNT_ID}/balances"
    headers = {
        "Authorization": f"Bearer {TRADIER_TOKEN}",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        return float(data["balances"]["total_cash"])
    except Exception as e:
        print("Tradier API error:", e)
        return None

def calculate_stats(df):
    total_pnl = df["PnL"].sum()
    win_rate = (df["PnL"] > 0).mean() * 100 if len(df) > 0 else 0
    avg_gain = df["PnL"].mean() if len(df) > 0 else 0
    open_trades = df[df["Status"] == "OPEN"]
    open_pnl = open_trades["PnL"].sum() if not open_trades.empty else 0
    return total_pnl, win_rate, avg_gain, open_pnl

@app.route("/")
def dashboard():
    try:
        df = pd.read_csv("trade_log.csv")
        last_trades = df.tail(10).to_html(classes="data", border=1, index=False)
        total_pnl, win_rate, avg_gain, open_pnl = calculate_stats(df)
    except Exception as e:
        last_trades = f"<p>No trades found or error reading file: {e}</p>"
        total_pnl = win_rate = avg_gain = open_pnl = 0

    balance = get_tradier_balance()
    balance_display = f"${balance:.2f}" if balance is not None else "Unavailable"

    html = f"""
    <html>
    <head>
        <title>Money Printer Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 30px; background-color: #f9f9f9; }}
            .header {{ margin-bottom: 20px; }}
            .stats {{ margin-top: 20px; }}
            .data {{ border-collapse: collapse; width: 100%; }}
            .data td, .data th {{ border: 1px solid #ddd; padding: 8px; }}
            .data th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>💰 Money Printer Dashboard</h1>
            <p><strong>Tradier Account Balance:</strong> {balance_display}</p>
            <p><strong>Total Realized PnL:</strong> ${total_pnl:.2f}</p>
            <p><strong>Live Open PnL:</strong> ${open_pnl:.2f}</p>
        </div>
        <div class="stats">
            <p><strong>Win Rate:</strong> {win_rate:.2f}%</p>
            <p><strong>Average Gain/Loss per Trade:</strong> {avg_gain:.4f}</p>
        </div>
        <h3>Recent Trades:</h3>
        {last_trades}
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    app.run(debug=False)
