import asyncio
import os
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

# --- Настройки ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
# URL сайта, который мы получим от Render (для локального теста можно localhost)
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

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
        "Привет! 👋\n\nЭто бот знакомств <b>Ember</b>.\nНажми на кнопку ниже, чтобы начать 💕",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def run_bot():
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запускаем бота в фоне
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())
    # Запускаем Flask (это нужно для Render)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
