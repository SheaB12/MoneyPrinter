import os
import requests

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def send_discord_alert(message):
    if not WEBHOOK_URL:
        raise EnvironmentError("DISCORD_WEBHOOK_URL is not set.")
    payload = {"content": message}
    requests.post(WEBHOOK_URL, json=payload)

def format_discord_message(decision, status):
    emoji = "✅" if status == "EXECUTED" else "⚠️"
    return (
        f"🪩 **Decision**: `{decision['decision'].upper()}`\n"
        f"✅ **Confidence**: `{decision['confidence'] * 100:.2f}%`\n"
        f"💬 **Reason**: {decision['reason']}\n"
        f"{emoji} **Status**: {status}"
    )

def alert_threshold_change(new, old):
    diff = (new - old) * 100
    emoji = "📊"
    send_discord_alert(
        f"{emoji} **Threshold Change Alert**\n"
        f"Old: `{old * 100:.2f}%` → New: `{new * 100:.2f}%`\n"
        f"Change: `{diff:+.2f}%`"
    )
