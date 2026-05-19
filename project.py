import json
import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

bot_token = "8591393121:AAH8Dwxmk9GolU1OgSURcVW9WqbD806u9T4"
data_file = "tasks.json"

# ---------- DATA ----------

def load_data():
    try:
        with open(data_file, "r") as file:
            return json.load(file)
    except Exception:
        return {}

def save_data(data):
    with open(data_file, "w") as file:
        json.dump(data, file, indent=2)

# ---------- COMMANDS ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot started.\n\n"
        "/add - add new task\n"
        "/list - show tasks\n"
        "/done <name or id> - mark done\n"
        "/cancel - cancel adding"
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["adding"] = "name"
    await update.message.reply_text("Enter task name:")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    tasks = data.get(user_id, [])

    if not tasks:
        await update.message.reply_text("No tasks")
        return

    message_text = ""
    for task_index, task_item in enumerate(tasks):
        status = "✅" if task_item["done"] else "❌"
        message_text += (
            f"{task_index + 1}. {task_item['name']}\n"
            f"📅 {task_item['date']} | ⚡ {task_item['priority']} | {status}\n\n"
        )
    await update.message.reply_text(message_text)

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data or not context.args:
        await update.message.reply_text("Usage: /done <task name or id>")
        return

    tasks = data[user_id]
    argument_text = " ".join(context.args)

    if argument_text.isdigit():
        task_index = int(argument_text) - 1
        if task_index >= len(tasks):
            await update.message.reply_text("Wrong ID")
            return
        tasks[task_index]["done"] = True
        save_data(data)
        await update.message.reply_text(f"✅ Done: {tasks[task_index]['name']}")
        return

    query_text = argument_text.lower()
    matched_indexes = [
        index for index, task_item in enumerate(tasks)
        if query_text in task_item["name"].lower()
    ]

    if not matched_indexes:
        await update.message.reply_text("No matching task found")
        return

    if len(matched_indexes) > 1:
        message_text = "Multiple matches:\n"
        for task_index in matched_indexes:
            message_text += f"{task_index}. {tasks[task_index]['name']}\n"
        message_text += "\nUse /done <id>"
        await update.message.reply_text(message_text)
        return

    task_index = matched_indexes[0]
    tasks[task_index]["done"] = True
    save_data(data)
    await update.message.reply_text(f"✅ Done: {tasks[task_index]['name']}")

# ---------- ADD FLOW ----------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.startswith("/") and "adding" in context.user_data:
        await update.message.reply_text("Finish adding or use /cancel")
        return

    if "adding" not in context.user_data:
        return

    current_step = context.user_data["adding"]
    message_text = update.message.text

    if current_step == "name":
        context.user_data["task_name"] = message_text
        context.user_data["adding"] = "date"
        await send_date_keyboard(update)
    elif current_step == "date_manual":
        try:
            datetime.datetime.strptime(message_text, "%Y-%m-%d")
            context.user_data["task_date"] = message_text
            context.user_data["adding"] = "priority"
            await send_priority_keyboard(update.effective_chat.id, context.bot)
        except ValueError:
            await update.message.reply_text("Invalid date. Use YYYY-MM-DD")

# ---------- KEYBOARDS ----------

async def send_date_keyboard(update):
    keyboard = [
        [
            InlineKeyboardButton("📅 Today", callback_data="date_today"),
            InlineKeyboardButton("📅 Tomorrow", callback_data="date_tomorrow"),
        ],
        [InlineKeyboardButton("✏️ Custom date", callback_data="date_custom")],
    ]
    await update.message.reply_text(
        "Choose task date:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def send_priority_keyboard(chat_id, bot):
    keyboard = [
        [
            InlineKeyboardButton("🟢 Low", callback_data="prio_low"),
            InlineKeyboardButton("🟡 Medium", callback_data="prio_medium"),
            InlineKeyboardButton("🔴 High", callback_data="prio_high"),
        ]
    ]
    await bot.send_message(
        chat_id=chat_id,
        text="Choose priority:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ---------- CALLBACKS ----------

async def date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_query = update.callback_query
    await callback_query.answer()
    today = datetime.date.today()

    if callback_query.data == "date_today":
        context.user_data["task_date"] = today.isoformat()
    elif callback_query.data == "date_tomorrow":
        context.user_data["task_date"] = (today + datetime.timedelta(days=1)).isoformat()
    elif callback_query.data == "date_custom":
        context.user_data["adding"] = "date_manual"
        await callback_query.edit_message_text("Enter date (YYYY-MM-DD):")
        return

    context.user_data["adding"] = "priority"
    await callback_query.edit_message_text("Date selected")
    await send_priority_keyboard(callback_query.message.chat_id, context.bot)

async def priority_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    callback_query = update.callback_query
    await callback_query.answer()

    priority_value = callback_query.data.replace("prio_", "")
    user_id = str(callback_query.from_user.id)

    task_item = {
        "name": context.user_data["task_name"],
        "date": context.user_data["task_date"],
        "priority": priority_value,
        "done": False,
    }

    data = load_data()
    data.setdefault(user_id, []).append(task_item)
    save_data(data)

    context.user_data.clear()
    await callback_query.edit_message_text("✅ Task added!")

# ---------- MAIN ----------

def main():
    application = ApplicationBuilder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("done", done))

    application.add_handler(CallbackQueryHandler(date_callback, pattern="^date_"))
    application.add_handler(CallbackQueryHandler(priority_callback, pattern="^prio_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    application.run_polling()

if __name__ == "__main__":
    main()