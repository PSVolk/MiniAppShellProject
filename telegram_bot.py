import asyncio
import hashlib
import requests
import sqlite3
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)
from dotenv import load_dotenv
import os

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

SERVICES = {
    "🛢️ Замена масла": "oil_change",
    "⛓️ Регулировка цепи": "chain_adjustment",
    "⚙️ Ремонт двигателя": "engine_repair",
    "🆘 Помощь на дороге": "road_assistance"
}

CHOOSING_SERVICE, ENTERING_NAME, ENTERING_PHONE, ENTERING_PASSWORD = range(4)

# Клавиатуры
start_keyboard = ReplyKeyboardMarkup([['/start']], resize_keyboard=True, is_persistent=True)
services_keyboard = ReplyKeyboardMarkup(
    [[service] for service in SERVICES.keys()],
    resize_keyboard=True,
    one_time_keyboard=False
)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_or_get_client(username: str, phone: str, password: str) -> int:
    """Регистрирует нового клиента или возвращает существующего"""
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()

        # Проверяем существующего клиента
        cursor.execute(
            'SELECT id FROM clients WHERE username = ? OR phone = ?',
            (username, phone)
        )
        if existing := cursor.fetchone():
            return existing[0]

        # Регистрируем нового клиента
        cursor.execute(
            'INSERT INTO clients (username, phone, password) VALUES (?, ?, ?)',
            (username, phone, hash_password(password))
        )
        conn.commit()
        return cursor.lastrowid


def save_order_to_db(user_id: int, service: str) -> int:
    """Сохраняет заказ в БД и возвращает его ID"""
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO orders (user_id, service) VALUES (?, ?)',
            (user_id, service)
        )
        conn.commit()
        return cursor.lastrowid


def send_to_telegram(chat_id: str, message: str):
    """Отправляет сообщение в Telegram"""
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            },
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Добро пожаловать в Мотомастер! Выберите услугу:",
        reply_markup=services_keyboard
    )
    return CHOOSING_SERVICE


async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service = update.message.text
    if service not in SERVICES:
        await update.message.reply_text(
            "⚠️ Выберите услугу из списка:",
            reply_markup=services_keyboard
        )
        return CHOOSING_SERVICE

    context.user_data['service'] = service
    await update.message.reply_text("📝 Введите ваше имя:", reply_markup=ReplyKeyboardRemove())
    return ENTERING_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await update.message.reply_text("📱 Введите ваш телефон:")
    return ENTERING_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("🔑 Введите ваш пароль:")
    return ENTERING_PASSWORD


async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        password = update.message.text
        await update.message.delete()

        username = context.user_data.get('username')
        phone = context.user_data.get('phone')
        service = context.user_data.get('service')

        if not all([username, phone, service]):
            raise ValueError("Недостаточно данных для оформления заказа")

        # Регистрируем или получаем клиента
        user_id = register_or_get_client(username, phone, password)

        # Сохраняем заказ
        order_id = save_order_to_db(user_id, service)
        logger.info(f"Создан заказ #{order_id} для пользователя {username}")

        # Уведомляем пользователя
        await update.message.reply_text(
            f"✅ Благодарим, {username}! Ваш заказ #{order_id} принят.\n"
            f"Услуга: {service}\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=start_keyboard
        )

        # Уведомляем администратора (как в Flask-приложении)
        admin_msg = (
            f"<b>Новый заказ!</b>\n\n"
            f"<b>ID заказа:</b> {order_id}\n"
            f"<b>Услуга:</b> {service}\n"
            f"<b>Имя:</b> {username}\n"
            f"<b>Телефон:</b> {phone}\n"
        )
        send_to_telegram(TELEGRAM_CHAT_ID, admin_msg)

    except sqlite3.Error as e:
        logger.error(f"Ошибка базы данных: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка при обработке заказа. Попробуйте позже.",
            reply_markup=start_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка оформления заказа: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
            reply_markup=start_keyboard
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Действие отменено. Нажмите /start для продолжения.",
        reply_markup=start_keyboard
    )
    return ConversationHandler.END


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка: {context.error}", exc_info=True)
    if update and update.message:
        await update.message.reply_text(
            "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=start_keyboard
        )


def run_bot():
    """Запуск бота"""

    def start_bot():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            application = ApplicationBuilder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

            conv_handler = ConversationHandler(
                entry_points=[CommandHandler('start', start)],
                states={
                    CHOOSING_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_service)],
                    ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
                    ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
                    ENTERING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_password)],
                },
                fallbacks=[CommandHandler('cancel', cancel)]
            )

            application.add_handler(conv_handler)
            application.add_error_handler(error_handler)

            logger.info("Бот запущен")
            application.run_polling()

        except Exception as e:
            logger.critical(f"Ошибка запуска бота: {e}")
            raise
        finally:
            loop.close()

    from threading import Thread
    bot_thread = Thread(target=start_bot, name="BotThread")
    bot_thread.daemon = True
    bot_thread.start()
    return bot_thread


if __name__ == '__main__':
    run_bot()