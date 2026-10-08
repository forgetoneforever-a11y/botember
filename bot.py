import asyncio
import os
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

# --- Переменные окружения ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# --- Flask (для Render) ---
app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "Bot is running!"

# --- Telegram Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔥 Открыть Ember",
            web_app=WebAppInfo(url=SITE_URL)
        )]
    ])
    await message.answer(
        "Привет! 👋\n\n"
        "Это бот знакомств <b>Ember</b>.\n"
        "Нажми на кнопку ниже, чтобы начать 💕",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Помощь</b>\n\n"
        "/start — открыть Ember\n"
        "/help — эта справка",
        parse_mode="HTML"
    )

@dp.message()
async def echo(message: types.Message):
    await message.answer("Нажми /start, чтобы открыть Ember 🔥")

async def run_bot():
    print("🤖 Запускаю Telegram-бота...")
    await dp.start_polling(bot)

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    # Flask в отдельном потоке
    threading.Thread(target=start_flask, daemon=True).start()
    # Бот в главном потоке
    asyncio.run(run_bot())
