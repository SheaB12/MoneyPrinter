import datetime
import requests
from config import TRADIER_TOKEN
from math import floor, ceil

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"
HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json"
}

def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

def validate_option_symbol(symbol):
    url = f"{TRADIER_BASE_URL}/markets/options/lookup"
    params = {"symbol": symbol}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code != 200:
        return False
    try:
        data = response.json()
        return "options" in data and len(data["options"]) > 0
    except:
        return False

def build_option_symbol(direction, strike, expiry):
    strike_formatted = f"{int(strike * 1000):08d}"
    right = "C" if direction == "call" else "P"
    return f"SPY{expiry.replace('-', '')}{right}{strike_formatted}"

def test_strikes():
    expiry = get_next_friday()
    print(f"📅 Testing strikes for expiration: {expiry}")
    
    try:
        # Get live SPY price from sandbox (or just hardcode for now)
        spy_price = 545  # You can manually set or pull from sandbox
    except:
        spy_price = 545

    min_strike = floor(spy_price) - 15
    max_strike = ceil(spy_price) + 15

    for direction in ["call", "put"]:
        print(f"\n🔍 Testing {direction.upper()}S:")
        for strike in range(min_strike, max_strike + 1, 5):  # Every $5 increment
            symbol = build_option_symbol(direction, strike, expiry)
            valid = validate_option_symbol(symbol)
            if valid:
                print(f"✅ VALID: {symbol}")
            else:
                print(f"❌ INVALID: {symbol}")

if __name__ == "__main__":
    test_strikes()
