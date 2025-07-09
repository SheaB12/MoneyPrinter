import os
import requests

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message: str):
    if not WEBHOOK_URL:
        raise EnvironmentError("DISCORD_WEBHOOK_URL is not set in environment variables.")
    
    payload = {
        "content": message
    }
    response = requests.post(WEBHOOK_URL, json=payload)
    if response.status_code != 204:
        raise Exception(f"Failed to send Discord alert: {response.text}")

def send_threshold_change_alert(new_threshold: float, old_threshold: float):
    message = (
        f"⚠️ **Confidence Threshold Changed**\n"
        f"Old Threshold: `{round(old_threshold, 2)}`\n"
        f"New Threshold: `{round(new_threshold, 2)}`"
    )
    send_discord_alert(message)
