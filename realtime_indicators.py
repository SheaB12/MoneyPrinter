import websocket
import json
import os

API_KEY = os.getenv("POLYGON_API_KEY")

def on_message(ws, message):
    print(f"📈 Real-time message: {message}")

def on_open(ws):
    auth_data = {"action": "auth", "params": API_KEY}
    ws.send(json.dumps(auth_data))

    # Subscribe to SPY 1-minute bars (aggregates)
    sub_data = {"action": "subscribe", "params": "A.SPY"}
    ws.send(json.dumps(sub_data))

def on_error(ws, error):
    print(f"❌ Error: {error}")

def on_close(ws):
    print("🚪 Connection closed.")

socket = f"wss://socket.polygon.io/stocks"

ws = websocket.WebSocketApp(socket,
                            on_open=on_open,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)

print("🔌 Connecting to Polygon real-time feed...")
ws.run_forever()
