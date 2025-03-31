import os
import logging
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from dotenv import load_dotenv

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
logger.info("Переменные окружения загружены")

# Конфигурация
IS_RENDER = os.getenv('IS_RENDER', 'false').lower() == 'true'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
RENDER_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')
PORT = int(os.getenv('PORT', '5000'))

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")

# Инициализация Flask приложения
from app import create_app
app = Flask(__name__)
app = create_app()

# Импорт из telegram_bot
from telegram_bot import init_bot, run_polling

# Инициализация бота
bot_application = init_bot()


# def setup_webhook():
#     """Настройка вебхука для Render"""
#     import asyncio
#
#     async def _setup():
#         await bot_application.initialize()
#         await bot_application.start()
#         await bot_application.bot.set_webhook(
#             url=f"https://{RENDER_HOSTNAME}/webhook",
#             secret_token=WEBHOOK_SECRET
#         )
#         logger.info(f"Вебхук установлен на https://{RENDER_HOSTNAME}/webhook")
#
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     try:
#         loop.run_until_complete(_setup())
#     finally:
#         loop.close()

# @app.route('/')
# def home():
#     """Корневой маршрут для проверки работы Flask"""
#     return jsonify({
#         "status": "running",
#         "service": "Motomaster Bot",
#         "mode": "webhook" if IS_RENDER else "polling"
#     })


# @app.route('/webhook', methods=['POST'])
# def telegram_webhook():
#     if not IS_RENDER:
#         return "Webhook mode disabled", 400

#     if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
#         return "Unauthorized", 403

#     try:
#         update = Update.de_json(request.get_json(), bot_application.bot)
#         bot_application.update_queue.put(update)
#         return "OK", 200
#     except Exception as e:
#         logger.error(f"Ошибка обработки вебхука: {e}")
#         return "Server Error", 500

@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    logger.info("Получен запрос вебхука")
    if not IS_RENDER:
        logger.warning("Попытка использовать webhook в не-Render режиме")
        return "Webhook mode disabled", 400

    secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret_token != WEBHOOK_SECRET:
        logger.warning(f"Неверный секретный токен: {secret_token}")
        return "Unauthorized", 403

    try:
        update_data = request.get_json()
        logger.debug(f"Данные обновления: {update_data}")
        update = Update.de_json(update_data, bot_application.bot)
        bot_application.update_queue.put(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки вебхука: {e}", exc_info=True)
        return "Server Error", 500

# def setup_webhook():
#     """Настройка вебхука для Render"""
#     import asyncio
#
#     async def _setup():
#         await bot_application.initialize()
#         await bot_application.start()
#         await bot_application.bot.set_webhook(
#             url=f"https://{RENDER_HOSTNAME}/webhook",
#             secret_token=WEBHOOK_SECRET
#         )
#         logger.info(f"Вебхук установлен на https://{RENDER_HOSTNAME}/webhook")
#
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     try:
#         loop.run_until_complete(_setup())
#     finally:
#         loop.close()

def setup_webhook():
    """Настройка вебхука для Render"""
    import asyncio

    async def _setup():
        try:
            await bot_application.initialize()
            await bot_application.start()
            webhook_url = f"https://{RENDER_HOSTNAME}/webhook"
            logger.info(f"Попытка установить вебхук на: {webhook_url}")
            result = await bot_application.bot.set_webhook(
                url=webhook_url,
                secret_token=WEBHOOK_SECRET
            )
            logger.info(f"Вебхук установлен: {result}")
            # Проверка текущего вебхука
            webhook_info = await bot_application.bot.get_webhook_info()
            logger.info(f"Информация о вебхуке: {webhook_info}")
        except Exception as e:
            logger.error(f"Ошибка при настройке вебхука: {e}")
            raise

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_setup())
    except Exception as e:
        logger.error(f"Ошибка в event loop: {e}")
    finally:
        loop.close()
        logger.info("Настройка вебхука завершена")

def run_flask():
    """Запуск Flask сервера"""
    app.run(host='0.0.0.0', port=PORT, debug=not IS_RENDER, use_reloader=False, threaded=True)


def main():
    if IS_RENDER:
        logger.info("Режим: Render (вебхуки)")
        setup_webhook()
    else:
        logger.info("Режим: локальный (polling)")
        # Запуск polling в отдельном потоке
        bot_thread = Thread(target=run_polling, daemon=True)
        bot_thread.start()

    # Запуск Flask в основном потоке
    run_flask()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
    finally:
        logger.info("Приложение завершает работу")
