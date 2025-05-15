import os
import tempfile
import shutil
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Admin Telegram ID, 0 if not set
ADS_TEXT = os.getenv("ADS_TEXT", "")  # Optional ads text to append in title

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Send me any video/audio/photo link.")

def setads(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("You're not authorized to use this command.")
        return
    global ADS_TEXT
    ADS_TEXT = " ".join(context.args)
    update.message.reply_text(f"Ads text set to: {ADS_TEXT}")

def download_and_send(update: Update, context: CallbackContext):
    url = update.message.text
    chat_id = update.effective_chat.id

    msg_search = update.message.reply_text("Searching...")
    msg_wait = update.message.reply_text("Wait...")

    # Create temp dir for download
    temp_dir = tempfile.mkdtemp()

    ydl_opts = {
        "outtmpl": temp_dir + "/%(title)s.%(ext)s",
        "format": "best",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            filesize = info.get("filesize") or info.get("filesize_approx") or 0
            title = info.get("title", "Video")

            if filesize > 500 * 1024 * 1024:  # 500MB limit
                update.message.reply_text("Error: File size exceeds 500MB limit.")
                msg_search.delete()
                msg_wait.delete()
                shutil.rmtree(temp_dir)
                return

            ydl.download([url])

            # Find downloaded file path
            downloaded_file = None
            for file in os.listdir(temp_dir):
                downloaded_file = os.path.join(temp_dir, file)
                break

            # Append ads text in title if set
            caption = title
            if ADS_TEXT:
                caption += "\n\n" + ADS_TEXT

            # Send file based on mime type (basic check)
            if downloaded_file.endswith((".mp4", ".mkv", ".webm")):
                bot.send_video(chat_id=chat_id, video=open(downloaded_file, "rb"), caption=caption)
            elif downloaded_file.endswith((".mp3", ".m4a", ".wav")):
                bot.send_audio(chat_id=chat_id, audio=open(downloaded_file, "rb"), caption=caption)
            elif downloaded_file.endswith((".jpg", ".jpeg", ".png")):
                bot.send_photo(chat_id=chat_id, photo=open(downloaded_file, "rb"), caption=caption)
            else:
                bot.send_document(chat_id=chat_id, document=open(downloaded_file, "rb"), caption=caption)

            # Cleanup
            msg_search.delete()
            msg_wait.delete()
            shutil.rmtree(temp_dir)

    except Exception as e:
        msg_search.delete()
        msg_wait.delete()
        update.message.reply_text(f"Failed to download or send media: {str(e)}")
        shutil.rmtree(temp_dir)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("setads", setads, pass_args=True))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, download_and_send))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8443"))
    app.run(host="0.0.0.0", port=port)