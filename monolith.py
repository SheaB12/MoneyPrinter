import os
import datetime
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

try:
    import openai
except Exception:
    openai = None

load_dotenv()

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
LOG_FILE = "trade_log.csv"

OFFLINE_ENV = os.getenv("OFFLINE", "0") == "1"
OFFLINE = OFFLINE_ENV or not all([TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY]) or openai is None
if not OFFLINE and openai is not None:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

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
        requests.post(
            DISCORD_WEBHOOK_URL,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        print(f"❌ Failed to send Discord embed: {e}")

# === Helpers ===

def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_spy_price():
    if OFFLINE:
        data = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
        return float(data["Close"].iloc[-1]) if not data.empty else 500.00
    url = "https://sandbox.tradier.com/v1/markets/quotes"
    params = {"symbols": "SPY"}
    r = requests.get(url, headers={
        "Authorization": f"Bearer {TRADIER_TOKEN}",
        "Accept": "application/json",
    }, params=params)
    return float(r.json()["quotes"]["quote"]["last"])

def get_valid_option_symbol(direction: str, strike_type: str = "ATM"):
    expiry = get_next_friday()
    current_price = get_spy_price()
    option_type = "call" if direction.lower() == "call" else "put"
    if OFFLINE:
        return f"SPY_FAKE_{option_type.upper()}", current_price

    url = "https://sandbox.tradier.com/v1/markets/options/chains"
    params = {
        "symbol": "SPY",
        "expiration": expiry,
        "greeks": "false"
    }
    headers = {
        "Authorization": f"Bearer {TRADIER_TOKEN}",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, params=params)
    options = r.json().get("options", {}).get("option", [])
    filtered = [opt for opt in options if opt["option_type"] == option_type]

    sorted_opts = sorted(filtered, key=lambda x: abs(x["strike"] - current_price))
    if not sorted_opts:
        return "INVALID_OPTION", current_price

    selected = sorted_opts[0]
    return selected["symbol"], selected["strike"]

# === GPT Strategy ===

def gpt_trade_decision(df):
    last_5 = df.tail(5)
    if last_5.empty:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM"}

    if OFFLINE or openai is None:
        diff = last_5["Close"].iloc[-1] - last_5["Open"].iloc[0]
        decision = "CALL" if diff > 0 else "PUT"
        confidence = min(int(abs(diff) * 10), 100)
        return {"decision": decision, "confidence": confidence, "strike_type": "ATM"}

    prompt = "You're a disciplined SPY options trader. Based on the last 5 minutes of candles, should we buy CALL, PUT, or NOTHING?"
    for i, row in last_5.iterrows():
        prompt += f"\n{row.name.strftime('%H:%M')} - O:{row['Open']:.2f} H:{row['High']:.2f} L:{row['Low']:.2f} C:{row['Close']:.2f}"
    prompt += "\nReturn CALL, PUT, or NOTHING. Include confidence (0-100) and whether to use ATM, ITM, or OTM."

    try:
        res = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Options scalper"}, {"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = res.choices[0].message.content.upper()
        decision = "CALL" if "CALL" in text else "PUT" if "PUT" in text else "NOTHING"
        confidence = int("".join(c for c in text.split("CONFIDENCE")[-1] if c.isdigit())[:3] or "0")
        strike_type = "ITM" if "ITM" in text else "OTM" if "OTM" in text else "ATM"
        return {"decision": decision, "confidence": confidence, "strike_type": strike_type}
    except:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM"}

# === Simulated Trade + Exit ===

def place_trade_and_exit(direction, strike_type):
    symbol, strike = get_valid_option_symbol(direction, strike_type)
    entry = get_spy_price()
    simulated_move = 0.03 if direction == "CALL" else -0.03
    exit_price = entry * (1 + simulated_move)
    profit_pct = ((exit_price - entry) / entry) * 100 if direction == "CALL" else ((entry - exit_price) / entry) * 100
    won = profit_pct >= 0

    log = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "symbol": symbol,
        "direction": direction,
        "strike_type": strike_type,
        "entry": round(entry, 2),
        "exit": round(exit_price, 2),
        "pnl_pct": round(profit_pct, 2),
        "result": "WIN" if won else "LOSS"
    }
    log_trade(log)

    send_discord_embed(
        "📤 Trade Executed (Simulated)",
        f"{'✅ WIN' if won else '❌ LOSS'} | {symbol} | {direction} | {strike_type}",
        color=0x2ECC71 if won else 0xFF0000,
        fields=[
            {"name": "Entry", "value": f"${log['entry']}", "inline": True},
            {"name": "Exit", "value": f"${log['exit']}", "inline": True},
            {"name": "PnL %", "value": f"{log['pnl_pct']}%", "inline": True},
        ]
    )

# === Trade Log ===

def log_trade(trade: dict):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        writer = pd.DataFrame([trade])
        writer.to_csv(f, header=not file_exists, index=False)

# === Summary Reporting ===

def send_weekly_summary():
    if not os.path.isfile(LOG_FILE):
        print("⚠️ No trade log found.")
        return

    df = pd.read_csv(LOG_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    one_week_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    df = df[df["timestamp"] > one_week_ago]

    if df.empty:
        send_discord_embed("📊 Weekly Summary", "No trades this week.", color=0x5865F2)
        return

    wins = df[df["result"] == "WIN"].shape[0]
    losses = df[df["result"] == "LOSS"].shape[0]
    total = wins + losses
    win_rate = (wins / total) * 100 if total else 0
    avg_pnl = df["pnl_pct"].mean()

    send_discord_embed(
        "📊 Weekly Performance Summary",
        f"Here's your performance over the last 7 days.",
        color=0x0099FF,
        fields=[
            {"name": "Total Trades", "value": str(total), "inline": True},
            {"name": "Win Rate", "value": f"{win_rate:.2f}%", "inline": True},
            {"name": "Avg PnL %", "value": f"{avg_pnl:.2f}%", "inline": True},
        ]
    )

# === Main Bot ===

def run_bot():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        send_discord_embed("❌ Data Error", "Could not fetch SPY data.", color=0xFF0000)
        return

    print("🧠 GPT making decision...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        msg = f"⚠️ No trade taken | Confidence {result['confidence']}%"
        print(msg)
        send_discord_embed("⚠️ Trade Skipped", msg, color=0xFFA500)
        return

    print(f"✅ Trading {result['decision']} | {result['strike_type']}")
    place_trade_and_exit(result["decision"], result["strike_type"])

# === CLI ===

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "summary"])
    args = parser.parse_args()

    if args.command == "run":
        run_bot()
    elif args.command == "summary":
        send_weekly_summary()
