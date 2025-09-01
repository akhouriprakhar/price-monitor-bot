import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)
import re
import signal
import sys
from urllib.parse import urlparse
from database import Database
from scraper import ProductScraper
from scheduler import PriceMonitor
from config import BOT_TOKEN

# --- Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ('amazon.in', 'flipkart.com', 'myntra.com')
ADMIN_CHAT_ID = 5682929226  # <-- IMPORTANT: Replace with your numeric Telegram chat ID

# --- State definitions for conversations ---
SET_PRICE, FEEDBACK = range(2)

# --- Initialize Components ---
db = Database()
scraper = ProductScraper()
monitor = PriceMonitor()

# --- Helper Functions ---
def is_product_url(text):
    """Check if text is a valid URL."""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.search(url_pattern, text) is not None

# --- Main Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and shows the main menu."""
    user_name = update.effective_user.first_name
    welcome_message = f"👋 **Hi {user_name}!**\n\nI'm your personal price tracking assistant. Send me a product link to get started, or use the buttons below! 🛒"
    keyboard = [
        [InlineKeyboardButton("📦 List My Products", callback_data='list_products')],
        [InlineKeyboardButton("📋 Get Help", callback_data='help'), InlineKeyboardButton("📝 Send Feedback", callback_data='feedback')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, parse_mode='Markdown', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a helpful message with all commands and features."""
    help_text = """
📋 **How I Can Help You:**

• **Track Products:** Just send me a product link from a supported site. I'll automatically fetch the price.

• **/list:** View all your tracked products. From here, you can click on an item to view it, stop tracking it, or set a target price.

• **Target Price:** Use the "🎯 Set Price" button in your product list to set a price goal. I will only notify you when the price drops below your target.

• **/feedback:** Send a message directly to my developer for suggestions or bug reports.
    """
    if update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's tracked products with interactive buttons."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    is_callback = update.callback_query is not None

    products = db.get_user_products(user.id)

    if not products:
        message_text = "You're not tracking any products yet! Send me a product URL to start."
        if is_callback:
            # If the list is now empty after deleting, edit the message.
            await update.callback_query.edit_message_text(text=message_text)
        else:
            await context.bot.send_message(chat_id=chat_id, text=message_text)
        return

    message_header = "📦 **Your Tracked Products:**"
    keyboard = []
    for product in products:
        product_id, title, _, price, url, target_price = product
        title_short = (title or "Unknown")[:30]
        price_text = f"₹{price:,.2f}" if price else "N/A"
        
        product_display = f"{title_short}... ({price_text})"
        if target_price:
            product_display += f" [🎯 ₹{target_price:,.2f}]"
            
        keyboard.append([
            InlineKeyboardButton(product_display, url=url),
            InlineKeyboardButton("🎯", callback_data=f'askprice_{product_id}'),
            InlineKeyboardButton("❌", callback_data=f'stop_{product_id}'),
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        try:
            await update.callback_query.edit_message_text(text=message_header, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.warning(f"Could not edit message (it might be the same): {e}")
    else:
        await context.bot.send_message(chat_id=chat_id, text=message_header, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming product URLs."""
    user_id = update.effective_user.id
    url = update.message.text.strip()

    if not is_product_url(url):
        await update.message.reply_text("Please send a valid product URL.")
        return

    try:
        domain = urlparse(url).netloc
        if not any(d in domain for d in SUPPORTED_DOMAINS):
            await update.message.reply_text(f"Sorry, I only support these sites: {', '.join(SUPPORTED_DOMAINS)}")
            return
    except Exception:
        await update.message.reply_text("That link seems invalid. Please try again.")
        return
    
    processing_msg = await update.message.reply_text("🔍 Analyzing product... Please wait.")
    
    product_info = scraper.get_product_info(url)
    
    if not product_info or not product_info.get('price'):
        await processing_msg.edit_text("❌ Sorry, I couldn't extract product details from this URL.")
        return
    
    product_id = db.add_product(user_id, url, product_info['title'], product_info['price'])
    
    if product_id is None:
        await processing_msg.edit_text("❌ An error occurred while adding the product to the database.")
        return

    success_message = f"✅ **Now Tracking!**\n\n**Product:** {product_info['title']}\n**Current Price:** ₹{product_info['price']:.2f}"
    keyboard = [[InlineKeyboardButton("🎯 Set a Target Price", callback_data=f'askprice_{product_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await processing_msg.edit_text(success_message, parse_mode='Markdown', reply_markup=reply_markup)

# --- Conversation Flow Handlers ---

async def ask_target_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation to set a target price."""
    query = update.callback_query
    product_id = int(query.data.split('_')[1])
    context.user_data['product_id_for_price'] = product_id
    await query.message.reply_text("What is your target price? (e.g., 15000)\nType /cancel to abort.")
    return SET_PRICE

async def save_target_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and saves the target price."""
    product_id = context.user_data.get('product_id_for_price')
    user_id = update.effective_user.id
    try:
        target_price = float(update.message.text)
        if db.set_target_price(product_id, user_id, target_price):
            await update.message.reply_text(f"✅ Great! I will notify you when the price drops below ₹{target_price:,.2f}.")
        else:
            await update.message.reply_text("❌ Something went wrong. I couldn't find that product to update.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ That doesn't look like a valid price. Please enter a number only.")
    
    context.user_data.pop('product_id_for_price', None)
    return ConversationHandler.END

async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation for user feedback."""
    await update.callback_query.message.reply_text("Please type your feedback, and I'll send it to my developer.\nType /cancel to abort.")
    return FEEDBACK

async def save_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives and forwards the user's feedback."""
    user = update.effective_user
    feedback_text = update.message.text
    forward_message = f"📝 **New Feedback from {user.full_name} (@{user.username}, ID: {user.id}):**\n\n\"{feedback_text}\""
    
    try:
        if ADMIN_CHAT_ID and ADMIN_CHAT_ID != "YOUR_OWN_TELEGRAM_CHAT_ID":
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=forward_message, parse_mode='Markdown')
            await update.message.reply_text("✅ Thank you! Your feedback has been sent.")
        else:
            await update.message.reply_text("✅ Feedback received! (Note: Admin notifications are not configured).")
            logger.info(forward_message)
    except Exception as e:
        logger.error(f"Failed to forward feedback: {e}")
        await update.message.reply_text("❌ Sorry, an error occurred while sending your feedback.")
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the current conversation."""
    context.user_data.clear()
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# --- General Button Click Router ---

async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes button clicks that are not part of a conversation."""
    query = update.callback_query
    await query.answer()

    if query.data == 'list_products':
        await list_products(update, context)
    elif query.data == 'help':
        await help_command(update, context)
    elif query.data.startswith('stop_'):
        user_id = query.effective_user.id
        product_id = int(query.data.split('_')[1])
        db.delete_product(user_id, product_id)
        await list_products(update, context) # Refresh the list

# --- Main Application Setup ---
def main():
    """Initializes and runs the bot."""
    logger.info("🤖 Starting Price Monitor Bot v2.0...")
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler for setting a target price
    set_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_target_price, pattern='^askprice_')],
        states={SET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_target_price)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )

    # Conversation handler for feedback
    feedback_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_feedback, pattern='^feedback$')],
        states={FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_feedback)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_products))
    application.add_handler(CommandHandler("feedback", ask_feedback)) # Allow command too
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    application.add_handler(set_price_conv)
    application.add_handler(feedback_conv)
    application.add_handler(CallbackQueryHandler(button_router)) # Handles non-conversation buttons
    
    monitor.start_monitoring()
    logger.info("🚀 Price Monitor Bot is running!")
    application.run_polling()

if __name__ == '__main__':
    main()

