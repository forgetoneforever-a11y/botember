cd $HOME\Desktop\ember\bot

@'
import asyncio
import os
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# --- Flask для Render ---
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
    print("🤖 Запускаю Telegram-бота...")
    await dp.start_polling(bot)

def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    import threading
    threading.Thread(target=start_flask, daemon=True).start()
    
    # Запускаем бота в главном потоке (это правильно для Python 3.12)
    asyncio.run(run_bot())
'@ | Out-File -FilePath bot.py -Encoding UTF8
