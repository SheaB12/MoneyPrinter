import os
import requests

def send_discord_alert(decision, confidence, reason, action):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL not set.")
        return

    color = 0x7289da  # Blue default
    if action == "TRADE":
        color = 0x2ecc71  # Green
    elif action == "SKIPPED":
        color = 0xe67e22  # Orange
    elif action == "REJECTED":
        color = 0xe74c3c  # Red

    embed = {
        "title": f"🧠 GPT Decision: {decision.upper()}",
        "color": color,
        "fields": [
            {"name": "✅ Confidence", "value": f"{confidence:.0%}", "inline": True},
            {"name": "💬 Reason", "value": reason or "*No reason provided*", "inline": False},
            {"name": "📊 Action", "value": action, "inline": True},
        ]
    }

    payload = {"embeds": [embed]}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print("✅ Discord alert sent.")
    except Exception as e:
        print("⚠️ Failed to send Discord alert:", e)
