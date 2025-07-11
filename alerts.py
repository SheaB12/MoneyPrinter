import requests
import os
from datetime import datetime
from logger import get_daily_summary

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message: str, color: int = 0x3498db, title="📊 MoneyPrinter Alert"):
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL is not set.")
        return

    data = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=data)
    if response.status_code != 204:
        print(f"❌ Discord alert failed: {response.status_code} - {response.text}")
    else:
        print("✅ Discord alert sent.")


def send_trade_alert(action: str, confidence: int, reason: str, strike_type: str):
    color = 0x2ecc71 if action in ['call', 'put'] else 0xe67e22
    message = (
        f"**Action**: `{action.upper()}`\n"
        f"**Confidence**: `{confidence}%`\n"
        f"**Strike Type**: `{strike_type}` (based on historical profitability)\n"
        f"**Expiration**: `End of Day`\n"
        f"**Reason**: {reason}"
    )
    send_discord_alert(message, color, title="🤖 GPT Trade Decision")


def send_profit_alert(profit_pct: float, win: bool):
    color = 0x2ecc71 if win else 0xe74c3c
    message = (
        f"**Predicted Trade Outcome**\n"
        f"Estimated Profit: `{profit_pct:.2f}%`\n"
        f"Result: `{'WIN' if win else 'LOSS'}`\n"
        f"Based on: Entry vs. High (CALL) or Entry vs. Low (PUT)"
    )
    send_discord_alert(message, color, title="💰 GPT Profit Estimate")


def send_threshold_change_alert(old: float, new: float):
    color = 0xf1c40f
    message = f"🔁 Dynamic confidence threshold changed from `{old}%` → `{new}%`"
    send_discord_alert(message, color, title="⚙️ Threshold Update")


def send_daily_summary():
    try:
        summary = get_daily_summary()
        if not summary:
            print("⚠️ No daily summary available to send.")
            return
        send_discord_alert(summary, color=0x7289DA, title="📅 Daily Performance Summary")
    except Exception as e:
        print(f"❌ Error sending daily summary: {e}")
