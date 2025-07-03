import os
import csv
import datetime
import requests
import pandas as pd
import yfinance as yf
import openai
from flask import Flask, render_template_string
from dotenv import load_dotenv

# === Configuration ===
load_dotenv()
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY]):
    raise EnvironmentError("Missing required environment variables")

openai.api_key = OPENAI_API_KEY
TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
}

LOG_FILE = "trade_log.csv"

# === Helpers ===

def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_spy_price():
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    params = {"symbols": "SPY"}
    r = requests.get(url, headers=HEADERS, params=params)
    return float(r.json()["quotes"]["quote"]["last"])

def get_option_symbol(direction: str, strike: int) -> str:
    expiry = get_next_friday().replace("-", "")
    strike_formatted = f"{int(strike * 1000):08d}"
    right = "C" if direction.lower() == "call" else "P"
    return f"SPY{expiry}{right}{strike_formatted}"

def validate_option_symbol(symbol: str) -> bool:
    url = f"{TRADIER_BASE_URL}/markets/options/lookup"
    r = requests.get(url, headers=HEADERS, params={"symbol": symbol})
    if r.status_code != 200:
        return False
    try:
        data = r.json()
        return bool(data.get("options"))
    except Exception:
        return False

def place_option_trade(direction: str, strike_type: str = "ATM"):
    try:
        price = get_spy_price()
        if strike_type == "ITM":
            strike = round(price - 5)
        elif strike_type == "OTM":
            strike = round(price + 5)
        else:
            strike = round(price)
        symbol = get_option_symbol(direction, strike)
        if not validate_option_symbol(symbol):
            return {"status": "error", "error": f"Invalid option {symbol}"}
        payload = {
            "class": "option",
            "symbol": symbol,
            "side": "buy_to_open",
            "quantity": 1,
            "type": "market",
            "duration": "day",
        }
        url = f"{TRADIER_BASE_URL}/accounts/{ACCOUNT_ID}/orders"
        resp = requests.post(url, headers=HEADERS, data=payload)
        data = resp.json()
        if "order" in data:
            return {"status": "success", "symbol": symbol, "underlying_price": price}
        return {"status": "error", "error": data.get("errors", {}).get("error", "Unknown")}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# === GPT Decision ===

def gpt_trade_decision(df: pd.DataFrame) -> dict:
    last_5 = df.tail(5)
    if last_5.empty:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": "Not enough data"}
    prompt = "You're a disciplined SPY options trader. Based on the last 5 minutes of 1-minute candles, should we buy a CALL, PUT, or NOTHING?\n"
    for i, row in last_5.iterrows():
        t = i.strftime('%H:%M')
        prompt += f"{t} - O={row['Open']:.2f}, H={row['High']:.2f}, L={row['Low']:.2f}, C={row['Close']:.2f}, V={int(row['Volume'])}\n"
    prompt += "\nRespond with: CALL, PUT, or NOTHING. Then give a 1-line reason and confidence (0-100). Also suggest: ATM, ITM, or OTM strike."
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You're a disciplined SPY options scalper."}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        text = response.choices[0].message["content"].strip().upper()
        decision = "NOTHING"
        confidence = 0
        strike_type = "ATM"
        if "CALL" in text:
            decision = "CALL"
        elif "PUT" in text:
            decision = "PUT"
        if "CONFIDENCE" in text:
            digits = "".join(c for c in text.split("CONFIDENCE")[1] if c.isdigit())
            confidence = int(digits[:3]) if digits else 0
        if "ITM" in text or "IN-THE-MONEY" in text:
            strike_type = "ITM"
        elif "OTM" in text or "OUT-OF-THE-MONEY" in text:
            strike_type = "OTM"
        return {"decision": decision, "confidence": confidence, "strike_type": strike_type, "raw": text}
    except Exception as e:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": str(e)}

# === Trade Logging ===

def log_header():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Direction", "Option", "Entry Price", "Exit Price", "PnL", "Source", "Time Held", "Stop Hit", "Profit Target Hit", "Confidence", "Reason", "Stop %", "Target %",
            ])

def log_trade(row):
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

# === Trailing Manager ===

def check_trailing_and_update():
    try:
        df = pd.read_csv(LOG_FILE)
        open_trades = df[df["Status"] == "OPEN"]
        if open_trades.empty:
            print("📭 No open trades to monitor.")
            return
        current_price = get_spy_price()
        for idx, row in open_trades.iterrows():
            direction = row["Direction"].lower()
            entry = float(row["EntryPrice"])
            stop_pct = float(row["StopLoss%"]) / 100
            target_pct = float(row["Target%"]) / 100
            gain = (current_price - entry) / entry if direction == "call" else (entry - current_price) / entry
            pnl_percent = round(gain * 100, 2)
            if gain <= -stop_pct:
                df.at[idx, "Status"] = "CLOSED"
                df.at[idx, "PnL"] = pnl_percent
                print(f"🛑 STOP HIT: {direction.upper()} closed at {pnl_percent}%")
            elif gain >= target_pct:
                df.at[idx, "Status"] = "CLOSED"
                df.at[idx, "PnL"] = pnl_percent
                print(f"🎯 TARGET HIT: {direction.upper()} closed at {pnl_percent}%")
            else:
                df.at[idx, "PnL"] = pnl_percent
        df.to_csv(LOG_FILE, index=False)
    except Exception as e:
        print(f"❌ Trailing stop logic error: {e}")

# === Dashboard ===
app = Flask(__name__)

@app.route("/")
def dashboard():
    try:
        df = pd.read_csv(LOG_FILE)
        last_trades = df.tail(10).to_html(classes="data", border=1, index=False)
        total_pnl = df["PnL"].sum()
        win_rate = (df["PnL"] > 0).mean() * 100 if len(df) > 0 else 0
        avg_gain = df["PnL"].mean() if len(df) > 0 else 0
        open_trades = df[df["Status"] == "OPEN"]
        open_pnl = open_trades["PnL"].sum() if not open_trades.empty else 0
    except Exception as e:
        last_trades = f"<p>No trades found or error reading file: {e}</p>"
        total_pnl = win_rate = avg_gain = open_pnl = 0
    html = f"""
    <html>
    <head>
        <title>Money Printer Dashboard</title>
    </head>
    <body>
        <h1>💰 Money Printer Dashboard</h1>
        <p><strong>Total Realized PnL:</strong> ${total_pnl:.2f}</p>
        <p><strong>Live Open PnL:</strong> ${open_pnl:.2f}</p>
        <p><strong>Win Rate:</strong> {win_rate:.2f}%</p>
        <p><strong>Average Gain/Loss:</strong> {avg_gain:.4f}</p>
        <h3>Recent Trades:</h3>
        {last_trades}
    </body>
    </html>
    """
    return html

# === Strike Tester ===

def test_strikes():
    expiry = get_next_friday()
    try:
        spy_price = get_spy_price()
    except Exception:
        spy_price = 545
    for direction in ["call", "put"]:
        print(f"\nTesting {direction.upper()}S:")
        for strike in range(int(spy_price) - 15, int(spy_price) + 16, 5):
            symbol = get_option_symbol(direction, strike)
            valid = validate_option_symbol(symbol)
            if valid:
                print(f"✅ VALID: {symbol}")
            else:
                print(f"❌ INVALID: {symbol}")

# === Main Bot ===

def run_bot():
    print("📈 Downloading SPY data...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        print("❌ No SPY data retrieved.")
        return
    print("🧠 Running GPT decision logic...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result.get("confidence", 0) < 50:
        print(f"⚠️ SKIP: Confidence {result.get('confidence', 0)}% | Reason: {result.get('reason', 'Low confidence')}")
        return
    print(f"✅ Decision: {result['decision']} | Strike: {result['strike_type']} | Confidence: {result['confidence']}%")
    trade = place_option_trade(result["decision"], result["strike_type"])
    if trade["status"] == "success":
        print(f"📤 ORDER PLACED: {trade['symbol']} at ${trade['underlying_price']:.2f}")
    else:
        print(f"❌ ORDER FAILED: {trade.get('error', 'Unknown error')}")

# === CLI ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Combined Money Printer script")
    parser.add_argument("command", choices=["run", "dashboard", "monitor", "test-strikes"], help="Action to perform")
    args = parser.parse_args()

    if args.command == "run":
        run_bot()
    elif args.command == "dashboard":
        app.run(debug=False)
    elif args.command == "monitor":
        check_trailing_and_update()
    elif args.command == "test-strikes":
        test_strikes()

