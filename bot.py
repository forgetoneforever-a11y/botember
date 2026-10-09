import asyncio
import os
import threading
import time
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from dotenv import load_dotenv
import psycopg2

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL")

# Канал-спонсор (без @)
SPONSOR_CHANNEL = "emberbot_love"

# Ссылка на правила и политику конфиденциальности
RULES_URL = "https://telegra.ph/Pravila-ispolzovaniya-Ember-10-09"

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

# Кэш имён
_name_cache = {}
_NAME_CACHE_TTL = 300


def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def get_user_name(user_id):
    now = time.time()
    cached = _name_cache.get(str(user_id))
    if cached and now - cached["time"] < _NAME_CACHE_TTL:
        return cached["name"]

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, age FROM users WHERE telegram_id = %s", (str(user_id),))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            name = f"{result[0]}, {result[1]}"
            _name_cache[str(user_id)] = {"name": name, "time": now}
            return name
    except Exception as e:
        print(f"Ошибка: {e}")
    return f"Пользователь {user_id}"


# ============ ПРОВЕРКА ПОДПИСКИ ============

async def is_subscribed(user_id):
    """Проверка подписки на канал-спонсор"""
    try:
        print(f"🔍 Проверка подписки: user={user_id} на @{SPONSOR_CHANNEL}")
        member = await bot.get_chat_member(chat_id=f"@{SPONSOR_CHANNEL}", user_id=user_id)
        print(f"✅ Статус: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"❌ Ошибка проверки: {type(e).__name__}: {e}")
        return False


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Подписаться на канал",
            url=f"https://t.me/{SPONSOR_CHANNEL}"
        )],
        [InlineKeyboardButton(
            text="✅ Я подписался",
            callback_data="check_subscription"
        )],
        [InlineKeyboardButton(
            text="📜 Правила и конфиденциальность",
            url=RULES_URL
        )]
    ])


async def send_subscribe_message(message_or_callback):
    text = (
        "🔒 <b>Доступ закрыт</b>\n\n"
        "Чтобы пользоваться ботом <b>Ember</b>, "
        "нужно подписаться на наш канал.\n\n"
        f"📢 Канал: @{SPONSOR_CHANNEL}\n\n"
        "После подписки нажми <b>«Я подписался»</b> 👇\n\n"
        "📜 <i>Используя бота, ты соглашаешься с правилами и политикой конфиденциальности.</i>"
    )

    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(
                text,
                reply_markup=subscribe_keyboard(),
                parse_mode="HTML"
            )
        except:
            await message_or_callback.message.answer(
                text,
                reply_markup=subscribe_keyboard(),
                parse_mode="HTML"
            )
    else:
        await message_or_callback.answer(
            text,
            reply_markup=subscribe_keyboard(),
            parse_mode="HTML"
        )


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔥 Открыть Ember",
            web_app=WebAppInfo(url=SITE_URL)
        )],
        [InlineKeyboardButton(
            text="💬 Мои чаты",
            callback_data="list_chats"
        )],
        [InlineKeyboardButton(
            text="📜 Правила и конфиденциальность",
            url=RULES_URL
        )]
    ])


# ============ КОМАНДЫ ============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    if not await is_subscribed(user_id):
        await send_subscribe_message(message)
        return

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("chat_"):
        partner_id = args[1].replace("chat_", "")
        active_chats[user_id] = partner_id
        partner_name = get_user_name(partner_id)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Закрыть чат", callback_data="close_chat")],
            [InlineKeyboardButton(text="💬 Все мои чаты", callback_data="list_chats")]
        ])

        await message.answer(
            f"💬 <b>Чат с {partner_name} открыт!</b>\n\n"
            f"Напиши сообщение — я передам его.\n"
            f"Переключиться на другой чат — /chats",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    await message.answer(
        "Привет! 👋\n\n"
        "Это бот знакомств <b>Ember</b>.\n"
        "Нажми на кнопку ниже, чтобы начать 💕",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )


@dp.message(Command("rules"))
async def cmd_rules(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await send_subscribe_message(message)
        return

    await message.answer(
        "📜 <b>Правила и конфиденциальность Ember</b>\n\n"
        f"Читай тут: {RULES_URL}\n\n"
        "<i>Используя бота, ты соглашаешься с этими правилами.</i>",
        parse_mode="HTML",
        disable_web_page_preview=False
    )


@dp.callback_query(lambda c: c.data == "check_subscription")
async def cb_check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    if await is_subscribed(user_id):
        await callback.answer("✅ Спасибо за подписку!")

        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\n"
            "Добро пожаловать в <b>Ember</b> 💕\n"
            "Нажми на кнопку ниже, чтобы начать:",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ты ещё не подписался!", show_alert=True)
        await send_subscribe_message(callback)


@dp.message(Command("chats"))
async def cmd_chats(message: types.Message):
    user_id = message.from_user.id

    if not await is_subscribed(user_id):
        await send_subscribe_message(message)
        return

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.telegram_id, u.name, u.age
            FROM users u
            WHERE u.telegram_id IN (
                SELECT CASE 
                    WHEN l1.from_user = %s THEN l1.to_user
                    ELSE l1.from_user
                END
                FROM likes l1
                INNER JOIN likes l2 
                    ON l1.from_user = l2.to_user 
                    AND l1.to_user = l2.from_user
                WHERE (l1.from_user = %s OR l1.to_user = %s)
                    AND l1.is_like = TRUE 
                    AND l2.is_like = TRUE
            )
        """, (str(user_id), str(user_id), str(user_id)))
        matches = cur.fetchall()
        cur.close()
        conn.close()

        if not matches:
            await message.answer(
                "💔 У тебя пока нет мэтчей.\n\n"
                "Открой Ember и найди кого-то!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="🔥 Открыть Ember",
                        web_app=WebAppInfo(url=SITE_URL)
                    )]
                ])
            )
            return

        keyboard_buttons = []
        for match in matches:
            partner_id, name, age = match
            prefix = "⭐ " if active_chats.get(user_id) == str(partner_id) else "💬 "
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"{prefix}{name}, {age}",
                    callback_data=f"open_chat_{partner_id}"
                )
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Закрыть активный чат", callback_data="close_chat")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            f"💬 <b>Твои чаты ({len(matches)})</b>\n\n"
            "Выбери, с кем хочешь поговорить:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка: {e}")
        await message.answer("❌ Ошибка загрузки чатов")


@dp.callback_query(lambda c: c.data == "list_chats")
async def cb_list_chats(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ Ты не подписан на канал!", show_alert=True)
        return
    await callback.answer()
    await cmd_chats(callback.message)


@dp.callback_query(lambda c: c.data.startswith("open_chat_"))
async def cb_open_chat(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ Ты не подписан на канал!", show_alert=True)
        return

    partner_id = callback.data.replace("open_chat_", "")
    active_chats[callback.from_user.id] = partner_id
    partner_name = get_user_name(partner_id)

    await callback.answer("Чат открыт")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Все мои чаты", callback_data="list_chats")],
        [InlineKeyboardButton(text="❌ Закрыть чат", callback_data="close_chat")]
    ])

    await callback.message.answer(
        f"💬 <b>Чат с {partner_name} открыт!</b>\n\n"
        f"Пиши сообщение — я передам.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "close_chat")
async def cb_close_chat(callback: types.CallbackQuery):
    if callback.from_user.id in active_chats:
        del active_chats[callback.from_user.id]
        await callback.answer("Чат закрыт")
        await callback.message.answer("❌ Чат закрыт.")
    else:
        await callback.answer("Нет активного чата")


@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await send_subscribe_message(message)
        return

    if message.from_user.id in active_chats:
        del active_chats[message.from_user.id]
        await message.answer("❌ Чат закрыт. Открой /chats чтобы выбрать другой.")
    else:
        await message.answer("У тебя нет активного чата. Используй /chats.")


@dp.message()
async def forward_message(message: types.Message):
    user_id = message.from_user.id

    if not await is_subscribed(user_id):
        await send_subscribe_message(message)
        return

    if user_id in active_chats:
        partner_id = active_chats[user_id]
        partner_name = get_user_name(user_id)

        try:
            if message.text:
                await bot.send_message(
                    partner_id,
                    f"💬 <b>Сообщение от {partner_name}:</b>\n\n{message.text}\n\n"
                    f"<i>Ответь мне, чтобы передать сообщение обратно</i>",
                    parse_mode="HTML"
                )
            elif message.photo:
                await bot.send_photo(
                    partner_id,
                    message.photo[-1].file_id,
                    caption=f"💬 <b>Фото от {partner_name}</b>\n{message.caption or ''}",
                    parse_mode="HTML"
                )
            elif message.voice:
                await bot.send_voice(partner_id, message.voice.file_id)
            else:
                await message.answer("Я умею передавать только текст, фото и голосовые.")
                return

            await message.answer("✅ Отправлено")
        except Exception as e:
            error_text = str(e)
            if "chat not found" in error_text:
                await message.answer(
                    "❌ Не удалось отправить.\n\n"
                    "Твой собеседник ещё не запускал бота @Emberanon_bot."
                )
            else:
                await message.answer(f"❌ Ошибка: {error_text}")
    else:
        await message.answer(
            "Выбери чат, чтобы написать сообщение:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Мои чаты", callback_data="list_chats")],
                [InlineKeyboardButton(
                    text="🔥 Открыть Ember",
                    web_app=WebAppInfo(url=SITE_URL)
                )]
            ])
        )


async def run_bot():
    print("🤖 Бот Ember запущен...")

    await bot.set_my_commands([
        types.BotCommand(command="/start", description="🚀 Открыть Ember"),
        types.BotCommand(command="/chats", description="💬 Мои чаты"),
        types.BotCommand(command="/rules", description="📜 Правила и конфиденциальность"),
        types.BotCommand(command="/stop", description="❌ Закрыть активный чат"),
    ])

    await dp.start_polling(bot)


def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    asyncio.run(run_bot())
