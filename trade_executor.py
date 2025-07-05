import os
import time
import json
import requests
from datetime import datetime, timedelta
from logger import log_trade_to_sheets
from discord_alerts import send_discord_alert

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
IS_SANDBOX = True

HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json"
}

BASE_URL = "https://sandbox.tradier.com/v1" if IS_SANDBOX else "https://api.tradier.com/v1"
TRADE_STATE_FILE = "trade_state.json"


def already_traded_today():
    if not os.path.exists(TRADE_STATE_FILE):
        return False
    with open(TRADE_STATE_FILE, "r") as f:
        state = json.load(f)
    return state.get("last_trade_date") == datetime.now().strftime("%Y-%m-%d")


def mark_trade_complete():
    with open(TRADE_STATE_FILE, "w") as f:
        json.dump({"last_trade_date": datetime.now().strftime("%Y-%m-%d")}, f)


def get_next_expiration_date():
    url = f"{BASE_URL}/markets/options/expirations"
    params = {"symbol": "SPY"}
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    data = response.json()
    expirations = data.get("expirations", {}).get("date", [])
    if not expirations:
        raise Exception("No expirations found for SPY")
    return expirations[0]  # Soonest valid expiration


def find_option_symbol_from_chain(direction):
    expiration = get_next_expiration_date()
    url = f"{BASE_URL}/markets/options/chains"
    params = {
        "symbol": "SPY",
        "expiration": expiration,
        "greeks": "false"
    }
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        options = data.get("options", {}).get("option", [])

        if not options:
            raise Exception("No option chains returned")

        direction = direction.upper()
        filtered = [o for o in options if o["option_type"] == direction]

        if not filtered:
            raise Exception(f"No {direction} options found for expiration {expiration}")

        best_option = filtered[0]
        print(f"Selected {direction} option: {best_option['symbol']}")
        return best_option["symbol"]
    except Exception as e:
        print(f"Error fetching option chain: {e}")
        raise


def place_order(option_symbol, quantity):
    url = f"{BASE_URL}/accounts/{ACCOUNT_ID}/orders"
    payload = {
        "class": "option",
        "symbol": option_symbol,
        "side": "buy_to_open",
        "quantity": quantity,
        "type": "market",
        "duration": "day"
    }
    try:
        response = requests.post(url, headers=HEADERS, data=payload)
        print("Raw response:", response.text)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP Error: {http_err}")
        raise
    except requests.exceptions.RequestException as req_err:
        print(f"Request Error: {req_err}")
        raise
    except json.JSONDecodeError:
        print("Tradier API did not return valid JSON.")
        raise


def get_option_price(symbol):
    url = f"{BASE_URL}/markets/quotes"
    params = {"symbols": symbol}
    r = requests.get(url, headers=HEADERS, params=params)
    data = r.json()
    return data['quotes']['quote']['last']


def monitor_trade(symbol, entry_price):
    targets = {
        "TP1": entry_price * 1.50,
        "TP2": entry_price * 1.75,
        "SL": entry_price * 0.70
    }

    filled_tp1 = False
    filled_tp2 = False
    stop_hit = False

    end_time = datetime.now().replace(hour=11, minute=0, second=0)
    if datetime.now() > end_time:
        end_time = datetime.now() + timedelta(minutes=15)

    while datetime.now() < end_time:
        try:
            price = get_option_price(symbol)
            print(f"[{datetime.now()}] Price: {price:.2f}")
            if not filled_tp1 and price >= targets["TP1"]:
                print("TP1 hit. Selling 1 contract.")
                filled_tp1 = True
            elif not filled_tp2 and price >= targets["TP2"]:
                print("TP2 hit. Selling 1 contract.")
                filled_tp2 = True
            elif price <= targets["SL"]:
                print("Stop loss hit. Exit all.")
                stop_hit = True
                break

            if filled_tp1 and filled_tp2:
                break

            time.sleep(15)
        except Exception as e:
            print("Error fetching price:", e)
            time.sleep(15)

    contracts_closed = int(filled_tp1) + int(filled_tp2)
    remaining = 2 - contracts_closed
    final_price = get_option_price(symbol)
    avg_exit = ((filled_tp1 * targets["TP1"]) + (filled_tp2 * targets["TP2"]) + (remaining * final_price)) / 2
    percent_gain = ((avg_exit - entry_price) / entry_price) * 100

    return {
        "exit_price": avg_exit,
        "stop_triggered": stop_hit,
        "target_hit": filled_tp1 or filled_tp2,
        "percent_gain": round(percent_gain, 2)
    }


def execute_trade():
    if already_traded_today():
        print("Trade already executed today. Exiting.")
        return

    direction = "CALL"
    option_symbol = find_option_symbol_from_chain(direction)

    print(f"Placing order for {option_symbol}")
    order_result = place_order(option_symbol, 2)
    print("Order result:", order_result)

    time.sleep(5)
    entry_price = get_option_price(option_symbol)
    print(f"Entry price: {entry_price:.2f}")

    send_discord_alert(
        title="📈 Trade Executed",
        description=f"Placed SPY {direction} – {option_symbol} (2 contracts)\nEntry: ${entry_price:.2f}"
    )

    result = monitor_trade(option_symbol, entry_price)

    log_trade_to_sheets({
        "trade_id": f"{option_symbol}_{datetime.now().strftime('%Y%m%d')}",
        "direction": direction,
        "entry_price": entry_price,
        "exit_price": result["exit_price"],
        "percent_gain": result["percent_gain"],
        "stop_triggered": result["stop_triggered"],
        "target_hit": result["target_hit"],
        "model_confidence": None,
        "signal_reason": "Time-based entry (sandbox test)"
    })

    send_discord_alert(
        title="✅ Trade Closed",
        description=f"Exit: ${result['exit_price']:.2f}\n"
                    f"PnL: {result['percent_gain']}%\n"
                    f"Target Hit: {result['target_hit']}\n"
                    f"Stop Triggered: {result['stop_triggered']}"
    )

    mark_trade_complete()
    print("Trade execution complete and logged.")


if __name__ == "__main__":
    execute_trade()
