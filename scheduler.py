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
        self.db = Database()
        self.scraper = ProductScraper()
        self.bot = Bot(token=BOT_TOKEN)
        self.is_running = False
        self.thread = None

    def _check_prices(self):
        """Scrapes and compares prices, prioritizing target price alerts."""
        logger.info("Scheduler running: Checking all product prices...")
        products = self.db.get_all_products()

        for product in products:
            product_id, user_id, url, title, last_price, target_price = product
            
            logger.info(f"Checking '{title[:30]}...' for user {user_id}")
            product_info = self.scraper.get_product_info(url)
            
            if not product_info or not product_info.get('price'):
                logger.warning(f"Could not get new price for {title}. Skipping.")
                continue

            current_price = product_info['price']
            
            if last_price is None or current_price == last_price:
                self.db.update_product_price(product_id, current_price)
                continue

            alert_reason = None
            # Priority 1: Check if price dropped below the user's target price
            if target_price and current_price <= target_price:
                alert_reason = f"dropped below your target of ₹{target_price:,.2f}"
            
            # Priority 2: If no target price, check for the general percentage drop
            elif not target_price:
                price_change_percent = ((current_price - last_price) / last_price) * 100
                if abs(price_change_percent) >= PRICE_ALERT_THRESHOLD:
                    change_type = "dropped" if price_change_percent < 0 else "increased"
                    alert_reason = f"{change_type} by {abs(price_change_percent):.2f}%"

            if alert_reason:
                logger.info(f"Significant price change for {title}! Reason: {alert_reason}")
                self._send_notification(user_id, title, url, last_price, current_price, alert_reason)
            
            # Always update the price in the database
            self.db.update_product_price(product_id, current_price)


    def _send_notification(self, user_id, title, url, old_price, new_price, reason):
        """Sends a price alert notification to the user."""
        emoji = "📉" if new_price < old_price else "📈"
        
        message = f"""
{emoji} **Price Alert!** {emoji}

**Product:** {title}
The price has **{reason}**!

**Old Price:** ₹{old_price:,.2f}
**New Price:** ₹{new_price:,.2f}

[View Product]({url})
        """
        try:
            asyncio.run(self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            ))
            logger.info(f"Notification sent to user {user_id} for '{title}'")
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
