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

# Initialize components
db = Database()
scraper = ProductScraper()
monitor = PriceMonitor()

def is_product_url(text):
    """Check if text contains a product URL"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.search(url_pattern, text) is not None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with buttons"""
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
• **/stop [number]** - Stop tracking a product

**To track a product:**
Just send me the product URL directly!
    """
    # This logic handles replies for both button clicks and direct commands
    if update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command, works for both command and button."""
    # Determine if the call is from a button or a command
    if update.callback_query:
        user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id
    else:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
    
    products = db.get_user_products(user_id)
    
    if not products:
        await context.bot.send_message(chat_id=chat_id, text="You're not tracking any products yet! Send me a product URL to start.")
        return
    
    message = "📦 **Your Tracked Products:**\n\n"
    for i, product in enumerate(products, 1):
        title = product[1] or "Unknown Product"
        current_price = f"₹{product[3]:.2f}" if product[3] else "Price not found"
        url = product[4]
        
        message += f"{i}. {title[:50]}...\n"
        message += f"   💰 **Current Price:** {current_price}\n"
        message += f"   🔗 [View Product]({url})\n\n"
    
    message += "Use `/stop [number]` to stop tracking a product."
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', disable_web_page_preview=True)


async def stop_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("Please specify which product to stop tracking.\nExample: `/stop 1`", parse_mode='Markdown')
        return
    
    try:
        product_number = int(context.args[0])
        products = db.get_user_products(user_id)
        
        if 1 <= product_number <= len(products):
            product_id = products[product_number - 1][0]
            db.delete_product(user_id, product_id)
            await update.message.reply_text(f"✅ Stopped tracking product #{product_number}")
        else:
            await update.message.reply_text("❌ Invalid product number. Use /list to see your products.")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number. Example: `/stop 1`", parse_mode='Markdown')

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle product URLs"""
    user_id = update.effective_user.id
    url = update.message.text.strip()
    
    if not is_product_url(url):
        await update.message.reply_text("Please send a valid product URL.")
        return
    
    processing_msg = await update.message.reply_text("🔍 Analyzing product... Please wait.")
    
    product_info = scraper.get_product_info(url)
    
    if not product_info or not product_info['price']:
        await processing_msg.edit_text("❌ Sorry, I couldn't extract the price from this URL. Please try a different product.")
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
    """Handles button clicks"""
    query = update.callback_query
    await query.answer()

    if query.data == 'list_products':
        # Pass the original Update object to the handler
        await list_products(update, context)
    elif query.data == 'help':
        # Pass the original Update object to the handler
        await help_command(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Exception while handling an update: {context.error}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal. Stopping bot...")
    monitor.stop_monitoring()
    sys.exit(0)

def main():
    """Run the bot with price monitoring"""
    logger.info("🤖 Starting Price Monitor Bot...")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    monitor.start_monitoring()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers for commands and messages
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_products))
    application.add_handler(CommandHandler("stop", stop_tracking))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    # Add handler for button clicks
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_error_handler(error_handler)
    
    logger.info("🚀 Price Monitor Bot is running!")
    logger.info("📊 Price monitoring is active!")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()

