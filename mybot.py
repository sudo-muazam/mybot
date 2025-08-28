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

            # Format record
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
        await update.message.reply_text(f"❌ Error occurred: {e}")
        await send_developer_info(update)

# ====== Developer info ======
async def send_developer_info(update: Update):
    developer_msg = "🤖 Bot developed by Muazam Ali\n📞 WhatsApp: "
    await update.message.reply_text(developer_msg)
    await update.message.reply_text("Choose your search type:", reply_markup=get_search_inline_keyboard())
    user_state.pop(update.effective_chat.id, None)

# ====== /stats Command (Styled Excel) ======
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

        # Styling setup
        center = Alignment(horizontal="center", vertical="center")
        bold_font_white = Font(bold=True, color="FFFFFF")
        bold_font_black = Font(bold=True, color="000000")
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'),
                             top=Side(style='thin'), bottom=Side(style='thin'))

        # Color fills
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

            # Row 1: User Name / User Id
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

            # Row: Total Searches
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=2)
            ws.cell(row=row_num, column=1, value="Total No OF Searches").fill = yellow_fill
            ws.cell(row=row_num, column=1).alignment = center
            ws.cell(row=row_num, column=1).font = bold_font_black
            ws.cell(row=row_num, column=1).border = thin_border

            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
            ws.cell(row=row_num, column=3, value=search_count).fill = yellow_fill
            ws.cell(row=row_num, column=3).alignment = center
            ws.cell(row=row_num, column=3).font = bold_font_black
            ws.cell(row=row_num, column=3).border = thin_border

            row_num += 1

            # Headers for search data
            ws.cell(row=row_num, column=1, value="SR").fill = green_fill
            ws.cell(row=row_num, column=2, value="Search Type").fill = orange_fill
            ws.cell(row=row_num, column=3, value="Search Query").fill = cyan_fill
            ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)

            for col in range(1, 5):
                ws.cell(row=row_num, column=col).alignment = center
                ws.cell(row=row_num, column=col).font = bold_font_white
                ws.cell(row=row_num, column=col).border = thin_border

            row_num += 1

            # Search entries
            for idx, s in enumerate(searches, start=1):
                ws.cell(row=row_num, column=1, value=idx).fill = green_fill
                ws.cell(row=row_num, column=1).alignment = center

                search_type = "Number" if s["type"] == "number" else "Cnic"
                ws.cell(row=row_num, column=2, value=search_type).fill = orange_fill
                ws.cell(row=row_num, column=2).alignment = center

                ws.merge_cells(start_row=row_num, start_column=3, end_row=row_num, end_column=4)
                ws.cell(row=row_num, column=3, value=s["query"]).fill = cyan_fill
                ws.cell(row=row_num, column=3).alignment = center

                for col in range(1, 5):
                    ws.cell(row=row_num, column=col).border = thin_border

                row_num += 1

            row_num += 2  # Space between users

        # Adjust column widths
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
