import asyncio
import os
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# --- Flask для Render ---
app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "Bot is running!"

# --- Telegram Bot ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище: кто с кем сейчас общается
active_chats = {}

# Подключение к Neon
def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Проверяем, есть ли параметр chat_<id>
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("chat_"):
        partner_id = args[1].replace("chat_", "")
        active_chats[message.from_user.id] = partner_id
        await message.answer(
            f"💬 <b>Чат открыт!</b>\n\n"
            f"Напиши сообщение — я передам его собеседнику.\n"
            f"Чтобы выйти из чата, напиши /stop",
            parse_mode="HTML"
        )
        return

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

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    if message.from_user.id in active_chats:
        del active_chats[message.from_user.id]
        await message.answer("❌ Чат закрыт. Открой Ember, чтобы найти нового собеседника.")
    else:
        await message.answer("Ты не в чате. Открой Ember и найди мэтч!")

@dp.message()
async def forward_message(message: types.Message):
    user_id = message.from_user.id

    # Если пользователь в чате — пересылаем
    if user_id in active_chats:
        partner_id = active_chats[user_id]
        try:
            # Пересылаем собеседнику
            if message.text:
                await bot.send_message(
                    partner_id,
                    f"💬 <b>Сообщение:</b>\n\n{message.text}\n\n"
                    f"<i>Ответь мне, чтобы передать сообщение обратно</i>",
                    parse_mode="HTML"
                )
            elif message.photo:
                await bot.send_photo(
                    partner_id,
                    message.photo[-1].file_id,
                    caption=f"💬 {message.caption or ''}"
                )
            elif message.voice:
                await bot.send_voice(partner_id, message.voice.file_id)
            else:
                await message.answer("Я умею передавать только текст, фото и голосовые.")

            await message.answer("✅ Отправлено")
        except Exception as e:
            await message.answer(f"❌ Не удалось отправить: {e}")
    else:
        await message.answer("Нажми /start, чтобы открыть Ember 🔥")


async def run_bot():
    print("🤖 Бот Ember запущен...")
    await dp.start_polling(bot)


def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    asyncio.run(run_bot())
