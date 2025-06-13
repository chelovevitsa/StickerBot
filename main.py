from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import json
import hashlib
import hmac
from config import BOT_TOKEN
from datetime import datetime
import asyncio
from telethon.sync import TelegramClient
from config import API_ID, API_HASH
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

USERS_FILE = "users.json"
STICKER_BOT_USERNAME = "sticker_bot"

class PaymentData(BaseModel):
    user_id: int
    access_hash: int  # доступен через WebApp initData
    stars: int
    init_data: str  # Добавляем init_data для проверки подписи
    action: str = "payment"  # По умолчанию - обычный платеж


def verify_telegram_data(init_data: str) -> bool:
    try:
        # Разбираем init_data
        data_check_string = init_data.split("&")
        received_hash = None
        data_dict = {}
        
        for item in data_check_string:
            if item.startswith("hash="):
                received_hash = item.split("=")[1]
            else:
                key, value = item.split("=")
                data_dict[key] = value
        
        # Создаем строку для проверки
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_dict.items()))
        
        # Создаем секретный ключ
        secret_key = hmac.new(
            "WebAppData".encode(),
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Вычисляем хеш
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == received_hash
    except Exception as e:
        logger.error(f"Ошибка при проверке подписи: {e}")
        return False


async def transfer_stars_to_userbot(user_id: int, stars: int):
    """Передача звёзд на аккаунт userbot'а через @sticker_bot"""
    try:
        async with TelegramClient("user_session", API_ID, API_HASH) as client:
            # Получаем диалог с @sticker_bot
            bot = await client.get_entity(STICKER_BOT_USERNAME)
            
            # Отправляем команду для передачи звёзд
            await client.send_message(bot, f"/transfer {user_id} {stars}")
            
            # Ждем ответа
            async for message in client.iter_messages(bot, limit=1):
                if "успешно" in message.text.lower():
                    logger.info(f"Успешная передача {stars} звёзд от пользователя {user_id}")
                    return True
                else:
                    logger.error(f"Ошибка при передаче звёзд: {message.text}")
                    raise Exception(f"Ошибка при передаче звёзд: {message.text}")
    except Exception as e:
        logger.error(f"Ошибка при передаче звёзд: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def save_user(user_id: int, access_hash: int, stars: int):
    try:
        logger.info(f"Попытка сохранения пользователя {user_id} с {stars} звёздами")
        try:
            with open(USERS_FILE, "r") as f:
                users = json.load(f)
                logger.info(f"Текущие пользователи: {users}")
        except FileNotFoundError:
            users = []
            logger.info("Файл users.json не найден, создаём новый")

        # Находим пользователя или создаем новую запись
        user_exists = False
        for user in users:
            if user["user_id"] == user_id:
                user["stars"] = user.get("stars", 0) + stars
                user["last_payment"] = datetime.now().isoformat()
                user_exists = True
                logger.info(f"Обновление существующего пользователя {user_id}")
                break

        if not user_exists:
            new_user = {
                "user_id": user_id,
                "access_hash": access_hash,
                "stars": stars,
                "first_payment": datetime.now().isoformat(),
                "last_payment": datetime.now().isoformat()
            }
            users.append(new_user)
            logger.info(f"Добавление нового пользователя: {new_user}")

        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
            logger.info(f"Пользователи успешно сохранены в {USERS_FILE}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя: {e}")
        raise


@app.post("/payment")
async def receive_payment(data: PaymentData):
    logger.info(f"Получен платеж от пользователя {data.user_id} на {data.stars} звёзд")
    
    if not verify_telegram_data(data.init_data):
        logger.error("Неверная подпись данных")
        raise HTTPException(status_code=400, detail="Invalid data signature")
    
    if data.action == "transfer_stars":
        # Передаем звёзды на аккаунт userbot'а
        await transfer_stars_to_userbot(data.user_id, data.stars)
    
    # Сохраняем информацию о пользователе
    save_user(data.user_id, data.access_hash, data.stars)
    
    return {
        "status": "ok",
        "message": "Stars transferred successfully" if data.action == "transfer_stars" else "User saved",
        "stars": data.stars
    }
