import os
import logging
from dotenv import load_dotenv
import asyncio
from threading import Thread
from flask import Flask
from telegram.ext import Application

# 1. Инициализация логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. Загрузка переменных окружения
load_dotenv()
logger.info("Переменные окружения загружены")

# 3. Конфигурация
IS_RENDER = os.getenv('IS_RENDER', 'false').lower() == 'true'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
RENDER_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")

# 4. Импорт и инициализация приложений
from app import create_app
from telegram_bot import run_bot

app = create_app()
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()


# 5. Маршруты Flask
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    if not IS_RENDER:
        return "Webhook mode disabled", 400

    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        return "Unauthorized", 403

    try:
        update = Update.de_json(request.get_json(), application.bot)
        Thread(target=lambda: asyncio.run(application.process_update(update))).start()
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}")
        return "Server Error", 500


# 6. Режимы работы
async def setup_webhook():
    """Настройка вебхука для Render"""
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(
        url=f"https://{RENDER_HOSTNAME}/webhook",
        secret_token=WEBHOOK_SECRET
    )
    logger.info(f"Вебхук установлен на https://{RENDER_HOSTNAME}/webhook")


def run_flask():
    """Запуск Flask сервера"""
    app.run(host='0.0.0.0', port=5000, debug=not IS_RENDER, use_reloader=False)


def run_async(coroutine):
    """Запуск асинхронной функции в новом event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(coroutine)


# 7. Главная функция
def main():
    if IS_RENDER:
        logger.info("Режим: Render (вебхуки)")
        # Настройка вебхука
        Thread(target=run_async, args=(setup_webhook(),), daemon=True).start()
    else:
        logger.info("Режим: локальный (polling)")
        # Запуск бота в отдельном потоке
        run_bot()

    # Запуск Flask в основном потоке
    run_flask()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
    finally:
        logger.info("Приложение завершает работу")
