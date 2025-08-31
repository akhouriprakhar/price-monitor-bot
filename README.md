# Price Monitor Telegram Bot

A Telegram bot that tracks product prices from various e-commerce sites and sends alerts when prices change.

## Features

- 🔍 Track prices from Amazon, Flipkart, Myntra and more
- 📊 Get notified of price drops and increases
- 💾 Store tracking data in SQLite database
- 🤖 Easy Telegram interface
- 🔄 Automatic price checking every hour

## Usage

1. Start a chat with the bot
2. Send `/start` to get started
3. Send any product URL to begin tracking
4. Use `/list` to see your tracked products
5. Use `/stop [number]` to remove a product

## Deployment

This bot is designed to run on Railway. Environment variables required:

- `BOT_TOKEN` - Your Telegram bot token from @BotFather
- `PRICE_ALERT_THRESHOLD` - Price change threshold (default: 5%)
- `CHECK_INTERVAL` - How often to check prices in minutes (default: 60)

## Local Development

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/akhouriprakhar/price-monitor-bot.git](https://github.com/akhouriprakhar/price-monitor-bot.git)
    ```
2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create and configure the .env file** Create a new file in the project folder named `.env`. Open it and add the following lines, replacing the placeholder with your actual bot token:
    ```
    BOT_TOKEN=YOUR_BOT_TOKEN_FROM_BOTFATHER
    PRICE_ALERT_THRESHOLD=5
    CHECK_INTERVAL=60
    ```
4.  **Run the bot**
    ```bash
    python main.py
    ```
