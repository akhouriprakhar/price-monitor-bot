import os
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

# Get environment variables (Railway will provide these)
BOT_TOKEN = os.getenv('BOT_TOKEN')
PRICE_ALERT_THRESHOLD = float(os.getenv('PRICE_ALERT_THRESHOLD', '5'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))

# Validate required variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

print(f"✅ Configuration loaded:")
print(f"   • Price alert threshold: {PRICE_ALERT_THRESHOLD}%")
print(f"   • Check interval: {CHECK_INTERVAL} minutes")
