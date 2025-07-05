import os
import requests

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def send_discord_alert(title, description, color=3447003):
    if not WEBHOOK_URL:
        print("DISCORD_WEBHOOK not set.")
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }

    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Discord alert sent.")
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")
