import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters.command import Command
from aiogram.types import Message
from aiohttp import web
from openai import AsyncOpenAI

# Получаем ключи с сервера
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# ==========================================
# 🛠 1. РАБОТЯГИ (Решают тест)
# Вставь сюда ID бесплатных моделей, которые будут думать над вопросом
# ==========================================
SOLVER_MODELS = [
    "stepfun/step-3.5-flash:free", # Например: "google/gemini-2.0-flash-exp:free"
    "arcee-ai/trinity-large-preview:free", # Например: "meta-llama/llama-3.3-70b-instruct:free"
    "z-ai/glm-4.5-air:free", # Например: "mistralai/mistral-7b-instruct:free"
    "qwen/qwen3-vl-235b-a22b-thinking",
    "openai/gpt-oss-120b:free"
]

# ==========================================
# ⚖️ 2. СУДЬЯ (Подводит итоги)
# Эта модель изучит ответы работяг и выдаст вердикт
# ==========================================
AGGREGATOR_MODEL = "ТВОЯgoogle/gemma-3-27b-it:free" # Советую поставить сюда "google/gemini-2.0-flash-exp:free"

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
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
    text = (f"Привет! Я умный консилиум.\n"
            f"У меня в подчинении {len(SOLVER_MODELS)} моделей-решателей и 1 судья.\n\n"
            f"Скинь мне тест, и я выдам тебе точный ответ по большинству голосов!")
    await message.answer(text)

# Функция: отправляем вопрос одному работяге
async def fetch_answer_from_model(model_id: str, question: str, index: int) -> str:
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "Ты решаешь тесты. Рассуждай кратко. В самом конце обязательно напиши свой выбор (например: 'ИТОГ: Вариант В')."},
                {"role": "user", "content": question}
            ],
            timeout=45.0
        )
        # Возвращаем ответ вместе с номером модели, чтобы Судья понимал, кто это написал
        return f"--- Ответ Модели {index} ---\n{response.choices[0].message.content}\n"
    except Exception as e:
        return f"--- Ответ Модели {index} ---\n❌ Ошибка связи с моделью.\n"

# Основной обработчик
@dp.message()
async def handle_test_question(message: Message):
    # Отправляем заглушку, чтобы пользователь знал, что процесс идет
    status_msg = await message.answer(f"🧠 Опрашиваю {len(SOLVER_MODELS)} нейросетей одновременно... Ожидайте.")
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # ЭТАП 1: Одновременный опрос всех моделей-работяг
    tasks = [fetch_answer_from_model(model_id, message.text, i+1) for i, model_id in enumerate(SOLVER_MODELS)]
    results = await asyncio.gather(*tasks)
    
    # Собираем все их ответы в один большой текст
    all_answers_text = "\n".join(results)
    
    await bot.edit_message_text(f"⚖️ Ответы получены! Судья ({AGGREGATOR_MODEL}) подсчитывает голоса...", 
                                chat_id=message.chat.id, 
                                message_id=status_msg.message_id)
    
    # ЭТАП 2: Передаем все ответы Судье для подведения итогов
    judge_prompt = (
        f"Ты — главный судья консилиума ИИ. Тебе дается исходный вопрос теста и сырые ответы нескольких нейросетей.\n"
        f"Твоя задача:\n"
        f"1. Изучить их ответы и кратко выписать списком, какой конкретный вариант выбрала каждая модель (букву или короткую фразу).\n"
        f"2. Подсчитать голоса.\n"
        f"3. Выдать финальный рекомендуемый ответ на основе большинства голосов.\n\n"
        f"ВОПРОС ТЕСТА:\n{message.text}\n\n"
        f"ОТВЕТЫ НЕЙРОСЕТЕЙ:\n{all_answers_text}"
    )

    try:
        judge_response = await client.chat.completions.create(
            model=AGGREGATOR_MODEL,
            messages=[
                {"role": "system", "content": "Ты строгий и объективный судья. Пиши только сухую выжимку по фактам, без лишней воды."},
                {"role": "user", "content": judge_prompt}
            ],
            timeout=30.0
        )
        final_verdict = judge_response.choices[0].message.content
        
        # Отправляем пользователю только красивый вердикт судьи
        await message.answer(f"🏆 **РЕЗУЛЬТАТ КОНСИЛИУМА** 🏆\n\n{final_verdict}")
        # Удаляем временное сообщение со статусом
        await bot.delete_message(chat_id=message.chat.id, message_id=status_msg.message_id)
        
    except Exception as e:
        await message.answer(f"Судья сломался! Ошибка: {str(e)}")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

