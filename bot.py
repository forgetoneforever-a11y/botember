import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import BOT_TOKEN, SITE_URL

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


@dp.message()
async def echo(message: types.Message):
    await message.answer("Нажми /start, чтобы открыть Ember 🔥")


async def main():
    print("Бот Ember запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
