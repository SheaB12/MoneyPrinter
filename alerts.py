import os
import requests
from dotenv import load_dotenv

load_dotenv()
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(content):
    if not WEBHOOK_URL:
        raise EnvironmentError("DISCORD_WEBHOOK_URL is not set.")
    
    payload = {
        "content": content
    }

    response = requests.post(WEBHOOK_URL, json=payload)
    if response.status_code != 204:
        print(f"❌ Discord alert failed: {response.text}")

def format_discord_message(decision, status):
    emoji = "📈" if decision["decision"] == "CALL" else "📉"
    status_emoji = "✅" if status == "EXECUTED" else "⚠️"

    return (
        f"{emoji} **Decision:** {decision['decision']}\n"
        f"🎯 **Confidence:** {round(decision['confidence'] * 100, 2)}%\n"
        f"🗒️ **Reason:** {decision['reason']}\n"
        f"{status_emoji} **Status:** {status}"
    )

def alert_threshold_change(message):
    send_discord_alert(f"📢 **Threshold Update**\n{message}")
