from datetime import datetime

# Simulated trade execution logic
def execute_trade(direction):
    # Replace this with real trade logic if needed
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "timestamp": now,
        "action": f"Simulated {direction} option",
        "status": "executed",
        "notes": "Paper trade only"
    }
