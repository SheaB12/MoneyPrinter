import os
import datetime
import json
import pandas as pd
import yfinance as yf
import requests
from dotenv import load_dotenv

try:
    import openai
except ImportError:
    openai = None

# === Load Environment ===
load_dotenv()
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OFFLINE = os.getenv("OFFLINE", "0") == "1"

if not OFFLINE and openai is not None:
    openai.api_key = OPENAI_API_KEY

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
} if not OFFLINE else {}

PERF_LOG_FILE = "performance_log.json"

# === Discord Alerts ===
def send_discord_embed(title, description, color=0x5865F2, fields=None):
    if not DISCORD_WEBHOOK_URL:
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
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
    except Exception as e:
        print(f"❌ Discord alert failed: {e}")

# === Option Helpers ===
def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_spy_price():
    if OFFLINE:
        df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
        return float(df["Close"].iloc[-1])
    r = requests.get(f"{TRADIER_BASE_URL}/markets/quotes", headers=HEADERS, params={"symbols": "SPY"})
    return float(r.json()["quotes"]["quote"]["last"])

def get_valid_option_symbol(direction: str, strike_type="ATM"):
    if OFFLINE:
        return "SPY_FAKE_OPTION", 500.0
    expiry = get_next_friday()
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    params = {"symbol": "SPY", "expiration": expiry}
    r = requests.get(url, headers=HEADERS, params=params)
    options = r.json().get("options", {}).get("option", [])
    if not options:
        raise RuntimeError("Tradier returned no option chain")

    current_price = get_spy_price()
    right = "call" if direction.lower() == "call" else "put"
    filtered = [opt for opt in options if opt["option_type"] == right]
    sorted_opts = sorted(filtered, key=lambda x: abs(x["strike"] - current_price))

    if strike_type == "ATM":
        selected = sorted_opts[0]
    elif strike_type == "ITM":
        selected = next((o for o in sorted_opts if
                         (o["strike"] < current_price if right == "call" else o["strike"] > current_price)), sorted_opts[0])
    elif strike_type == "OTM":
        selected = next((o for o in sorted_opts if
                         (o["strike"] > current_price if right == "call" else o["strike"] < current_price)), sorted_opts[0])
    else:
        selected = sorted_opts[0]
    return selected["symbol"], selected["strike"]

# === Simulated Trade Logic ===
def simulate_exit(entry_price: float, direction: str):
    exit_price = get_spy_price()
    gain = (exit_price - entry_price) if direction == "CALL" else (entry_price - exit_price)
    return exit_price, gain

def log_trade(win: bool):
    today = datetime.date.today().isoformat()
    if not os.path.exists(PERF_LOG_FILE):
        data = {}
    else:
        with open(PERF_LOG_FILE, "r") as f:
            data = json.load(f)

    if today not in data:
        data[today] = {"wins": 0, "losses": 0}
    if win:
        data[today]["wins"] += 1
    else:
        data[today]["losses"] += 1

    with open(PERF_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def send_summary(days=7):
    if not os.path.exists(PERF_LOG_FILE):
        return
    with open(PERF_LOG_FILE, "r") as f:
        data = json.load(f)

    summary = {}
    for date, stats in data.items():
        d = datetime.date.fromisoformat(date)
        if d >= datetime.date.today() - datetime.timedelta(days=days):
            summary[date] = stats

    wins = sum(v["wins"] for v in summary.values())
    losses = sum(v["losses"] for v in summary.values())
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0

    send_discord_embed(
        f"📊 {'Weekly' if days == 7 else 'Daily'} Performance Summary",
        f"Period: Last {days} day(s)",
        color=0x3498DB,
        fields=[
            {"name": "Trades", "value": str(total), "inline": True},
            {"name": "Wins", "value": str(wins), "inline": True},
            {"name": "Losses", "value": str(losses), "inline": True},
            {"name": "Win Rate", "value": f"{win_rate:.1f}%", "inline": True},
        ],
    )

# === GPT Logic ===
def gpt_trade_decision(df: pd.DataFrame) -> dict:
    last_5 = df.tail(5)
    if last_5.empty:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": "Not enough data"}
    if OFFLINE or openai is None:
        diff = last_5["Close"].iloc[-1] - last_5["Open"].iloc[0]
        if abs(diff) < 0.05:
            return {"decision": "NOTHING", "confidence": 50, "strike_type": "ATM", "reason": "Small movement"}
        decision = "CALL" if diff > 0 else "PUT"
        confidence = min(int(abs(diff) * 10), 100)
        return {"decision": decision, "confidence": confidence, "strike_type": "ATM", "reason": "Heuristic"}

    prompt = "You're a disciplined SPY options trader. Based on the last 5 minutes of 1-minute candles, should we buy a CALL, PUT, or NOTHING?\n"
    for i, row in last_5.iterrows():
        try:
            t = i.strftime('%H:%M')
            prompt += f"\n{t} - O:{float(row['Open']):.2f} H:{float(row['High']):.2f} L:{float(row['Low']):.2f} C:{float(row['Close']):.2f} V:{int(row['Volume'])}"
        except Exception as e:
            prompt += f"\nERROR formatting row: {e}"
    prompt += "\n\nRespond with: CALL, PUT, or NOTHING. Then give a 1-line reason and confidence (0-100). Also suggest: ATM, ITM, or OTM strike."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a disciplined SPY options scalper."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=150,
        )
        text = response.choices[0].message.content.upper()
        decision = "CALL" if "CALL" in text else "PUT" if "PUT" in text else "NOTHING"
        confidence = int("".join(filter(str.isdigit, text.split("CONFIDENCE")[-1]))) if "CONFIDENCE" in text else 0
        strike_type = "ITM" if "ITM" in text else "OTM" if "OTM" in text else "ATM"
        return {"decision": decision, "confidence": confidence, "strike_type": strike_type, "raw": text}
    except Exception as e:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": str(e)}

# === Main Bot ===
def run_bot():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        send_discord_embed("❌ Data Error", "SPY data not retrieved.", color=0xE74C3C)
        return

    print("🧠 GPT making decision...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        send_discord_embed("⚠️ No Trade", f"Confidence {result['confidence']}% — Reason: {result.get('reason', 'Low confidence')}", color=0xF1C40F)
        return

    print(f"📥 Simulated Entry — {result['decision']} ({result['strike_type']})")
    symbol, _ = get_valid_option_symbol(result["decision"], result["strike_type"])
    entry_price = get_spy_price()

    send_discord_embed("📥 Simulated Trade", "Paper trade executed.", color=0x2ECC71, fields=[
        {"name": "Direction", "value": result["decision"], "inline": True},
        {"name": "Strike", "value": result["strike_type"], "inline": True},
        {"name": "Entry", "value": f"${entry_price:.2f}", "inline": True},
    ])

    exit_price, gain = simulate_exit(entry_price, result["decision"])
    win = gain > 0

    log_trade(win)
    send_discord_embed("📤 Simulated Exit", f"Exit Price: ${exit_price:.2f} | P&L: {gain:+.2f}", color=0x1ABC9C if win else 0xE74C3C)

# === CLI ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Money Printer Bot")
    parser.add_argument("command", choices=["run", "weekly"])
    args = parser.parse_args()

    if args.command == "run":
        run_bot()
    elif args.command == "weekly":
        send_summary(days=7)
