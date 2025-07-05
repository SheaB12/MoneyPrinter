import os
import datetime
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from collections import deque

try:
    import openai
except Exception:
    openai = None

# === Configuration ===
load_dotenv()
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OFFLINE_ENV = os.getenv("OFFLINE", "0") == "1"
OFFLINE = OFFLINE_ENV or not all([TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY]) or openai is None
if not OFFLINE and openai is not None:
    openai.api_key = OPENAI_API_KEY

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
} if not OFFLINE else {}

TRADE_LOG = "paper_trade_log.csv"
MAX_HOLD_MINUTES = 30
STOP_LOSS_PCT = -0.30
TAKE_PROFIT_PCT = 0.50

# === Discord Alerts ===

def send_discord_embed(title: str, description: str, color: int = 0x5865F2, fields: list = None):
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

# === Option Helpers ===

def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def get_spy_price():
    data = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if not data.empty:
        return float(data["Close"].iloc[-1])
    raise RuntimeError("Unable to fetch SPY price")

def get_valid_option_symbol(direction: str, strike_type: str = "ATM") -> tuple:
    expiry = get_next_friday()
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    params = {
        "symbol": "SPY",
        "expiration": expiry,
        "greeks": "false"
    }
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        raise RuntimeError("Failed to fetch options chain")

    data = response.json()
    options = data.get("options", {}).get("option", [])
    if not options:
        raise RuntimeError("No options returned from Tradier")

    current_price = get_spy_price()
    right = "call" if direction.lower() == "call" else "put"
    filtered = [opt for opt in options if opt["option_type"] == right]

    if not filtered:
        raise RuntimeError(f"No {right.upper()} options found")

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
    for i in last_5.index:
        row = last_5.loc[i]
        time_str = i.strftime('%H:%M')
        prompt += f"\n{time_str} - O:{row['Open']:.2f} H:{row['High']:.2f} L:{row['Low']:.2f} C:{row['Close']:.2f}"

    prompt += "\nRespond with: CALL, PUT, or NOTHING. Then give a 1-line reason and confidence (0-100). Also suggest: ATM, ITM, or OTM strike."
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
        text = response["choices"][0]["message"]["content"].strip().upper()
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

# === Trade Simulation ===

def simulate_exit(entry_price: float, direction: str, df: pd.DataFrame) -> float:
    start_index = df.index[-1]
    forward_df = df[df.index > start_index]
    max_minutes = min(MAX_HOLD_MINUTES, len(forward_df))

    for i in range(max_minutes):
        price = forward_df.iloc[i]["Close"]
        change = (price - entry_price) / entry_price if direction == "CALL" else (entry_price - price) / entry_price

        if change >= TAKE_PROFIT_PCT:
            return round(price, 2)
        elif change <= STOP_LOSS_PCT:
            return round(price, 2)

    return round(forward_df.iloc[max_minutes - 1]["Close"], 2)

def log_trade(symbol, entry, exit, direction):
    pnl = round(exit - entry, 2) if direction == "CALL" else round(entry - exit, 2)
    status = "WIN" if pnl > 0 else "LOSS"
    with open(TRADE_LOG, "a") as f:
        f.write(f"{datetime.datetime.now()},{symbol},{entry},{exit},{pnl},{status}\n")
    return pnl, status

# === Bot Run ===

def run_bot():
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        df.columns.name = None
    if df.empty:
        send_discord_embed("❌ Data Error", "Failed to download SPY data.", color=0xFF0000)
        return

    print("🧠 GPT making decision...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        print(f"⚠️ No Trade\nConfidence {result['confidence']}% - Reason: {result.get('reason', 'Low confidence')}")
        return

    direction = result["decision"]
    strike_type = result["strike_type"]
    symbol, _ = get_valid_option_symbol(direction, strike_type)
    entry_price = get_spy_price()
    exit_price = simulate_exit(entry_price, direction, df)
    pnl, status = log_trade(symbol, entry_price, exit_price, direction)

    send_discord_embed(
        f"📤 Simulated Trade - {status}",
        f"{direction} trade on {symbol}",
        color=0x2ECC71 if status == "WIN" else 0xE74C3C,
        fields=[
            {"name": "Entry", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "Exit", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "PnL", "value": f"${pnl:.2f}", "inline": True},
        ]
    )

def send_weekly_summary():
    if not os.path.exists(TRADE_LOG):
        print("📭 No trades to summarize.")
        return

    df = pd.read_csv(TRADE_LOG, header=None,
                     names=["timestamp", "symbol", "entry", "exit", "pnl", "status"],
                     parse_dates=["timestamp"])
    week = datetime.datetime.now().isocalendar().week
    weekly_df = df[df["timestamp"].dt.isocalendar().week == week]
    wins = (weekly_df["status"] == "WIN").sum()
    losses = (weekly_df["status"] == "LOSS").sum()
    total = wins + losses
    net_pnl = weekly_df["pnl"].sum()

    send_discord_embed(
        "📊 Weekly Performance Summary",
        f"Total Trades: {total}",
        color=0x3498DB,
        fields=[
            {"name": "Wins", "value": f"{wins}", "inline": True},
            {"name": "Losses", "value": f"{losses}", "inline": True},
            {"name": "Net PnL", "value": f"${net_pnl:.2f}", "inline": True},
        ]
    )

# === CLI ===

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Money Printer bot")
    parser.add_argument("command", choices=["run", "weekly"])
    args = parser.parse_args()

    if args.command == "run":
        run_bot()
    elif args.command == "weekly":
        send_weekly_summary()
