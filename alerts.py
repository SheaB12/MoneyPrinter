import requests
import os
from datetime import datetime
from logger import get_daily_summary

def send_discord_alert(message: str, color: int = 0x3498db, title: str = "📊 MoneyPrinter Alert"):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("❌ DISCORD_WEBHOOK_URL is not set.")
        return

    embed = {
        "title": title,
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat()
    }

    data = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            print(f"❌ Discord alert failed: {response.status_code} - {response.text}")
        else:
            print("✅ Discord alert sent.")
    except Exception as e:
        print(f"❌ Exception sending Discord alert: {e}")


def send_trade_alert(action: str, confidence: int, reason: str):
    try:
        color = 0x2ecc71 if action.lower() in ['call', 'put'] else 0xe74c3c
        message = f"**Action**: `{action.upper()}`\n**Confidence**: `{confidence}%`\n**Reason**: {reason}"
        send_discord_alert(message, color, title="🤖 GPT Trade Decision")
    except Exception as e:
        print(f"❌ Error in send_trade_alert: {e}")


def send_trade_result_alert(symbol: str, pnl: float, win: bool):
    try:
        color = 0x2ecc71 if win else 0xe74c3c
        result_text = "✅ WIN" if win else "❌ LOSS"
        message = f"**Symbol**: `{symbol}`\n**PnL**: `{pnl:.2f}%`\n**Result**: {result_text}"
        send_discord_alert(message, color, title="📈 Trade Result")
    except Exception as e:
        print(f"❌ Error in send_trade_result_alert: {e}")


def send_threshold_change_alert(old: float, new: float):
    try:
        color = 0xf1c40f
        message = f"🔁 Dynamic confidence threshold changed from `{old}%` → `{new}%`"
        send_discord_alert(message, color, title="⚙️ Threshold Update")
    except Exception as e:
        print(f"❌ Error in send_threshold_change_alert: {e}")


def send_daily_summary():
    try:
        summary = get_daily_summary()
        if not summary:
            print("⚠️ No daily summary available to send.")
            return
        send_discord_alert(summary, color=0x7289DA, title="📅 Daily Performance Summary")
    except Exception as e:
        print(f"❌ Error sending daily summary: {e}")
