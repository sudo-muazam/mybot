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
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
import tempfile

BOT_TOKEN = "7757762485:AAHY5BrJ58YpdW50lAwRUsTwahtRDrd1RyA"
ADMIN_ID = 6550324099

user_state = {}

STATS_FILE = "stats.json"
users_data = {}

# ====== Load stats ======
def load_stats():
    global users_data
    if not os.path.isfile(STATS_FILE):
        users_data = {}
        return
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            users_data = data if isinstance(data, dict) else {}
    except:
        users_data = {}

# ====== Save stats ======
def save_stats():
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(users_data, f, indent=2)
    except:
        pass

# ====== Inline Keyboards ======
def get_main_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🆓 Free Search", callback_data="free"),
            InlineKeyboardButton("💎 Premium Search", callback_data="premium"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_free_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📱 Search by Number", callback_data="search_number"),
            InlineKeyboardButton("🆔 Search by CNIC", callback_data="search_cnic"),
        ],
        [InlineKeyboardButton("⬅ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_premium_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🤖 Auto", callback_data="premium_auto"),
            InlineKeyboardButton("☎ PTCL Detail", callback_data="premium_ptcl"),
        ],
        [
            InlineKeyboardButton("📱 Number Ownership", callback_data="premium_number"),
            InlineKeyboardButton("🚗 Vehicle Detail", callback_data="premium_vehicle"),
        ],
        [
            InlineKeyboardButton("🆔 CNIC Detail", callback_data="premium_cnic"),
        ],
        [InlineKeyboardButton("⬅ Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ====== /start ======
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
        "👋 Welcome! Please choose an option:",
        reply_markup=get_main_inline_keyboard()
    )

# ====== Callback Handler ======
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    # Free vs Premium
    if query.data == "free":
        await query.message.reply_text("🆓 Free Search Options:", reply_markup=get_free_inline_keyboard())
    elif query.data == "premium":
        await query.message.reply_text("💎 Premium Search Options:", reply_markup=get_premium_inline_keyboard())
    elif query.data == "back_main":
        await query.message.reply_text("⬅ Back to Main Menu:", reply_markup=get_main_inline_keyboard())

    # Free Search options
    elif query.data == "search_number":
        user_state[chat_id] = ("free", "number")
        await query.message.reply_text("📱 Please enter the mobile number (10 or 11 digits):", reply_markup=ReplyKeyboardRemove())
    elif query.data == "search_cnic":
        user_state[chat_id] = ("free", "cnic")
        await query.message.reply_text("🆔 Please enter the CNIC number (13 digits):", reply_markup=ReplyKeyboardRemove())

    # Premium Search options (blocked)
    elif query.data.startswith("premium_"):
        await query.message.reply_text("❌ You are not a premium member.")
    else:
        await query.message.reply_text("⚠ Unknown option.")

# ====== Handle searches ======
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
        await update.message.reply_text("⚠ Please type /start and select an option.", reply_markup=get_main_inline_keyboard())
        return

    mode, search_type = user_state[chat_id]

    # ===== Free Search =====
    if mode == "free":
        if search_type == "number":
            if not text.isdigit() or len(text) not in [10, 11]:
                await update.message.reply_text("❌ Invalid number. Enter 10 or 11 digits.")
                return
        elif search_type == "cnic":
            if not text.isdigit() or len(text) != 13:
                await update.message.reply_text("❌ Invalid CNIC. Enter exactly 13 digits.")
                return

        users_data[user_id]["search_count"] += 1
        users_data[user_id]["searches"].append({"type": search_type, "query": text})
        save_stats()

        await update.message.reply_text("🔍 Searching (Free)... Please wait.")

        url = "https://minahalsimdata.com.pk/sim-info/"
        payload = {"searchinfo": text}
        try:
            response = requests.post(url, data=payload)
            soup = BeautifulSoup(response.text, "html.parser")
            result_containers = soup.find_all("div", class_="resultcontainer")

            if not result_containers:
                await update.message.reply_text("⚠ No result found.")
                await send_developer_info(update)
                return

            result_text = ""
            for container in result_containers:
                rows = container.find_all("div", class_="row")
                record = {}
                for row in rows:
                    head = row.find("span", class_="detailshead")
                    value = row.find("span", class_="details")
                    if head and value:
                        record[head.get_text(strip=True).replace(":", "")] = value.get_text(strip=True)

                result_text += (
                    f"👤 Name: {record.get('Name', 'N/A')}\n"
                    f"📱 Mobile: {record.get('Mobile', 'N/A')}\n"
                    f"🌍 Country: {record.get('Country', 'N/A')}\n"
                    f"🆔 CNIC: {record.get('CNIC', 'N/A')}\n"
                    f"🏠 Address: {record.get('Address', 'N/A')}\n\n"
                )

            await update.message.reply_text(result_text.strip() or "⚠ No data found.")
            await send_developer_info(update)

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            await send_developer_info(update)

    # ===== Premium Search (blocked) =====
    elif mode == "premium":
        await update.message.reply_text("❌ You are not a premium member.")
        await send_developer_info(update)

# ===== Developer info =====
async def send_developer_info(update: Update):
    developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: "
    await update.message.reply_text(developer_msg)
    await update.message.reply_text("Choose search type:", reply_markup=get_main_inline_keyboard())
    user_state.pop(update.effective_chat.id, None)

# ====== Stats Command ======
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Unauthorized.")
            return
        if not users_data:
            await update.message.reply_text("No users yet.")
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "User Stats"

        center = Alignment(horizontal="center", vertical="center")
        bold_font_white = Font(bold=True, color="FFFFFF")
        bold_font_black = Font(bold=True, color="000000")
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'),
                             top=Side(style='thin'), bottom=Side(style='thin'))

        blue_fill = PatternFill(start_color="00B0F0", end_color="00B0F0", fill_type="solid")
        purple_fill = PatternFill(start_color="A47DB9", end_color="A47DB9", fill_type="solid")
        yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
        green_fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
        orange_fill = PatternFill(start_color="F79646", end_color="F79646", fill_type="solid")
        cyan_fill = PatternFill(start_color="00B0F0", end_color="00B0F0", fill_type="solid")

        row_num = 1

        for uid, data in users_data.items():
            username = data.get("username", "Unknown")
            search_count = data.get("search_count", 0)
            searches = data.get("searches", [])

            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2)
            ws.cell(row=row_num, column=1, value="User Name").fill = blue_fill
            ws.cell(row=row_num, column=1).alignment = center
            ws.cell(row=row_num, column=1).font = bold_font_white
            ws.cell(row=row_num, column=1).border = thin_border

            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
            ws.cell(row=row_num, column=3, value="User Id").fill = purple_fill
            ws.cell(row=row_num, column=3).alignment = center
            ws.cell(row=row_num, column=3).font = bold_font_white
            ws.cell(row=row_num, column=3).border = thin_border

            row_num += 1

            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2)
            ws.cell(row=row_num, column=1, value=username).border = thin_border
            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
            ws.cell(row=row_num, column=3, value=uid).border = thin_border

            row_num += 1

            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2)
            ws.cell(row=row_num, column=1, value="Total Searches").fill = yellow_fill
            ws.cell(row=row_num, column=1).alignment = center
            ws.cell(row=row_num, column=1).font = bold_font_black
            ws.cell(row=row_num, column=1).border = thin_border

            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
            ws.cell(row=row_num, column=3, value=search_count).fill = yellow_fill
            ws.cell(row=row_num, column=3).alignment = center
            ws.cell(row=row_num, column=3).font = bold_font_black
            ws.cell(row=row_num, column=3).border = thin_border

            row_num += 1

            ws.cell(row=row_num, column=1, value="SR").fill = green_fill
            ws.cell(row=row_num, column=2, value="Search Type").fill = orange_fill
            ws.cell(row=row_num, column=3, value="Search Query").fill = cyan_fill
            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)

            for col in range(1, 5):
                ws.cell(row=row_num, column=col).alignment = center
                ws.cell(row=row_num, column=col).font = bold_font_white
                ws.cell(row=row_num, column=col).border = thin_border

            row_num += 1

            for idx, s in enumerate(searches, start=1):
                ws.cell(row=row_num, column=1, value=idx).fill = green_fill
                ws.cell(row=row_num, column=1).alignment = center

                ws.cell(row=row_num, column=2, value=s["type"]).fill = orange_fill
                ws.cell(row=row_num, column=2).alignment = center

                ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
                ws.cell(row=row_num, column=3, value=s["query"]).fill = cyan_fill
                ws.cell(row=row_num, column=3).alignment = center

                for col in range(1, 5):
                    ws.cell(row=row_num, column=col).border = thin_border

                row_num += 1

            row_num += 2

        for col in range(1, 5):
            ws.column_dimensions[get_column_letter(col)].width = 20

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
