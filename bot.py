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

# Твой Telegram ID (админ)
ADMIN_ID = 8617178928

# Канал-спонсор
SPONSOR_CHANNEL = "emberbot_love"

# Ссылка на правила
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

active_chats = {}

# Хранилища для поддержки
pending_support = {}

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


# ============ ПОДПИСКА ============

async def is_subscribed(user_id):
    try:
        member = await bot.get_chat_member(chat_id=f"@{SPONSOR_CHANNEL}", user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        return False


def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=f"https://t.me/{SPONSOR_CHANNEL}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
        [InlineKeyboardButton(text="📜 Правила и конфиденциальность", url=RULES_URL)]
    ])


async def send_subscribe_message(message_or_callback):
    text = (
        "🔒 <b>Доступ закрыт</b>\n\n"
        "Чтобы пользоваться ботом <b>Ember</b>, "
        "нужно подписаться на наш канал.\n\n"
        f"📢 Канал: @{SPONSOR_CHANNEL}\n\n"
        "После подписки нажми <b>«Я подписался»</b> 👇"
    )
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(text, reply_markup=subscribe_keyboard(), parse_mode="HTML")
        except:
            await message_or_callback.message.answer(text, reply_markup=subscribe_keyboard(), parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=subscribe_keyboard(), parse_mode="HTML")


def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Открыть Ember", web_app=WebAppInfo(url=SITE_URL))],
        [InlineKeyboardButton(text="💬 Мои чаты", callback_data="list_chats")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="start_support")],
        [InlineKeyboardButton(text="📜 Правила и конфиденциальность", url=RULES_URL)]
    ])


# ============ КОМАНДЫ ============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    if not await is_subscribed(user_id):
        await send_subscribe_message(message)
        return

    pending_support.pop(user_id, None)

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


# ============ ПОДДЕРЖКА ============

@dp.message(Command("support"))
async def cmd_support(message: types.Message):
    if not await is_subscribed(message.from_user.id):
        await send_subscribe_message(message)
        return
    await start_support_flow(message)


@dp.callback_query(lambda c: c.data == "start_support")
async def cb_start_support(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ Ты не подписан!", show_alert=True)
        return
    await callback.answer()
    await start_support_flow(callback.message)


async def start_support_flow(message: types.Message):
    user_id = message.from_user.id
    pending_support[user_id] = "waiting"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_support")]
    ])

    await message.answer(
        "💬 <b>Поддержка Ember</b>\n\n"
        "Напиши своё сообщение одним текстом. Это может быть:\n\n"
        "• 💡 Идея или предложение\n"
        "• 🐞 Сообщение об ошибке\n"
        "• ❓ Вопрос\n"
        "• ⚠️ Жалоба на пользователя\n\n"
        "<i>Администрация прочитает и ответит.</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@dp.callback_query(lambda c: c.data == "cancel_support")
async def cb_cancel_support(callback: types.CallbackQuery):
    pending_support.pop(callback.from_user.id, None)
    await callback.answer("Отменено")
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer("💬 Поддержка отменена.")


@dp.callback_query(lambda c: c.data.startswith("reply_support_"))
async def cb_reply_support(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Это не для тебя", show_alert=True)
        return

    user_id = int(callback.data.replace("reply_support_", ""))
    pending_support[ADMIN_ID] = f"reply_to_{user_id}"

    await callback.answer()
    await callback.message.answer(
        f"✍️ Напиши ответ пользователю <code>{user_id}</code>:",
        parse_mode="HTML"
    )


# ============ ЧАТЫ ============

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
                "💔 У тебя пока нет мэтчей.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔥 Открыть Ember", web_app=WebAppInfo(url=SITE_URL))]
                ])
            )
            return

        keyboard_buttons = []
        for match in matches:
            partner_id, name, age = match
            prefix = "⭐ " if active_chats.get(user_id) == str(partner_id) else "💬 "
            keyboard_buttons.append([
                InlineKeyboardButton(text=f"{prefix}{name}, {age}", callback_data=f"open_chat_{partner_id}")
            ])

        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Закрыть активный чат", callback_data="close_chat")
        ])

        await message.answer(
            f"💬 <b>Твои чаты ({len(matches)})</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка: {e}")


@dp.callback_query(lambda c: c.data == "list_chats")
async def cb_list_chats(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ Ты не подписан!", show_alert=True)
        return
    await callback.answer()
    await cmd_chats(callback.message)


@dp.callback_query(lambda c: c.data.startswith("open_chat_"))
async def cb_open_chat(callback: types.CallbackQuery):
    if not await is_subscribed(callback.from_user.id):
        await callback.answer("❌ Ты не подписан!", show_alert=True)
        return

    partner_id = callback.data.replace("open_chat_", "")
    active_chats[callback.from_user.id] = partner_id
    partner_name = get_user_name(partner_id)

    await callback.answer("Чат открыт")
    await callback.message.answer(
        f"💬 <b>Чат с {partner_name} открыт!</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Все мои чаты", callback_data="list_chats")],
            [InlineKeyboardButton(text="❌ Закрыть чат", callback_data="close_chat")]
        ]),
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
    pending_support.pop(message.from_user.id, None)
    if message.from_user.id in active_chats:
        del active_chats[message.from_user.id]
        await message.answer("❌ Чат закрыт.")
    else:
        await message.answer("У тебя нет активного чата. Используй /chats.")


# ============ ОБРАБОТКА СООБЩЕНИЙ ============

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id

    # 1. Админ отвечает на поддержку
    if user_id == ADMIN_ID and str(pending_support.get(ADMIN_ID, "")).startswith("reply_to_"):
        target_user_id = int(pending_support[ADMIN_ID].replace("reply_to_", ""))
        pending_support.pop(ADMIN_ID, None)

        try:
            await bot.send_message(
                target_user_id,
                f"📬 <b>Ответ от поддержки:</b>\n\n{message.text}\n\n"
                f"<i>Если нужно — напиши снова через /support</i>",
                parse_mode="HTML"
            )
            await message.answer("✅ Ответ отправлен пользователю!")
        except Exception as e:
            await message.answer(f"❌ Не удалось отправить: {e}")
        return

    # 2. Проверка подписки
    if not await is_subscribed(user_id):
        await send_subscribe_message(message)
        return

    # 3. Пользователь пишет в поддержку
    if user_id in pending_support and pending_support[user_id] == "waiting":
        pending_support.pop(user_id, None)

        user_name = await get_telegram_name(user_id)
        text = message.text or "[не текст]"

        try:
            await bot.send_message(
                ADMIN_ID,
                f"📬 <b>Новое сообщение в поддержку</b>\n\n"
                f"👤 <b>Имя:</b> {user_name}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"🔗 <a href='tg://user?id={user_id}'>Открыть профиль</a>\n\n"
                f"💬 <b>Текст:</b>\n{text}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✍️ Ответить",
                        callback_data=f"reply_support_{user_id}"
                    )]
                ])
            )
            await message.answer(
                "✅ <b>Сообщение отправлено!</b>\n\n"
                "Поддержка прочитает его и ответит в ближайшее время.\n\n"
                "Спасибо, что делаешь Ember лучше 💜"
            )
        except Exception as e:
            print(f"Ошибка отправки админу: {e}")
            await message.answer("❌ Не удалось отправить. Попробуй позже.")
        return

    # 4. Обычный чат
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
            "Выбери действие:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Мои чаты", callback_data="list_chats")],
                [InlineKeyboardButton(text="💬 Поддержка", callback_data="start_support")],
                [InlineKeyboardButton(text="🔥 Открыть Ember", web_app=WebAppInfo(url=SITE_URL))]
            ])
        )


async def get_telegram_name(user_id):
    try:
        chat = await bot.get_chat(user_id)
        if chat.username:
            return f"@{chat.username}"
        elif chat.first_name:
            return chat.first_name
    except:
        pass
    return f"ID {user_id}"


async def run_bot():
    print("🤖 Бот Ember запущен...")
    print(f"👑 Админ ID: {ADMIN_ID}")

    await bot.set_my_commands([
        types.BotCommand(command="/start", description="🚀 Открыть Ember"),
        types.BotCommand(command="/chats", description="💬 Мои чаты"),
        types.BotCommand(command="/support", description="💬 Поддержка"),
        types.BotCommand(command="/rules", description="📜 Правила"),
        types.BotCommand(command="/stop", description="❌ Закрыть чат"),
    ])

    await dp.start_polling(bot)


def start_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=start_flask, daemon=True).start()
    asyncio.run(run_bot())
