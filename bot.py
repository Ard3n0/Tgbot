import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.types import Message
from aiohttp import web
import google.generativeai as genai

# Получаем ключи из настроек Render (переменные окружения)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Словарь для хранения истории диалогов (чтобы бот помнил, о чем вы говорили)
user_chats = {}

# --- ВЕБ-СЕРВЕР ДЛЯ ОБМАНА RENDER ---
async def handle_ping(request):
    return web.Response(text="Я не сплю! Бот работает.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render сам выдает нужный порт через переменную PORT
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер-обманка запущен на порту {port}")
# ------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Создаем новую сессию чата при команде /start
    user_chats[message.from_user.id] = model.start_chat(history=[])
    await message.answer("Привет! Я твой личный ИИ-ассистент на базе Gemini. Напиши мне что-нибудь!")

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    
    # Если истории нет, создаем новую
    if user_id not in user_chats:
        user_chats[user_id] = model.start_chat(history=[])
        
    chat = user_chats[user_id]
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        # Отправляем сообщение в чат с учетом истории
        response = await chat.send_message_async(message.text)
        await message.answer(response.text)
    except Exception as e:
        # Теперь бот будет жаловаться тебе лично!
        await message.answer(f"Я сломался! Вот текст ошибки:\n{str(e)}")

async def main():
    # Запускаем веб-сервер и бота одновременно
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())