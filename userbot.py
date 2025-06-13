import json
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerUser
from config import API_ID, API_HASH, BOT_TOKEN
import logging
import re
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='userbot.log'
)
logger = logging.getLogger(__name__)

# Файлы с данными
USERS_FILE = "users.json"
STICKER_FILE = "sticker_data.json"

# Константы
STICKER_BOT_USERNAME = "sticker_bot"
MIN_STARS_REQUIRED = 1000  # Минимальное количество звёзд для покупки стикера

# Создаем сессию в памяти
session = StringSession()

async def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

async def load_sticker():
    try:
        with open(STICKER_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

async def get_total_stars(client):
    """Получение баланса звёзд"""
    try:
        bot = await client.get_entity(STICKER_BOT_USERNAME)
        await client.send_message(bot, "/balance")
        
        async for message in client.iter_messages(bot, limit=1):
            if "баланс" in message.text.lower():
                # Извлекаем число из текста
                stars = re.search(r'\d+', message.text)
                if stars:
                    return int(stars.group())
        return 0
    except Exception as e:
        logger.error(f"Ошибка при получении баланса: {e}")
        return 0

async def transfer_stars(client, from_user_id, stars):
    """Передача звёзд от пользователя к боту через @sticker_bot"""
    try:
        # Получаем общее количество звёзд
        total_stars = await get_total_stars(client)
        
        # Проверяем, достаточно ли звёзд
        if total_stars < stars:
            logger.error(f"Недостаточно звёзд. Требуется: {stars}, Доступно: {total_stars}")
            return False

        # Получаем диалог с @sticker_bot
        bot = await client.get_entity(STICKER_BOT_USERNAME)
        
        # Отправляем команду для передачи звёзд
        await client.send_message(bot, f"/transfer {from_user_id} {stars}")
        
        # Ждем подтверждения
        async for message in client.iter_messages(bot, limit=1):
            if "успешно" in message.text.lower():
                logger.info(f"Успешно передано {stars} звёзд пользователю {from_user_id}")
                return True
            else:
                logger.error(f"Ошибка при передаче звёзд: {message.text}")
                return False
                
    except Exception as e:
        logger.error(f"Ошибка при передаче звёзд: {e}")
        return False

async def save_sticker_data(sticker_data):
    """Сохранение информации о стикере"""
    try:
        with open(STICKER_FILE, "w") as f:
            json.dump(sticker_data, f, indent=2)
        logger.info("Информация о стикере сохранена")
    except Exception as e:
        logger.error(f"Ошибка при сохранении стикера: {e}")

async def monitor_stickers():
    """Мониторинг новых стикеров"""
    try:
        async with TelegramClient(session, API_ID, API_HASH) as client:
            logger.info("Userbot запущен")
            
            while True:
                try:
                    # Получаем диалог с @sticker_bot
                    bot = await client.get_entity(STICKER_BOT_USERNAME)
                    
                    # Получаем последние сообщения
                    async for message in client.iter_messages(bot, limit=10):
                        if message.sticker:
                            # Проверяем баланс звёзд
                            stars = await get_total_stars(client)
                            if stars >= 1000:  # Минимальное количество звёзд для покупки
                                # Покупаем стикер
                                await client.send_message(bot, "/buy")
                                
                                # Сохраняем информацию о стикере
                                sticker_data = {
                                    "document": {
                                        "id": message.sticker.id,
                                        "access_hash": message.sticker.access_hash
                                    },
                                    "emoji": message.sticker.emoji or "⭐️"
                                }
                                await save_sticker_data(sticker_data)
                                logger.info(f"Новый стикер куплен и сохранен")
                            else:
                                logger.info(f"Недостаточно звёзд для покупки стикера. Текущий баланс: {stars}")
                    
                    # Ждем перед следующей проверкой
                    await asyncio.sleep(60)  # Проверяем каждую минуту
                    
                except Exception as e:
                    logger.error(f"Ошибка в мониторинге: {e}")
                    await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой
    except Exception as e:
        logger.error(f"Критическая ошибка в monitor_stickers: {e}")
        raise

async def send_sticker_to_users(client):
    users = await load_users()
    sticker_data = await load_sticker()

    if not sticker_data:
        logger.error("Не найден файл с данными стикера")
        return

    for user in users:
        try:
            user_id = user["user_id"]
            access_hash = user["access_hash"]
            stars = user.get("stars", 0)

            # Проверяем, достаточно ли звёзд для получения стикера
            if stars < 1:
                logger.info(f"У пользователя {user_id} недостаточно звёзд")
                continue

            # Передаем звёзды от пользователя к боту
            if await transfer_stars(client, user_id, 1):
                peer = InputPeerUser(user_id=user_id, access_hash=access_hash)
                
                logger.info(f"Отправляем стикер {sticker_data['emoji']} пользователю {user_id}")
                # Отправляем стикер используя новый метод
                await client.send_file(
                    peer,
                    sticker_data["document"],
                    file_type="sticker"
                )

                # Обновляем количество звёзд у пользователя
                user["stars"] -= 1
                with open(USERS_FILE, "w") as f:
                    json.dump(users, f, indent=2)

        except Exception as e:
            logger.error(f"Ошибка для user {user_id}: {e}")

async def main():
    try:
        async with TelegramClient(session, API_ID, API_HASH) as client:
            # Запускаем мониторинг новых стикеров
            await monitor_stickers()
            # Отправляем стикеры пользователям
            await send_sticker_to_users(client)
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
