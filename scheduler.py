import schedule
import time
import threading
import logging
import asyncio
from telegram import Bot
from database import Database
from scraper import ProductScraper
from config import BOT_TOKEN, PRICE_ALERT_THRESHOLD, CHECK_INTERVAL

logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self):
        """Initializes the price monitor components."""
        self.db = Database()
        self.scraper = ProductScraper()
        self.bot = Bot(token=BOT_TOKEN)
        self.is_running = False
        self.thread = None

    def _check_prices(self):
        """The core job that scrapes and compares prices."""
        logger.info("Scheduler running: Checking all product prices...")
        products = self.db.get_all_products()

        for product in products:
            product_id, user_id, url, title, last_price = product
            
            logger.info(f"Checking: {title[:30]}...")
            product_info = self.scraper.get_product_info(url)
            
            if not product_info or not product_info.get('price'):
                logger.warning(f"Could not get new price for {title}. Skipping.")
                continue

            current_price = product_info['price']
            
            if last_price is None: # First check after adding
                self.db.update_product_price(product_id, current_price)
                continue

            price_change_percent = ((current_price - last_price) / last_price) * 100

            if abs(price_change_percent) >= PRICE_ALERT_THRESHOLD:
                logger.info(f"Significant price change detected for {title}!")
                self._send_notification(user_id, title, url, last_price, current_price)
                self.db.update_product_price(product_id, current_price)
            else:
                logger.info(f"No significant price change for {title}.")

    def _send_notification(self, user_id, title, url, old_price, new_price):
        """Sends a price alert notification to the user via Telegram."""
        change_type = "dropped" if new_price < old_price else "increased"
        emoji = "📉" if change_type == "dropped" else "📈"
        
        message = f"""
{emoji} **Price Alert!** {emoji}

**Product:** {title}
**Old Price:** ₹{old_price:,.2f}
**New Price:** ₹{new_price:,.2f}

The price has {change_type}!

[View Product]({url})
        """
        try:
            # Use asyncio to run the async bot method in a sync context
            asyncio.run(self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            ))
            logger.info(f"Notification sent to user {user_id} for product '{title}'")
        except Exception as e:
            logger.error(f"Failed to send notification to user {user_id}: {e}")

    def _run_scheduler(self):
        """Sets up and runs the scheduled job loop."""
        schedule.every(CHECK_INTERVAL).minutes.do(self._check_prices)
        logger.info(f"Scheduler configured to check prices every {CHECK_INTERVAL} minutes.")
        
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
        
        logger.info("Scheduler has stopped.")

    def start_monitoring(self):
        """Starts the price monitoring in a separate thread."""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            logger.info("Price monitoring thread started.")

    def stop_monitoring(self):
        """Stops the price monitoring thread."""
        if self.is_running:
            self.is_running = False
            logger.info("Stopping price monitoring thread...")