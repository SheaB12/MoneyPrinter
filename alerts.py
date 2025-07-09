import os
import requests
from datetime import datetime

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(title, description, color=0x3498db):  # Default: blue
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL is not set.")
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

def send_threshold_change_alert(new_threshold, old_threshold):
    diff = round(abs(new_threshold - old_threshold), 3)
    color = 0xffa500 if new_threshold > old_threshold else 0x1abc9c  # Orange/Teal
    title = "⚙️ Confidence Threshold Changed"
    desc = (
        f"**Old Threshold:** {old_threshold:.2f}\n"
        f"**New Threshold:** {new_threshold:.2f}\n"
        f"**Change:** {diff:.3f}"
    )
    send_discord_alert(title, desc, color)
