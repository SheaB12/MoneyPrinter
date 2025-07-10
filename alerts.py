import requests
import os
from datetime import datetime

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

def send_trade_alert(action, confidence, reason, strike_type, entry_time, exit_time):
    color = 0x2ecc71 if action == "call" else 0xe74c3c if action == "put" else 0x95a5a6
    message = (
        f"**Action**: `{action.upper()}`\n"
        f"**Confidence**: `{confidence}%`\n"
        f"**Reason**: {reason}\n"
        f"**Strike Type**: `{strike_type}`\n"
        f"**Expiration**: `End of Day`\n"
        f"**Entry Time**: `{entry_time}`\n"
        f"**Exit Time**: `{exit_time}`"
    )
    send_discord_alert(message, color, title="🤖 GPT Trade Decision")
