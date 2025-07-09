import os
import requests

def send_discord_alert(message: str):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        raise EnvironmentError("DISCORD_WEBHOOK_URL is not set in environment variables.")

    payload = {
        "content": None,
        "embeds": [
            {
                "title": "💸 Money Printer GPT Decision",
                "description": message,
                "color": 5763719 if "CALL" in message else 15548997
            }
        ]
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=payload, headers=headers)

    if response.status_code != 204:
        raise Exception(f"Failed to send Discord alert: {response.status_code}, {response.text}")
