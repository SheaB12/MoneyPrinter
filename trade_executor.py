import requests
import datetime
from config import TRADIER_TOKEN, ACCOUNT_ID

TRADIER_BASE_URL = "https://sandbox.tradier.com/v1"

HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

def get_next_friday():
    today = datetime.date.today()
    days_ahead = 4 - today.weekday()  # Friday = 4
    if days_ahead < 0:
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
    strike_formatted = f"{int(strike*1000):08d}"  # Format to 8 digits
    right = "C" if direction.lower() == "call" else "P"
    return f"SPY{expiry}{right}{strike_formatted}"

def place_option_trade(direction):
    try:
        spy_price = get_spy_price()
        strike = round(spy_price)  # ATM
        symbol = get_option_symbol(direction, strike)

        payload = {
            "class": "option",
            "symbol": symbol,
            "side": "buy_to_open",
            "quantity": 1,
            "type": "market",
            "duration": "day"
        }

        url = f"{TRADIER_BASE_URL}/accounts/{ACCOUNT_ID}/orders"
        response = requests.post(url, headers=HEADERS, data=payload)
        data = response.json()

        if "order" in data:
            order = data["order"]
            return {
                "status": "success",
                "symbol": symbol,
                "price": spy_price
            }
        else:
            return {
                "status": "error",
                "error": data.get("errors", {}).get("error", "Unknown error")
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
