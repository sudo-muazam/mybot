import requests
from bs4 import BeautifulSoup
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
import json
import os
import openpyxl
from openpyxl.utils import get_column_letter
import tempfile

BOT_TOKEN = "7757762485:AAHY5BrJ58YpdW50lAwRUsTwahtRDrd1RyA"
ADMIN_ID = 6550324099
user_state = {}

STATS_FILE = "stats.json"
users_data = {}

# ====== Load stats from file ======
def load_stats():
    global users_data
    if not os.path.isfile(STATS_FILE):
        users_data = {}
        return
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                users_data = data
            else:
                print("Warning: stats.json content is not a dict. Resetting data.")
                users_data = {}
    except Exception as e:
        print(f"Error loading stats.json: {e}")
        users_data = {}

# ====== Save stats to file ======
def save_stats():
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(users_data, f, indent=2)
    except Exception as e:
        print(f"Error saving stats.json: {e}")

# ====== Inline Keyboard ======
def get_search_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🔍 Search by Number", callback_data="search_number"),
            InlineKeyboardButton("🆔 Search by CNIC", callback_data="search_cnic"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== /start Command ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name or "Unknown"

    if user_id not in users_data:
        users_data[user_id] = {"username": username, "search_count": 0, "searches": []}
        save_stats()
    else:
        users_data[user_id]["username"] = username
        save_stats()

    user_state.pop(update.effective_chat.id, None)
    await update.message.reply_text(
        "👋 Welcome! Please choose an option to search:",
        reply_markup=get_search_inline_keyboard()
    )

# ====== Callback Query Handler ======
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "search_number":
        user_state[chat_id] = "number"
        await query.message.reply_text("📱 Please enter the mobile number (10 or 11 digits):", reply_markup=ReplyKeyboardRemove())
    elif query.data == "search_cnic":
        user_state[chat_id] = "cnic"
        await query.message.reply_text("🆔 Please enter the CNIC number (13 digits, without dashes):", reply_markup=ReplyKeyboardRemove())
    else:
        await query.message.reply_text("⚠ Unknown option selected.")

# ====== Handler for searches ======
async def menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_id = str(user.id)
    username = user.username or user.first_name or "Unknown"
    text = update.message.text.strip()

    if user_id not in users_data:
        users_data[user_id] = {"username": username, "search_count": 0, "searches": []}
    else:
        users_data[user_id]["username"] = username
    save_stats()

    if chat_id not in user_state:
        await update.message.reply_text("⚠ Please start by typing /start and selecting an option:", reply_markup=get_search_inline_keyboard())
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

    users_data[user_id]["search_count"] += 1
    users_data[user_id]["searches"].append({"type": search_type, "query": text})
    save_stats()

    await update.message.reply_text("🔍 Searching... Please wait.")

    payload = {"mobileNumber": text, "submit": "Search"}
    url = "https://minahilsimsdata.pro/search.php"

    try:
        response = requests.post(url, data=payload)
        soup = BeautifulSoup(response.text, "html.parser")
        result_div = soup.find("div", id="result")
        if not result_div:
            await update.message.reply_text("⚠ No result found.")
            await send_developer_info(update)
            return

        rows = result_div.find_all("tr")
        if len(rows) < 2:
            await update.message.reply_text("⚠ No result found.")
            await send_developer_info(update)
            return

        result_text = ""
        for row in rows[1:]:
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if cols:
                result_text += f"📱 Mobile: {cols[0]}\n👤 Name: {cols[1]}\n🆔 CNIC: {cols[2]}\n🏠 Address: {cols[3]}\n\n"

        await update.message.reply_text(result_text.strip() or "⚠ No data found.")
        await send_developer_info(update)

    except Exception as e:
        await update.message.reply_text(f"❌ Error occurred: {e}")
        await send_developer_info(update)

# ====== Developer info ======
async def send_developer_info(update: Update):
    developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: +923067632070"
    await update.message.reply_text(developer_msg)
    await update.message.reply_text("Choose your search type:", reply_markup=get_search_inline_keyboard())
    user_state.pop(update.effective_chat.id, None)

# ====== /stats Command (Sends Excel) ======
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ You are not authorized to view stats.")
            return

        if not users_data:
            await update.message.reply_text("No users or searches recorded yet.")
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "User Stats"
        headers = ["User ID", "Username", "Search Count", "Search Type", "Query"]
        ws.append(headers)

        for uid, data in users_data.items():
            if not isinstance(data, dict):
                continue
            username = data.get("username", "Unknown")
            search_count = data.get("search_count", 0)
            searches = data.get("searches", [])
            if not searches:
                ws.append([uid, username, search_count, "", ""])
            else:
                for s in searches:
                    qtype = "Number" if s["type"] == "number" else "CNIC"
                    ws.append([uid, username, search_count, qtype, s["query"]])

        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp_path = tmp.name
            wb.save(tmp_path)

        with open(tmp_path, "rb") as file:
            await context.bot.send_document(chat_id=ADMIN_ID, document=file, filename="user_stats.xlsx")

        os.remove(tmp_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ====== Main ======
if __name__ == "__main__":
    load_stats()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_choice))
    print("🤖 Bot is running...")
    app.run_polling()
