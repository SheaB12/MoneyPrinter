import os
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_trade_alert(direction, confidence, reason, threshold, status):
    if not DISCORD_WEBHOOK_URL:
        print("❌ DISCORD_WEBHOOK_URL not set. Skipping alert.")
        return

    color = 0x00ff00 if direction != "SKIP" and confidence >= threshold else 0xffcc00
    title = f"📊 Trade Decision: {direction}"
    if direction == "SKIP":
        title = "⏭️ No Trade Today"

    embed = {
        "title": title,
        "color": color,
        "fields": [
            {"name": "Confidence", "value": f"{confidence:.2f}", "inline": True},
            {"name": "Threshold", "value": f"{threshold:.2f}", "inline": True},
            {"name": "Status", "value": status, "inline": True},
            {"name": "Reason", "value": reason or "N/A", "inline": False}
        ]
    }

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code != 204:
            print(f"⚠️ Discord alert failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"⚠️ Exception sending Discord alert: {e}")
