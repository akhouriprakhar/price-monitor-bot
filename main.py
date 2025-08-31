import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
import re
import signal
import sys
from urllib.parse import urlparse # <-- ADD THIS IMPORT
from database import Database
from scraper import ProductScraper
from scheduler import PriceMonitor
from config import BOT_TOKEN

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ADD THIS LIST OF SUPPORTED SITES ---
SUPPORTED_DOMAINS = ('amazon.in', 'flipkart.com', 'myntra.com')
# -----------------------------------------

# Initialize components
db = Database()
scraper = ProductScraper()
monitor = PriceMonitor()

def is_product_url(text):
    """Check if text contains a product URL."""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.search(url_pattern, text) is not None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with buttons and personalization."""
    user_name = update.effective_user.first_name
    welcome_message = f"""
👋 **Hi {user_name}!**

🔍 Welcome to the Price Monitor Bot! I can help you track product prices and notify you of changes.

Just send me a product link to get started, or use the buttons below! 🛒
    """
    keyboard = [
        [InlineKeyboardButton("📦 List My Products", callback_data='list_products')],
        [InlineKeyboardButton("📋 Get Help", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command, works for both command and button."""
    help_text = """
📋 **Available Commands:**

• **/start** - Welcome message
• **/help** - Show this help
• **/list** - Show your tracked products

**To track a product:**
Just send me the product URL directly!

**To stop tracking:**
Use the 'Stop' button next to an item in your /list.
    """
    # This logic handles replies for both button clicks and direct commands
    if update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command with interactive stop buttons."""
    # This logic handles being called from a command or a button click
    is_callback = update.callback_query is not None
    user = update.effective_user
    chat_id = update.effective_chat.id

    products = db.get_user_products(user.id)

    if not products:
        await context.bot.send_message(chat_id=chat_id, text="You're not tracking any products yet! Send me a product URL to start.")
        return

    message = "📦 **Your Tracked Products:**"
    keyboard = []
    for i, product in enumerate(products, 1):
        product_id, title, _, current_price_val, url = product
        title = title or "Unknown Product"
        current_price = f"₹{current_price_val:.2f}" if current_price_val else "N/A"
        
        product_text = f"{i}. {title[:35]}... ({current_price})"
        keyboard.append([
            InlineKeyboardButton(product_text, url=url),
            InlineKeyboardButton("❌ Stop", callback_data=f'stop_{product_id}')
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # If it's a button click, edit the existing message. Otherwise, send a new one.
    if is_callback:
        try:
            await update.callback_query.edit_message_text(text=message, parse_mode='Markdown', reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e: # Handle case where message is unchanged
            logger.info(f"Could not edit message, sending new one: {e}")
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', reply_markup=reply_markup, disable_web_page_preview=True)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', reply_markup=reply_markup, disable_web_page_preview=True)


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product URLs."""
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    if not is_product_url(url):
        await update.message.reply_text("Please send a valid product URL.")
        return

    # --- NEW: Check if the domain is supported ---
    try:
        domain = urlparse(url).netloc
        if not any(supported_domain in domain for supported_domain in SUPPORTED_DOMAINS):
            supported_sites_str = ", ".join(SUPPORTED_DOMAINS)
            await update.message.reply_text(f"Sorry, I can only track products from these sites:\n{supported_sites_str}")
            return
    except Exception:
        await update.message.reply_text("That link seems to be invalid. Please try another one.")
        return
    # ------------------------------------------
    
    processing_msg = await update.message.reply_text("🔍 Analyzing product... Please wait.")
    
    product_info = scraper.get_product_info(url)
    
    if not product_info or not product_info.get('price'):
        await processing_msg.edit_text("❌ Sorry, I couldn't extract the product details from this URL. Please try a different one.")
        return
    
    db.add_product(user_id, url, product_info['title'], product_info['price'])
    
    success_message = f"""
✅ **Now Tracking!**

📦 **Product:** {product_info['title']}
💰 **Current Price:** ₹{product_info['price']:.2f}

I'll notify you when the price changes significantly!
Use /list to see all your tracked products.
    """
    
    await processing_msg.edit_text(success_message, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all button clicks."""
    query = update.callback_query
    await query.answer()

    command, *data = query.data.split('_')

    if command == 'list':
        await list_products(query, context)
    elif command == 'help':
        await help_command(query, context)
    elif command == 'stop':
        user_id = query.effective_user.id
        product_id = int(data[0])
        db.delete_product(user_id, product_id)
        # Refresh the product list automatically after deletion
        await list_products(query, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Exception while handling an update: {context.error}")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal. Stopping bot...")
    monitor.stop_monitoring()
    sys.exit(0)

def main():
    """Run the bot."""
    logger.info("🤖 Starting Price Monitor Bot...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor.start_monitoring()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_products))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_error_handler(error_handler)
    
    logger.info("🚀 Price Monitor Bot is running!")
    logger.info("📊 Price monitoring is active!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
