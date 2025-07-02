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
2. Set the required environment variables.  You can copy `.env.example` to
   `.env` and fill in your credentials or export them in your shell:
   - `TRADIER_TOKEN`
   - `TRADIER_ACCOUNT_ID`
   - `OPENAI_API_KEY`
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

## GitHub Actions

An example workflow is provided in `.github/workflows/run-bot.yml` for running
the bot using GitHub repository secrets. Define the following secrets in your
repository settings so the workflow can authenticate:

```
TRADIER_TOKEN
TRADIER_ACCOUNT_ID
OPENAI_API_KEY
```

Trigger the workflow manually from the Actions tab to execute the bot with
these credentials.
