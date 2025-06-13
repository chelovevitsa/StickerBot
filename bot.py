from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN
import json
import os
import asyncio

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# URL твоего Web App, размещённый на Render (или другом HTTPS-хостинге)
WEBAPP_URL = "https://stickerbot-telegram.onrender.com/"  # ЗАМЕНИ на свой актуальный адрес

def load_sticker_data():
    try:
        with open("sticker_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

# Команда /start
@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💫 Вплати звезды",
            web_app=types.WebAppInfo(url=WEBAPP_URL)
        )]
    ])
    await message.answer(
        "Привет! Я помогу тебе поддержать проект и буду присылать новинки стикеров. "
        "Нажми на кнопку ниже, чтобы внести вклад звёздами 💫",
        reply_markup=keyboard
    )

@dp.message(Command("stickers"))
async def send_stickers(message: types.Message):
    # Проверяем, есть ли пользователь в списке оплативших
    try:
        with open("users.json", "r") as f:
            users = json.load(f)
            if not any(u["user_id"] == message.from_user.id for u in users):
                await message.answer("Сначала нужно внести вклад звёздами! Используйте /start")
                return
    except FileNotFoundError:
        await message.answer("Сначала нужно внести вклад звёздами! Используйте /start")
        return

    sticker_data = load_sticker_data()
    if sticker_data:
        await message.answer_sticker(
            sticker_data["document"]["id"],
            emoji=sticker_data["emoji"]
        )
    else:
        await message.answer("Извините, стикеры временно недоступны.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
