import os
import csv
import datetime
import requests
import pandas as pd
import yfinance as yf
from flask import Flask
from dotenv import load_dotenv

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
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded",
} if not OFFLINE else {}

LOG_FILE = "trade_log.csv"

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
    if OFFLINE:
        data = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
        if not data.empty:
            return float(data["Close"].iloc[-1])
        raise RuntimeError("Unable to fetch SPY price in offline mode")
    url = f"{TRADIER_BASE_URL}/markets/quotes"
    params = {"symbols": "SPY"}
    r = requests.get(url, headers=HEADERS, params=params)
    return float(r.json()["quotes"]["quote"]["last"])

def get_valid_option_symbol(direction: str, strike_type: str = "ATM") -> tuple:
    if OFFLINE:
        return "SPY_FAKE_OPTION", 500.00

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
        raise RuntimeError(f"No {right.upper()} options found for SPY")

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

# === Trade Execution ===

def place_option_trade(direction: str, strike_type: str = "ATM"):
    try:
        symbol, strike = get_valid_option_symbol(direction, strike_type)
        price = get_spy_price()

        if OFFLINE:
            print(f"[DRY RUN] Would place {direction} trade for {symbol}")
            return {"status": "success", "symbol": symbol, "underlying_price": price}

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

        try:
            data = resp.json()
        except Exception:
            return {
                "status": "error",
                "error": f"Invalid JSON from Tradier. Raw response: {resp.text[:300]}"
            }

        if "order" in data:
            return {"status": "success", "symbol": symbol, "underlying_price": price}
        return {"status": "error", "error": data.get("errors", {}).get("error", "Unknown")}
    except Exception as e:
        return {"status": "error", "error": str(e)}

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
        t = i.strftime('%H:%M')
        prompt += f"{t} - O={row['Open']:.2f}, H={row['High']:.2f}, L={row['Low']:.2f}, C={row['Close']:.2f}, V={int(row['Volume'])}\n"
    prompt += "\nRespond with: CALL, PUT, or NOTHING. Then give a 1-line reason and confidence (0-100). Also suggest: ATM, ITM, or OTM strike."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a disciplined SPY options scalper."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=150,
        )
        text = response.choices[0].message.content.strip().upper()
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

# === Main Bot ===

def run_bot():
    print("📈 Downloading SPY data...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        df.columns.name = None
    if df.empty:
        msg = "❌ No SPY data retrieved."
        print(msg)
        send_discord_embed("❌ Data Fetch Error", msg, color=0xFF0000)
        return

    print("🧠 Running GPT decision logic...")
    result = gpt_trade_decision(df)
    if result["decision"] == "NOTHING" or result.get("confidence", 0) < 50:
        msg = f"⚠️ SKIPPED: Confidence {result.get('confidence', 0)}% | Reason: {result.get('reason', 'Low confidence')}"
        print(msg)
        send_discord_embed("⚠️ Trade Skipped", msg, color=0xFFA500)
        return

    print(f"✅ Decision: {result['decision']} | Strike: {result['strike_type']} | Confidence: {result['confidence']}%")
    send_discord_embed(
        "✅ Trade Decision Made",
        "GPT has chosen a trade setup.",
        color=0x2ECC71,
        fields=[
            {"name": "Direction", "value": result["decision"], "inline": True},
            {"name": "Strike Type", "value": result["strike_type"], "inline": True},
            {"name": "Confidence", "value": f"{result['confidence']}%", "inline": True},
        ],
    )

    trade = place_option_trade(result["decision"], result["strike_type"])
    if trade["status"] == "success":
        print(f"📤 ORDER PLACED: {trade['symbol']} at ${trade['underlying_price']:.2f}")
        send_discord_embed(
            "📤 Trade Executed",
            "Order successfully placed.",
            color=0x2ECC71,
            fields=[
                {"name": "Symbol", "value": trade["symbol"], "inline": False},
                {"name": "Entry Price", "value": f"${trade['underlying_price']:.2f}", "inline": True},
            ],
        )
    else:
        msg = f"❌ ORDER FAILED: {trade.get('error', 'Unknown error')}"
        print(msg)
        send_discord_embed("❌ Trade Failed", msg, color=0xFF0000)

# === CLI ===

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Money Printer bot")
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()

    if args.command == "run":
        run_bot()
