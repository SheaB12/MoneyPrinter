# polygon_stream.py
import asyncio
import json
import websockets
import os

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY")
TICKER = "SPY"

async def stream_spy_data(callback):
    uri = "wss://delayed.polygon.io/stocks"

    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({
            "action": "auth",
            "params": POLYGON_API_KEY
        }))
        await websocket.send(json.dumps({
            "action": "subscribe",
            "params": f"AM.{TICKER}"
        }))

        print("📡 Listening for SPY live ticks...")
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if isinstance(data, list):
                for event in data:
                    await callback(event)
