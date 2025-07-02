@echo off
cd /d C:\Projects\TradingBot
call venv\Scripts\activate
start http://127.0.0.1:5000
python flask_dashboard.py
