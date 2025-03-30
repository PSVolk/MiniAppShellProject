import asyncio
import hashlib
import requests
import sqlite3
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes
)
from dotenv import load_dotenv
import os

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Проверка обязательных переменных
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID в переменных окружения")

SERVICES = {
    "🛢️ Замена масла": "oil_change",
    "⛓️ Регулировка цепи": "chain_adjustment",
    "⚙️ Ремонт двигателя": "engine_repair",
    "🆘 Помощь на дороге": "road_assistance"
}

# Состояния разговора
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

def init_db():
    """Инициализация базы данных"""
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                phone TEXT NOT NULL,
                password TEXT NOT NULL,
                UNIQUE(username, phone)
            )''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES clients(id)
            )''')
        conn.commit()

def register_or_get_client(username: str, phone: str, password: str) -> int:
    """Регистрирует нового клиента или возвращает существующего"""
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM clients WHERE username = ? OR phone = ?',
            (username, phone)
        )
        if existing := cursor.fetchone():
            return existing[0]

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
    """Обработчик команды /start"""
    await update.message.reply_text(
        "🚀 Добро пожаловать в Мотомастер! Выберите услугу:",
        reply_markup=services_keyboard
    )
    return CHOOSING_SERVICE

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора услуги"""
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
    """Обработчик ввода имени"""
    context.user_data['username'] = update.message.text
    await update.message.reply_text("📱 Введите ваш телефон:")
    return ENTERING_PHONE

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода телефона"""
    context.user_data['phone'] = update.message.text
    await update.message.reply_text("🔑 Введите ваш пароль:")
    return ENTERING_PASSWORD

async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ввода пароля и завершение заказа"""
    try:
        password = update.message.text
        await update.message.delete()

        username = context.user_data.get('username')
        phone = context.user_data.get('phone')
        service = context.user_data.get('service')

        if not all([username, phone, service]):
            raise ValueError("Недостаточно данных для оформления заказа")

        user_id = register_or_get_client(username, phone, password)
        order_id = save_order_to_db(user_id, service)
        logger.info(f"Создан заказ #{order_id} для пользователя {username}")

        await update.message.reply_text(
            f"✅ Спасибо, {username}! Ваш заказ #{order_id} принят.\n"
            f"Услуга: {service}\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=start_keyboard
        )

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
    """Обработчик отмены"""
    await update.message.reply_text(
        "❌ Действие отменено. Нажмите /start для продолжения.",
        reply_markup=start_keyboard
    )
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=True)
    if update and update.message:
        await update.message.reply_text(
            "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.",
            reply_markup=start_keyboard
        )

async def post_init(application):
    """Функция, выполняемая после инициализации бота"""
    logger.info("Бот успешно инициализирован")
    init_db()
    logger.info("База данных инициализирована")

def init_bot():
    """Инициализация и настройка бота"""
    application = ApplicationBuilder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .post_init(post_init) \
        .build()

    # Регистрация обработчиков
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
    return application

def run_bot():
    """Запуск бота в режиме polling"""
    bot = init_bot()
    logger.info("Бот запускается в режиме polling...")
    bot.run_polling()

def register_handlers(app):
    """Регистрация обработчиков для Flask (оставлено для совместимости)"""
    pass

if __name__ == '__main__':
    run_bot()
