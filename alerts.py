import os
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(title, description, color=0x3498db):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ Discord webhook URL not set.")
        return

    data = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")

def send_threshold_change_alert(new_threshold, old_threshold):
    diff = round(new_threshold - old_threshold, 3)
    send_discord_alert(
        title="⚠️ Confidence Threshold Adjusted",
        description=f"New: **{new_threshold:.2f}** (was {old_threshold:.2f}, Δ = {diff})",
        color=0xf1c40f
    )

def send_trade_alert(decision_data, execution_result):
    decision = decision_data.get("decision", "UNKNOWN")
    confidence = decision_data.get("confidence", 0)
    reason = decision_data.get("reason", "N/A")
    status = execution_result.get("status", "unknown")
    notes = execution_result.get("notes", "")

    color = 0x2ecc71 if decision in ["CALL", "PUT"] else 0x95a5a6

    send_discord_alert(
        title=f"📊 Trade Decision: {decision}",
        description=(
            f"**Confidence**: {confidence:.2f}\n"
            f"**Reason**: {reason}\n"
            f"**Status**: {status}\n"
            f"**Notes**: {notes}"
        ),
        color=color
    )
