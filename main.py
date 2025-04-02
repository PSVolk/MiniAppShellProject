import os
import logging
import asyncio
import time
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from dotenv import load_dotenv
import tracemalloc
from telegram_bot import bot_manager, run_webhook_sync

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

app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    if not IS_RENDER:
        return "Webhook mode disabled", 400

    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != WEBHOOK_SECRET:
        return "Unauthorized", 403

    try:
        update = Update.de_json(request.get_json(), bot_manager.application.bot)
        bot_manager.put_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return "Server Error", 500


@app.route('/test-bot')
def test_bot():
    """Проверка состояния бота"""
    try:
        return jsonify({
            "status": "running",
            "webhook": IS_RENDER,
            "bot_initialized": hasattr(bot_manager, 'application')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/healthcheck')
def healthcheck():
    """Проверка работоспособности сервера"""
    return jsonify({"status": "ok", "mode": "webhook" if IS_RENDER else "polling"}), 200


def run_flask():
    """Запуск Flask сервера"""
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=not IS_RENDER,
        use_reloader=False,
        threaded=True
    )


if __name__ == '__main__':
    try:
        if IS_RENDER:
            logger.info("Starting in WEBHOOK mode")
            # Запуск webhook в отдельном потоке
            Thread(target=run_webhook_sync, args=(
                RENDER_HOSTNAME,
                PORT,
                WEBHOOK_SECRET
            ), daemon=True).start()

        run_flask()
    except Exception as e:
        logger.critical(f"Application failed: {e}", exc_info=True)
