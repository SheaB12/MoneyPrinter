import os
import json
import datetime
import requests
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from collections import defaultdict

try:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception:
    client = None

# === Configuration ===
load_dotenv()
TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

OFFLINE = not all([TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY]) or client is None

TRADES_LOG = "simulated_trades.json"
TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
} if not OFFLINE else {}

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
        print(f"❌ Discord error: {e}")

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

def get_valid_option_symbol(direction, strike_type="ATM"):
    expiry = get_next_friday()
    url = f"{TRADIER_BASE_URL}/markets/options/chains"
    params = {"symbol": "SPY", "expiration": expiry, "greeks": "false"}
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    options = data.get("options", {}).get("option", [])
    if not options:
        raise RuntimeError("No options returned from Tradier")
    current_price = get_spy_price()
    right = "call" if direction.lower() == "call" else "put"
    filtered = [opt for opt in options if opt["option_type"] == right]
    sorted_opts = sorted(filtered, key=lambda x: abs(x["strike"] - current_price))
    if strike_type == "ATM":
        selected = sorted_opts[0]
    elif strike_type == "ITM":
        selected = next((o for o in sorted_opts if (o["strike"] < current_price if right == "call" else o["strike"] > current_price)), sorted_opts[0])
    elif strike_type == "OTM":
        selected = next((o for o in sorted_opts if (o["strike"] > current_price if right == "call" else o["strike"] < current_price)), sorted_opts[0])
    else:
        selected = sorted_opts[0]
    return selected["symbol"], selected["strike"]

# === Trade Execution ===

def simulate_exit(entry_price, direction):
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        return 0.0
    post_entry = df.iloc[-20:]
    exit_price = post_entry["Close"].iloc[-1]
    move_pct = (exit_price - entry_price) / entry_price * 100
    return round(move_pct if direction == "CALL" else -move_pct, 2)

def place_option_trade(direction, strike_type="ATM"):
    try:
        symbol, strike = get_valid_option_symbol(direction, strike_type)
        entry_price = get_spy_price()
        percent_return = simulate_exit(entry_price, direction)
        result = {
            "symbol": symbol,
            "entry_price": entry_price,
            "return": percent_return,
            "timestamp": str(datetime.datetime.now()),
            "direction": direction
        }
        log_trade(result)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# === GPT Logic ===

def gpt_trade_decision(df):
    last_5 = df.tail(5)
    if last_5.empty:
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": "No data"}
    diff = last_5["Close"].iloc[-1] - last_5["Open"].iloc[0]
    if OFFLINE or client is None:
        if abs(diff) < 0.05:
            return {"decision": "NOTHING", "confidence": 50, "strike_type": "ATM", "reason": "Low volatility"}
        direction = "CALL" if diff > 0 else "PUT"
        return {"decision": direction, "confidence": 60, "strike_type": "ATM"}
    prompt = "You're a disciplined SPY options trader. Based on the last 5 minutes of 1-min candles, should we buy CALL, PUT, or NOTHING?\n"
    for i, row in last_5.iterrows():
        time_str = i.strftime('%H:%M')
        prompt += f"\n{time_str} - O:{row['Open']:.2f} H:{row['High']:.2f} L:{row['Low']:.2f} C:{row['Close']:.2f}"
    prompt += "\nRespond with CALL, PUT, or NOTHING. Also give CONFIDENCE and ATM/ITM/OTM."
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You're a disciplined SPY options scalper."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=150,
    )
    content = response.choices[0].message.content.upper()
    decision = "CALL" if "CALL" in content else "PUT" if "PUT" in content else "NOTHING"
    confidence = int("".join([c for c in content.split("CONFIDENCE")[-1] if c.isdigit()][:3])) if "CONFIDENCE" in content else 60
    strike_type = "ITM" if "ITM" in content else "OTM" if "OTM" in content else "ATM"
    return {"decision": decision, "confidence": confidence, "strike_type": strike_type}

# === Trade Logging ===

def log_trade(data):
    trades = []
    if os.path.exists(TRADES_LOG):
        with open(TRADES_LOG, "r") as f:
            trades = json.load(f)
    trades.append(data)
    with open(TRADES_LOG, "w") as f:
        json.dump(trades, f, indent=2)

def summarize_performance():
    if not os.path.exists(TRADES_LOG):
        return None
    with open(TRADES_LOG, "r") as f:
        trades = json.load(f)
    win = sum(1 for t in trades if t["return"] > 0)
    loss = sum(1 for t in trades if t["return"] <= 0)
    avg_return = sum(t["return"] for t in trades) / len(trades) if trades else 0
    return {
        "total": len(trades),
        "wins": win,
        "losses": loss,
        "avg_return": round(avg_return, 2)
    }

# === Main Bot ===

def run_bot(weekly=False):
    print("📈 Fetching SPY...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if df.empty:
        send_discord_embed("❌ No SPY Data", "Unable to fetch SPY data.", color=0xFF0000)
        return
    print("🧠 GPT making decision...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        send_discord_embed("⚠️ No Trade", f"Confidence {result['confidence']}% - Reason: {result.get('reason', 'N/A')}", color=0xAAAA00)
        return
    trade = place_option_trade(result["decision"], result["strike_type"])
    if trade["status"] == "success":
        r = trade["data"]
        print(f"📤 PAPER TRADE: {r['symbol']} | Entry: ${r['entry_price']:.2f} | Return: {r['return']}%")
        send_discord_embed(
            "📤 Paper Trade Executed",
            "Simulated trade completed.",
            color=0x2ECC71,
            fields=[
                {"name": "Symbol", "value": r["symbol"], "inline": True},
                {"name": "Return", "value": f"{r['return']}%", "inline": True},
            ]
        )
    else:
        send_discord_embed("❌ Trade Failed", trade["error"], color=0xFF0000)

    # Weekly summary (Sunday)
    if weekly:
        stats = summarize_performance()
        if stats:
            send_discord_embed(
                "📊 Weekly Summary",
                "Simulated performance this week:",
                color=0x3498DB,
                fields=[
                    {"name": "Total Trades", "value": stats["total"], "inline": True},
                    {"name": "Wins", "value": stats["wins"], "inline": True},
                    {"name": "Losses", "value": stats["losses"], "inline": True},
                    {"name": "Avg Return", "value": f"{stats['avg_return']}%", "inline": True},
                ]
            )

# === CLI ===

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--weekly", action="store_true", help="Send weekly summary")
    args = parser.parse_args()
    if args.command == "run":
        run_bot(weekly=args.weekly)
