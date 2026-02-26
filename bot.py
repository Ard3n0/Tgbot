import asyncio
import logging
import os
import subprocess
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from aiohttp import web
from google import genai

# Получаем ключи
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID") # Твой ID из Render

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

client = genai.Client(api_key=GEMINI_API_KEY)
user_chats = {}

# --- ВЕБ-СЕРВЕР ---
async def handle_ping(request):
    return web.Response(text="Я не сплю! Бот работает.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {port}")
# ------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_chats[message.from_user.id] = client.aio.chats.create(model="gemini-2.0-flash")
    await message.answer("Привет! Я твой личный ИИ-ассистент на базе Gemini 2.0. Напиши мне что-нибудь!")

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_chats:
        user_chats[user_id] = client.aio.chats.create(model="gemini-2.0-flash")
        
    chat = user_chats[user_id]
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    try:
        response = await chat.send_message(message.text)
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"Я сломался! Вот текст ошибки:\n{str(e)}")

# --- ФУНКЦИЯ УВЕДОМЛЕНИЯ АДМИНА ---
async def on_startup():
    commit_msg = "Обновление применено (текст коммита не найден)"
    try:
        # Пытаемся вытащить сообщение последнего коммита через консоль
        commit_msg = subprocess.check_output(['git', 'log', '-1', '--pretty=%B']).decode('utf-8').strip()
    except Exception:
        pass
    
    if ADMIN_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🚀 **Сервер запущен и готов к работе!**\n\n📝 _Последний коммит:_\n{commit_msg}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление: {e}")

async def main():
    await start_web_server()
    await on_startup() # Отправляем уведомление при старте
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

