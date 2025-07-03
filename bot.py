import os
import time
import yfinance as yf
import requests
import datetime
from dotenv import load_dotenv
from config import TRADIER_TOKEN, ACCOUNT_ID, OPENAI_API_KEY
import openai
import pandas as pd

# Load environment variables
load_dotenv()
openai.api_key = OPENAI_API_KEY

TICKER = "SPY"
MODE = os.getenv("MODE", "paper")
TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"  # Change to live for real trades

HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

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
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    return float(data["quotes"]["quote"]["last"])

def get_option_symbol(direction, strike):
    expiry = get_next_friday().replace("-", "")
    strike_formatted = f"{int(strike * 1000):08d}"
    right = "C" if direction.lower() == "call" else "P"
    return f"SPY{expiry}{right}{strike_formatted}"

def validate_option_symbol(symbol):
    """Check if the given option symbol exists in Tradier's sandbox environment."""
    url = f"{TRADIER_BASE_URL}/markets/options/lookup"
    params = {"symbol": symbol}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        print("⚠️ Lookup failed with status:", response.status_code)
        return False

    try:
        data = response.json()
        if "options" in data and data["options"]:
            return True
    except ValueError:
        print("⚠️ Invalid JSON from symbol validation.")
    return False

def place_option_trade(direction, strike_type="ATM"):
    try:
        spy_price = get_spy_price()

        if strike_type == "ATM":
            strike = round(spy_price)
        elif strike_type == "ITM":
            strike = round(spy_price - 5)
        elif strike_type == "OTM":
            strike = round(spy_price + 5)
        else:
            strike = round(spy_price)

        option_symbol = get_option_symbol(direction, strike)

        print(f"🧾 Checking option symbol: {option_symbol}")
        if not validate_option_symbol(option_symbol):
            return {
                "status": "error",
                "error": f"Invalid or unavailable option symbol: {option_symbol} (not found in sandbox)"
            }

        print(f"\n📤 Submitting order for: {option_symbol}")
        payload = {
            "class": "option",
            "symbol": option_symbol,
            "side": "buy_to_open",
            "quantity": 1,
            "type": "market",
            "duration": "day"
        }

        url = f"{TRADIER_BASE_URL}/accounts/{ACCOUNT_ID}/orders"
        print("📤 Payload:", payload)
        print("📡 Request URL:", url)
        print("📡 Headers:", HEADERS)

        response = requests.post(url, headers=HEADERS, data=payload)
        print("📡 Tradier response text:", response.text)

        try:
            data = response.json()
        except ValueError:
            return {
                "status": "error",
                "error": f"Non-JSON response from Tradier: {response.text.strip()}"
            }

        if "order" in data:
            return {
                "status": "success",
                "symbol": option_symbol,
                "strike": strike,
                "underlying_price": spy_price,
                "strike_type": strike_type,
                "order_id": data["order"]["id"]
            }
        else:
            return {
                "status": "error",
                "symbol": option_symbol,
                "strike": strike,
                "strike_type": strike_type,
                "error": data.get("errors", {}).get("error", "Unknown error")
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# === GPT Decision Logic ===

def gpt_trade_decision(df: pd.DataFrame):
    try:
        last_5 = df.tail(5)
        if last_5.empty:
            return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": "Not enough data"}

        prompt = "You're a disciplined SPY options trader. Based on the last 5 minutes of 1-minute candles, should we buy a CALL, PUT, or NOTHING?\n"

        for i, row in last_5.iterrows():
            try:
                t = i.strftime('%H:%M')
                o = float(row['Open'].iloc[0]) if isinstance(row['Open'], pd.Series) else float(row['Open'])
                h = float(row['High'].iloc[0]) if isinstance(row['High'], pd.Series) else float(row['High'])
                l = float(row['Low'].iloc[0]) if isinstance(row['Low'], pd.Series) else float(row['Low'])
                c = float(row['Close'].iloc[0]) if isinstance(row['Close'], pd.Series) else float(row['Close'])
                v = int(row['Volume'].iloc[0]) if isinstance(row['Volume'], pd.Series) else int(row['Volume'])

                prompt += f"{t} - O={o:.2f}, H={h:.2f}, L={l:.2f}, C={c:.2f}, V={v}\n"
            except:
                continue

        prompt += "\nRespond with: CALL, PUT, or NOTHING. Then give a 1-line reason and confidence (0–100). Also suggest: ATM, ITM, or OTM strike."

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a disciplined SPY options scalper."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )

        text = response.choices[0].message["content"].strip().upper()
        print("🧠 GPT Output:\n", text)

        decision = "NOTHING"
        confidence = 0
        strike_type = "ATM"

        if "CALL" in text: decision = "CALL"
        elif "PUT" in text: decision = "PUT"

        if "CONFIDENCE" in text:
            digits = "".join(c for c in text.split("CONFIDENCE")[1] if c.isdigit())
            confidence = int(digits[:3]) if digits else 0

        if "ITM" in text or "IN-THE-MONEY" in text:
            strike_type = "ITM"
        elif "OTM" in text or "OUT-OF-THE-MONEY" in text:
            strike_type = "OTM"

        return {
            "decision": decision,
            "confidence": confidence,
            "strike_type": strike_type,
            "raw": text
        }

    except Exception as e:
        print(f"OpenAI Error: {e}")
        return {"decision": "NOTHING", "confidence": 0, "strike_type": "ATM", "reason": str(e)}

# === Main Bot Logic ===

def run_bot():
    print("📈 Downloading SPY data...")
    df = yf.download("SPY", interval="1m", period="1d", progress=False, auto_adjust=True)

    if df.empty:
        print("❌ No SPY data retrieved.")
        return

    print("🧠 Running GPT decision logic...")
    result = gpt_trade_decision(df)

    if result["decision"] == "NOTHING" or result["confidence"] < 50:
        print(f"⚠️ SKIP: Confidence {result.get('confidence', 0)}% | Reason: {result.get('reason', 'Low confidence')}")
        return

    print(f"✅ Decision: {result['decision']} | Strike: {result['strike_type']} | Confidence: {result['confidence']}%")

    trade = place_option_trade(result["decision"], result["strike_type"])

    if trade["status"] == "success":
        print(f"📤 ORDER PLACED: {trade['symbol']} ({trade['strike_type']}) at ${trade['underlying_price']:.2f}")
    else:
        print(f"❌ ORDER FAILED: {trade.get('error', 'Unknown error')}")

if __name__ == "__main__":
    run_bot()
