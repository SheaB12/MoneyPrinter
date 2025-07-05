import os
import datetime
import json
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from collections import defaultdict

try:
    import openai
except Exception:
    openai = None

# === Load Configuration ===
load_dotenv()
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OFFLINE_ENV = os.getenv("OFFLINE", "0") == "1"
OFFLINE = OFFLINE_ENV or not all([TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY]) or openai is None
if not OFFLINE and openai is not None:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
} if not OFFLINE else {}

PERF_LOG = "performance_log.json"

# === Discord Alerts ===
def send_discord_embed(title, description, color=0x5865F2, fields=None):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ No Discord webhook URL found.")
        return
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "footer": {"text": "Money Printer Bot"},
    }
    if fields:
        embed["fields"] = fields
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, headers={"Content-Type": "application/json"})
    except Exception as e:
        print(f"❌ Failed to send Discord embed: {e}")

# === Utility Functions ===
def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_spy_price():
    if OFFLINE:
        data = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
        return float(data["Close"].iloc[-1])
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    params = {"symbols": "SPY"}
    r = requests.get(url, headers=HEADERS, params=params)
    return float(r.json()["quotes"]["quote"]["last"])

# === Option Symbol Fetching ===
def get_valid_option_symbol(direction, strike_type="ATM"):
    if OFFLINE:
        return "SPY_FAKE_OPTION", 500.00
    expiry = get_next_friday()
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    params = {"symbol": "SPY", "expiration": expiry, "greeks": "false"}
    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json()
    options = data.get("options", {}).get("option", [])
    current_price = get_spy_price()
    right = "call" if direction.lower() == "call" else "put"
    filtered = [opt for opt in options if opt["option_type"] == right]
    sorted_opts = sorted(filtered, key=lambda x: abs(x["strike"] - current_price))
    if strike_type == "ATM":
        return sorted_opts[0]["symbol"], sorted_opts[0]["strike"]
    elif strike_type == "ITM":
        for o in sorted_opts:
            if (o["strike"] < current_price if right == "call" else o["strike"] > current_price):
                return o["symbol"], o["strike"]
    elif strike_type == "OTM":
        for o in sorted_opts:
            if (o["strike"] > current_price if right == "call" else o["strike"] < current_price):
                return o["symbol"], o["strike"]
    return sorted_opts[0]["symbol"], sorted_opts[0]["strike"]

# === Simulated Trade Execution ===
def place_option_trade(direction, strike_type="ATM"):
    try:
        symbol, strike = get_valid_option_symbol(direction, strike_type)
        entry = get_spy_price()
        print(f"[PAPER] {direction} {strike_type} | {symbol} | Entry: ${entry:.2f}")
        return {"status": "success", "symbol": symbol, "entry": entry, "strike": strike}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# === Simulated Exit Logic ===
def simulate_exit(entry_price, direction):
    current_price = get_spy_price()
    pct_change = ((current_price - entry_price) / entry_price) * 100
    if direction == "PUT":
        pct_change *= -1
    return round(pct_change, 2)

# === GPT Decision Logic ===
def gpt_trade_decision(df):
    last_5 = df.tail(5)
    if last_5.empty:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": "Not enough data"}
    if OFFLINE or openai is None:
        diff = last_5["Close"].iloc[-1] - last_5["Open"].iloc[0]
        decision = "CALL" if diff > 0 else "PUT"
        return {"decision": decision, "confidence": 70, "strike_type": "ATM", "reason": "Offline heuristic"}
    prompt = "Based on the last 5 candles should we buy CALL, PUT, or NOTHING?\n"
    for _, row in last_5.iterrows():
        if isinstance(row.name, pd.Timestamp):
            time_str = row.name.strftime('%H:%M')
        else:
            time_str = str(row.name)
        prompt += f"\n{time_str} - O:{row['Open']:.2f} H:{row['High']:.2f} L:{row['Low']:.2f} C:{row['Close']:.2f}"
    prompt += "\nRespond with CALL, PUT, or NOTHING. Include confidence (0-100) and strike type (ATM, ITM, OTM)."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a disciplined SPY options scalper."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )
        text = response.choices[0].message.content.upper()
        decision = "NOTHING"
        if "CALL" in text:
            decision = "CALL"
        elif "PUT" in text:
            decision = "PUT"
        confidence = int("".join(c for c in text.split("CONFIDENCE")[-1] if c.isdigit())[:3] or "0")
        strike_type = "ATM"
        if "OTM" in text: strike_type = "OTM"
        elif "ITM" in text: strike_type = "ITM"
        return {"decision": decision, "confidence": confidence, "strike_type": strike_type, "raw": text}
    except Exception as e:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": str(e)}

# === Performance Logger ===
def log_performance(win, pnl):
    if not os.path.exists(PERF_LOG):
        with open(PERF_LOG, "w") as f:
            json.dump([], f)
    with open(PERF_LOG, "r") as f:
        data = json.load(f)
    data.append({
        "date": datetime.date.today().isoformat(),
        "win": win,
        "pnl": pnl
    })
    with open(PERF_LOG, "w") as f:
        json.dump(data, f, indent=2)

def send_weekly_summary():
    if not os.path.exists(PERF_LOG):
        print("No performance data.")
        return
    with open(PERF_LOG) as f:
        data = json.load(f)
    this_week = [d for d in data if datetime.date.fromisoformat(d["date"]).isocalendar()[1] == datetime.date.today().isocalendar()[1]]
    if not this_week:
        return
    total = len(this_week)
    wins = sum(1 for d in this_week if d["win"])
    avg_pnl = round(sum(d["pnl"] for d in this_week) / total, 2)
    send_discord_embed(
        "📊 Weekly Performance Summary",
        f"Total Trades: {total}\nWins: {wins}\nWin Rate: {wins/total:.2%}\nAvg PnL: {avg_pnl:.2f}%",
        color=0x7289DA
    )

# === Main Bot ===
def run_bot():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        send_discord_embed("❌ Error", "SPY data unavailable.", color=0xFF0000)
        return
    print("🧠 GPT making decision...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        send_discord_embed("⚠️ No Trade", "Low confidence or nothing chosen.", color=0xAAAAAA)
        return
    send_discord_embed("✅ Trade Signal", f"{result['decision']} | {result['strike_type']} | Confidence: {result['confidence']}%")
    trade = place_option_trade(result["decision"], result["strike_type"])
    if trade["status"] != "success":
        send_discord_embed("❌ Trade Error", trade["error"], color=0xFF0000)
        return
    pnl = simulate_exit(trade["entry"], result["decision"])
    win = pnl > 0
    print(f"💰 Simulated Exit: PnL = {pnl}%")
    log_performance(win, pnl)
    send_discord_embed(
        "📤 Simulated Exit",
        f"{'✅ WIN' if win else '❌ LOSS'} | PnL: {pnl:.2f}%",
        color=0x2ECC71 if win else 0xE74C3C
    )

# === CLI ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "weekly"])
    args = parser.parse_args()
    if args.command == "run":
        run_bot()
    elif args.command == "weekly":
        send_weekly_summary()
