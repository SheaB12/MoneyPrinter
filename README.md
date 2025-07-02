# MoneyPrinter

This repository contains a simple proof-of-concept trading bot that uses
OpenAI GPT to analyze SPY intraday data and place trades through the
Tradier API.  A small Flask dashboard can be launched to view recent
trades.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set your API keys in `config.py` (OpenAI and Tradier).
3. Run the bot:
   ```bash
   python bot.py
   ```
4. (Optional) Start the dashboard:
   ```bash
   python flask_dashboard.py
   ```

The trading logic writes to `trade_log.csv`.  This example project is for
educational purposes only and **not** financial advice.
