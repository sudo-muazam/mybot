import requests
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "7757762485:AAHY5BrJ58YpdW50lAwRUsTwahtRDrd1RyA"
user_state = {}

def get_search_keyboard():
    keyboard = [["🔍 Search by Number", "🆔 Search by CNIC"]]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "👋 Welcome! Please choose an option to search:",
        reply_markup=get_search_keyboard()
    )

async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if text == "🔍 Search by Number":
        user_state[chat_id] = "number"
        await update.message.reply_text("📱 Please enter the mobile number (10 or 11 digits):")
        return

    if text == "🆔 Search by CNIC":
        user_state[chat_id] = "cnic"
        await update.message.reply_text("🆔 Please enter the CNIC number (13 digits, without dashes):")
        return

    if chat_id not in user_state:
        await update.message.reply_text(
            "⚠ Please start by typing /start and selecting an option.",
            reply_markup=get_search_keyboard()
        )
        return

    search_type = user_state[chat_id]

    if search_type == "number":
        if not text.isdigit() or len(text) not in [10, 11]:
            await update.message.reply_text("❌ Invalid mobile number. Enter 10 or 11 digits.")
            return
    elif search_type == "cnic":
        if not text.isdigit() or len(text) != 13:
            await update.message.reply_text("❌ Invalid CNIC. Enter exactly 13 digits.")
            return

    await update.message.reply_text("🔍 Searching... Please wait.")

    payload = {"mobileNumber": text, "submit": "Search"}
    url = "https://minahilsimsdata.pro/search.php"

    try:
        response = requests.post(url, data=payload)
        soup = BeautifulSoup(response.text, "html.parser")

        result_div = soup.find("div", id="result")
        if not result_div:
            await update.message.reply_text("⚠ No result found.")
            developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: +923067632070"
            await update.message.reply_text(developer_msg)
            await update.message.reply_text("Choose your search type:", reply_markup=get_search_keyboard())
            user_state.pop(chat_id, None)
            return

        rows = result_div.find_all("tr")
        if len(rows) < 2:
            await update.message.reply_text("⚠ No result found.")
            developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: +923067632070"
            await update.message.reply_text(developer_msg)
            await update.message.reply_text("Choose your search type:", reply_markup=get_search_keyboard())
            user_state.pop(chat_id, None)
            return

        result_text = ""
        for row in rows[1:]:
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if cols:
                result_text += (
                    f"📱 Mobile: {cols[0]}\n"
                    f"👤 Name: {cols[1]}\n"
                    f"🆔 CNIC: {cols[2]}\n"
                    f"🏠 Address: {cols[3]}\n\n"
                )

        await update.message.reply_text(result_text.strip() or "⚠ No data found.")

        developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: +923067632070"
        await update.message.reply_text(developer_msg)

        user_state.pop(chat_id, None)
        await update.message.reply_text("Choose your search type:", reply_markup=get_search_keyboard())

    except Exception as e:
        await update.message.reply_text(f"❌ Error occurred: {e}")
        developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: +923067632070"
        await update.message.reply_text(developer_msg)
        await update.message.reply_text("Choose your search type:", reply_markup=get_search_keyboard())
        user_state.pop(chat_id, None)

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_choice))

    print("🤖 Bot is running...")
    app.run_polling()
