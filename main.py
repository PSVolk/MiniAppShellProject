import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from threading import Thread
import asyncio

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Проверка токена
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен!")

# Инициализация бота (исправленная строка)
try:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    logger.info("Бот успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    raise


# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Бот работает!')


# Регистрация обработчиков
application.add_handler(CommandHandler("start", start))


# Запуск бота (режим polling)
async def run_bot():
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Бот запущен в режиме polling")
    await application.idle()


# Запуск Flask
def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False)


# Главная функция
def main():
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем бота в основном потоке
    asyncio.run(run_bot())


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
