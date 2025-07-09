import os
import requests
from datetime import datetime

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_trade_alert(decision, confidence, reason):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL not set.")
        return

    message = {
        "embeds": [{
            "title": f"📈 Trade Signal: {decision}",
            "description": f"**Confidence:** {confidence:.2f}\n**Reason:** {reason}",
            "color": 3066993 if decision == "CALL" else 15158332 if decision == "PUT" else 8359053,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("✅ Discord alert sent.")
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

def send_threshold_change_alert(new_threshold, old_threshold):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL not set.")
        return

    message = {
        "embeds": [{
            "title": "📊 Threshold Adjustment",
            "description": f"**New Threshold:** {new_threshold:.2f}\n**Previous:** {old_threshold:.2f}",
            "color": 3447003,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=message)
        print("✅ Threshold change alert sent.")
    except Exception as e:
        print(f"❌ Failed to send threshold alert: {e}")
