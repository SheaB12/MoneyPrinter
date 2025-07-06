import os
import time
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from logger import log_trade_to_sheets
from discord_alerts import send_discord_alert
from gpt_decider import gpt_decision

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID")
IS_SANDBOX = False  # Live paper trading

HEADERS = {
    "Authorization": f"Bearer {TRADIER_TOKEN}",
    "Accept": "application/json"
}

BASE_URL = "https://sandbox.tradier.com/v1" if IS_SANDBOX else "https://api.tradier.com/v1"
TRADE_STATE_FILE = "trade_state.json"
MIN_CONFIDENCE = 60


def already_traded_today():
    if not os.path.exists(TRADE_STATE_FILE):
        return False
    with open(TRADE_STATE_FILE, "r") as f:
        state = json.load(f)
    return state.get("last_trade_date") == datetime.now().strftime("%Y-%m-%d")


def mark_trade_complete():
    with open(TRADE_STATE_FILE, "w") as f:
        json.dump({"last_trade_date": datetime.now().strftime("%Y-%m-%d")}, f)


def fetch_spy_candles():
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=30)
    url = f"{BASE_URL}/markets/timesales"
    params = {
        "symbol": "SPY",
        "interval": "1min",
        "start": start_time.strftime("%Y-%m-%dT%H:%M"),
        "end": end_time.strftime("%Y-%m-%dT%H:%M"),
        "session_filter": "open"
    }
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json().get("series", {}).get("data", [])
    df = pd.DataFrame(data)
    return df


def find_option_symbol_from_chain(direction):
    url_exp = f"{BASE_URL}/markets/options/expirations"
    params = {"symbol": "SPY"}
    response = requests.get(url_exp, headers=HEADERS, params=params)
    response.raise_for_status()
    expirations = response.json().get("expirations", {}).get("date", [])

    direction = direction.upper()

    for expiration in expirations:
        try:
            url_chain = f"{BASE_URL}/markets/options/chains"
            chain_params = {
                "symbol": "SPY",
                "expiration": expiration,
                "greeks": "false"
            }
            resp = requests.get(url_chain, headers=HEADERS, params=chain_params)
            resp.raise_for_status()
            options = resp.json().get("options", {}).get("option", [])

            filtered = [o for o in options if o["option_type"] == direction and o["strike"] >= 300 and o["last"] > 0]
            if filtered:
                best_option = filtered[0]
                print(f"Selected {direction} option: {best_option['symbol']} (exp: {expiration})")
                return best_option["symbol"]
        except Exception as e:
            print(f"Skipping expiration {expiration} due to error: {e}")
            continue

    raise Exception(f"No valid {direction} options found for any expiration.")


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
    except Exception as e:
        print(f"Order placement failed: {e}")
        raise


def get_option_price(symbol):
    url = f"{BASE_URL}/markets/quotes"
    params = {"symbols": symbol}
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    data = r.json()
    return data['quotes']['quote']['last']


def monitor_trade(symbol, entry_price, stop_pct, target_pct):
    tp1 = entry_price * (1 + target_pct / 100)
    sl = entry_price * (1 - stop_pct / 100)

    end_time = datetime.now().replace(hour=11, minute=0, second=0)
    if datetime.now() > end_time:
        end_time = datetime.now() + timedelta(minutes=15)

    while datetime.now() < end_time:
        try:
            price = get_option_price(symbol)
            print(f"[{datetime.now()}] Price: {price:.2f}")
            if price >= tp1:
                print("Target hit. Exiting.")
                return price, False, True
            elif price <= sl:
                print("Stop loss hit. Exiting.")
                return price, True, False
            time.sleep(15)
        except Exception as e:
            print(f"Error during monitoring: {e}")
            time.sleep(15)

    final = get_option_price(symbol)
    return final, False, False


def execute_trade():
    if already_traded_today():
        print("Trade already executed today.")
        return

    df = fetch_spy_candles()
    gpt = gpt_decision(df)

    if not gpt or gpt.get("decision") not in ["call", "put"]:
        print("GPT said to skip this trade.")
        return

    if gpt["confidence"] < MIN_CONFIDENCE:
        print(f"GPT confidence too low ({gpt['confidence']}%). Skipping trade.")
        return

    direction = gpt["decision"].upper()
    stop_pct = gpt.get("stop_loss_pct", 30)
    target_pct = gpt.get("target_pct", 50)

    option_symbol = find_option_symbol_from_chain(direction)
    print(f"Placing order for {option_symbol}")
    place_order(option_symbol, 2)

    time.sleep(5)
    entry = get_option_price(option_symbol)

    send_discord_alert(
        title="🤖 GPT Trade Triggered",
        description=f"**Direction**: {direction}\n"
                    f"**Option**: {option_symbol}\n"
                    f"**Confidence**: {gpt['confidence']}%\n"
                    f"**Reason**: {gpt['reason']}\n"
                    f"**Entry**: ${entry:.2f}\n"
                    f"**SL**: {stop_pct}% | **TP**: {target_pct}%"
    )

    exit_price, stop_hit, target_hit = monitor_trade(option_symbol, entry, stop_pct, target_pct)
    pnl = ((exit_price - entry) / entry) * 100

    log_trade_to_sheets({
        "trade_id": f"{option_symbol}_{datetime.now().strftime('%Y%m%d')}",
        "direction": direction,
        "entry_price": entry,
        "exit_price": exit_price,
        "percent_gain": round(pnl, 2),
        "stop_triggered": stop_hit,
        "target_hit": target_hit,
        "model_confidence": gpt['confidence'],
        "signal_reason": gpt['reason']
    })

    send_discord_alert(
        title="✅ Trade Closed",
        description=f"Exit: ${exit_price:.2f}\n"
                    f"PnL: {round(pnl, 2)}%\n"
                    f"Target Hit: {target_hit}\n"
                    f"Stop Triggered: {stop_hit}"
    )

    mark_trade_complete()


if __name__ == "__main__":
    execute_trade()
