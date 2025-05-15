import os
import re
import threading
import logging
import requests
import validators
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMINS = [123456789]  # Telegram user IDs of admins

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB max file size

# Global dictionary to hold admin-configured ad text
ad_text = ""

def is_valid_url(url: str) -> bool:
    """Validate URL format using validators package"""
    return validators.url(url)

def get_file_size(url: str) -> int:
    """Attempt to get file size via HEAD request"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        size = response.headers.get('content-length')
        return int(size) if size is not None else -1
    except Exception as e:
        logger.warning(f"HEAD request failed: {e}")
        return -1

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to Kexodrop! Send me any download link, and I will fetch the file for you.")

def send_welcome(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome to Kexodrop! Please send me the download link.")

def download_and_send(update: Update, context: CallbackContext, url: str):
    chat_id = update.message.chat_id
    filename = url.split('/')[-1].split('?')[0] or "downloaded_file"
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

    update.message.reply_text("Starting download... Please wait.")
    logger.info(f"User {update.message.from_user.id} requested download: {url}")

    try:
        size = get_file_size(url)
        if size > MAX_FILE_SIZE:
            update.message.reply_text(f"File is too large ({size/(1024*1024):.2f} MB). Limit is {MAX_FILE_SIZE/(1024*1024)} MB.")
            return
    except Exception as e:
        logger.error(f"Error checking file size: {e}")

    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        update.message.reply_text("Download complete. Uploading file...")
        with open(filename, 'rb') as f:
            context.bot.send_document(chat_id=chat_id, document=f, caption=ad_text)

        update.message.reply_text("File sent successfully!")

    except Exception as e:
        logger.error(f"Error downloading or sending file: {e}")
        update.message.reply_text(f"Error occurred: {e}")

    finally:
        if os.path.exists(filename):
            os.remove(filename)
            logger.info(f"Deleted file {filename}")

def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    user_id = update.message.from_user.id

    greetings = ['hello', 'hi', 'hey']
    if any(greet in text.lower() for greet in greetings):
        send_welcome(update, context)
        return

    if is_valid_url(text):
        # Download in separate thread to keep bot responsive
        threading.Thread(target=download_and_send, args=(update, context, text)).start()
    else:
        send_welcome(update, context)

def set_ad(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id not in ADMINS:
        update.message.reply_text("You are not authorized to use this command.")
        return

    global ad_text
    ad_text = " ".join(context.args)
    update.message.reply_text(f"Ad text set to: {ad_text}")

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("setad", set_ad))
    dp.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_message))

    updater.start_polling()
    logger.info("Bot started...")
    updater.idle()

if __name__ == "__main__":
    main()
