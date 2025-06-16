from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

TOKEN = "7215834710:AAHDas5fUxSU96BAKpQTn2d5P1tuT1hMw1Q"
ADMIN_ID = 7377694590  # Sizning ID (admin)

# Har bir user uchun vaqtinchalik savol va ID saqlanadi
user_data = {}  # {user_id: [(type, content)], ...}
last_user = {}  # {admin_id: user_id} — admin kimga javob berayotganini biladi

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📝 Savol yozish"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 Salom! Savol berish uchun pastdagi 📝 'Savol yozish' tugmasini bosing.", reply_markup=markup)

# Savol yozish tugmasi
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📝 Savol yozish":
        user_data[update.message.from_user.id] = []
        keyboard = [["📤 Yuborish"]]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "✍️ Savolingizni yozing yoki rasm/fayl yuboring.\nSo‘ng 📤 'Yuborish' tugmasini bosing.",
            reply_markup=markup
        )

# Medialarni yoki matnni yig‘ish
async def collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_data:
        return

    if update.message.text and update.message.text != "📤 Yuborish":
        user_data[user_id].append(("text", update.message.text))
    elif update.message.photo:
        file = update.message.photo[-1]
        user_data[user_id].append(("photo", file.file_id))
    elif update.message.document:
        user_data[user_id].append(("document", update.message.document.file_id))
    elif update.message.audio:
        user_data[user_id].append(("audio", update.message.audio.file_id))
    elif update.message.voice:
        user_data[user_id].append(("voice", update.message.voice.file_id))
    elif update.message.video:
        user_data[user_id].append(("video", update.message.video.file_id))

# Yuborish tugmasi
async def send_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_data:
        await update.message.reply_text("❗ Savol topilmadi.")
        return

    # foydalanuvchi haqida info olish
    user = update.message.from_user
    user_info = f"📩 Yangi savol:\n\n👤 Ism: {user.first_name}\n"
    if user.username:
        user_info += f"📛 Username: @{user.username}\n"
    user_info += f"🆔 ID: {user.id}\n\n"

    await update.message.reply_text("✅ Savolingiz yuborildi!\n🔄 Yangi savol uchun /start buyrug‘ini yuboring.", reply_markup=ReplyKeyboardRemove())

    # adminga yuborish
    await context.bot.send_message(chat_id=ADMIN_ID, text=user_info)

    for item_type, content in user_data[user_id]:
        if item_type == "text":
            await context.bot.send_message(chat_id=ADMIN_ID, text=content)
        elif item_type == "photo":
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=content)
        elif item_type == "document":
            await context.bot.send_document(chat_id=ADMIN_ID, document=content)
        elif item_type == "audio":
            await context.bot.send_audio(chat_id=ADMIN_ID, audio=content)
        elif item_type == "voice":
            await context.bot.send_voice(chat_id=ADMIN_ID, voice=content)
        elif item_type == "video":
            await context.bot.send_video(chat_id=ADMIN_ID, video=content)

    last_user[ADMIN_ID] = user_id
    user_data.pop(user_id)

# Admindan kelgan javobni qaytarish
async def reply_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    if ADMIN_ID not in last_user:
        await update.message.reply_text("⚠️ Oxirgi foydalanuvchi aniqlanmadi.")
        return

    to_user_id = last_user[ADMIN_ID]

    if update.message.text:
        await context.bot.send_message(chat_id=to_user_id, text=f"👨‍🏫 Admin javobi:\n\n{update.message.text}")
    elif update.message.photo:
        await context.bot.send_photo(chat_id=to_user_id, photo=update.message.photo[-1].file_id)
    elif update.message.document:
        await context.bot.send_document(chat_id=to_user_id, document=update.message.document.file_id)
    elif update.message.audio:
        await context.bot.send_audio(chat_id=to_user_id, audio=update.message.audio.file_id)
    elif update.message.voice:
        await context.bot.send_voice(chat_id=to_user_id, voice=update.message.voice.file_id)
    elif update.message.video:
        await context.bot.send_video(chat_id=to_user_id, video=update.message.video.file_id)

# Main
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📝 Savol yozish$"), handle_button))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📤 Yuborish$"), send_to_admin))
    app.add_handler(MessageHandler(filters.ALL, collect))
    app.add_handler(MessageHandler(filters.ALL, reply_from_admin))

    print("🤖 Bot ishga tushdi...")
    app.run_polling()
