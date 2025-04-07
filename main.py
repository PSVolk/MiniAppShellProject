import os
import logging
import asyncio
import time
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from dotenv import load_dotenv
import tracemalloc

# Инициализация трекинга памяти
tracemalloc.start()

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

app = create_app()

# Импорт из telegram_bot
from telegram_bot import init_bot, run_polling, bot_manager

# Инициализация бота
bot_application = init_bot()


@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        return "Unauthorized", 403

    try:
        update = Update.de_json(request.get_json(), bot_manager.application.bot)
        bot_manager.put_update(update)
        return "OK", 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "Error", 500


def run_webhook_thread():
    """Запуск бота в отдельном потоке"""
    bot_manager.run_webhook(RENDER_HOSTNAME, PORT, WEBHOOK_SECRET)


if IS_RENDER:
    Thread(target=run_webhook_thread, daemon=True).start()

@app.route('/test-bot')
def test_bot():
    """Проверка состояния бота"""
    try:
        return jsonify({
            "status": "running",
            "queue_size": bot_manager.application.update_queue.qsize(),
            "webhook": IS_RENDER,
            "bot_initialized": hasattr(bot_manager, 'application')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/test-message')
def test_message():
    """Тест обработки сообщения"""
    try:
        test_update = {
            "update_id": 999999999,
            "message": {
                "message_id": 1,
                "chat": {"id": 12345, "type": "private"},
                "text": "/test",
                "date": int(time.time())
            }
        }
        update = Update.de_json(test_update, bot_manager.application.bot)
        bot_manager.application.update_queue.put_nowait(update)
        return jsonify({"status": "test message queued"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    """Эндпоинт для проверки работоспособности"""
    return jsonify({
        "status": "ok",
        "mode": "webhook" if IS_RENDER else "polling",
        "bot_ready": hasattr(bot_manager, 'application')
    }), 200


def run_flask():
    """Запуск Flask сервера"""
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=not IS_RENDER,
        use_reloader=False,
        threaded=True
    )
def run_webhook_wrapper():
    """Обертка для запуска webhook в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot_manager.run_webhook(
            RENDER_HOSTNAME, PORT, WEBHOOK_SECRET
        ))
    except Exception as e:
        logger.error(f"Webhook failed: {e}")
    finally:
        loop.close()

def main():
    if IS_RENDER:
        logger.info("Starting in WEBHOOK mode")

        # Явная инициализация обработчика очереди
        def start_webhook():
            asyncio.run(bot_manager.run_webhook(
                RENDER_HOSTNAME,
                PORT,
                WEBHOOK_SECRET
            ))

        Thread(target=start_webhook, daemon=True).start()
    else:
        logger.info("Starting in POLLING mode")
        Thread(target=run_polling, daemon=True).start()

    run_flask()


if __name__ == '__main__':
    try:
        logger.info("Starting application...")
        main()
    except Exception as e:
        logger.critical(f"Application failed: {str(e)}", exc_info=True)
    finally:
        logger.info("Application stopped")
