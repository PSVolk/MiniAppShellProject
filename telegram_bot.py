import asyncio
import hashlib
import requests
import sqlite3
import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ConversationHandler, ContextTypes
)
from dotenv import load_dotenv
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

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

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")

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

class BotManager:
    def __init__(self):
        self.application = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.executor = ThreadPoolExecutor(max_workers=1)
        self._init_db()

    def _init_db(self):
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
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_or_get_client(self, username: str, phone: str, password: str) -> int:
        """Регистрирует нового клиента или возвращает существующего"""
        with sqlite3.connect('orders.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM clients WHERE username = ? OR phone = ?',
                (username, phone))
            if existing := cursor.fetchone():
                return existing[0]

            cursor.execute(
                'INSERT INTO clients (username, phone, password) VALUES (?, ?, ?)',
                (username, phone, self.hash_password(password)))
            conn.commit()
            return cursor.lastrowid

    def save_order_to_db(self, user_id: int, service: str) -> int:
        """Сохраняет заказ в БД и возвращает его ID"""
        with sqlite3.connect('orders.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO orders (user_id, service) VALUES (?, ?)',
                (user_id, service))
            conn.commit()
            return cursor.lastrowid

    def send_to_telegram(self, chat_id: str, message: str):
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
                timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка отправки в Telegram: {e}")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            "🚀 Добро пожаловать в Мотомастер! Выберите услугу:",
            reply_markup=services_keyboard)
        return CHOOSING_SERVICE

    async def choose_service(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора услуги"""
        service = update.message.text
        if service not in SERVICES:
            await update.message.reply_text(
                "⚠️ Выберите услугу из списка:",
                reply_markup=services_keyboard)
            return CHOOSING_SERVICE

        context.user_data['service'] = service
        await update.message.reply_text(
            "📝 Введите ваше имя:",
            reply_markup=ReplyKeyboardRemove())
        return ENTERING_NAME

    async def enter_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода имени"""
        context.user_data['username'] = update.message.text
        await update.message.reply_text("📱 Введите ваш телефон:")
        return ENTERING_PHONE

    async def enter_phone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода телефона"""
        context.user_data['phone'] = update.message.text
        await update.message.reply_text("🔑 Введите ваш пароль:")
        return ENTERING_PASSWORD

    async def enter_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ввода пароля"""
        try:
            password = update.message.text
            await update.message.delete()

            username = context.user_data.get('username')
            phone = context.user_data.get('phone')
            service = context.user_data.get('service')

            if not all([username, phone, service]):
                raise ValueError("Недостаточно данных для оформления заказа")

            user_id = self.register_or_get_client(username, phone, password)
            order_id = self.save_order_to_db(user_id, service)
            logger.info(f"Создан заказ #{order_id} для пользователя {username}")

            await update.message.reply_text(
                f"✅ Спасибо, {username}! Ваш заказ #{order_id} принят.\n"
                f"Услуга: {service}\n"
                "Мы свяжемся с вами в ближайшее время.",
                reply_markup=start_keyboard)

            admin_msg = (
                f"<b>Новый заказ!</b>\n\n"
                f"<b>ID заказа:</b> {order_id}\n"
                f"<b>Услуга:</b> {service}\n"
                f"<b>Имя:</b> {username}\n"
                f"<b>Телефон:</b> {phone}\n")
            self.send_to_telegram(TELEGRAM_CHAT_ID, admin_msg)

        except Exception as e:
            logger.error(f"Ошибка оформления заказа: {e}")
            await update.message.reply_text(
                "⚠️ Произошла ошибка. Пожалуйста, попробуйте еще раз.",
                reply_markup=start_keyboard)
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик отмены"""
        await update.message.reply_text(
            "❌ Действие отменено. Нажмите /start для продолжения.",
            reply_markup=start_keyboard)
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка: {context.error}", exc_info=True)
        if update and update.message:
            await update.message.reply_text(
                "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже.",
                reply_markup=start_keyboard)

    async def process_webhook_update(self, update: Update):
        """Асинхронная обработка обновлений"""
        try:
            logger.info(f"Processing update {update.update_id}")
            await self.application.process_update(update)
        except Exception as e:
            logger.error(f"Update processing error: {e}")

    async def run_webhook(self, hostname: str, port: int, secret_token: str):
        """Асинхронный запуск webhook"""
        if not self.application:
            self.init_bot()

        await self.application.initialize()
        await self.application.start()

        webhook_url = f"https://{hostname}/webhook"
        await self.application.bot.set_webhook(
            url=webhook_url,
            secret_token=secret_token,
            drop_pending_updates=True)
        logger.info(f"Webhook установлен на {webhook_url}")

        # Бесконечное ожидание
        await asyncio.Event().wait()

    async def run_polling(self):
        """Запуск бота в режиме polling"""
        if not self.application:
            self.init_bot()

        logger.info("Запуск бота в режиме polling")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Бот успешно запущен")

        # Бесконечное ожидание
        await asyncio.Event().wait()

    def init_bot(self):
        """Инициализация и настройка бота"""
        self.application = ApplicationBuilder() \
            .token(TELEGRAM_BOT_TOKEN) \
            .build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', self.start)],
            states={
                CHOOSING_SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.choose_service)],
                ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_name)],
                ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_phone)],
                ENTERING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.enter_password)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)])

        self.application.add_handler(conv_handler)
        self.application.add_error_handler(self.error_handler)
        return self.application

# Создание экземпляра бота
bot_manager = BotManager()

def init_bot():
    """Инициализация бота"""
    return bot_manager.init_bot()

def run_polling():
    """Запуск бота в режиме polling"""
    asyncio.run(bot_manager.run_polling())

if __name__ == '__main__':
    try:
        if os.getenv('TEST_WEBHOOK'):
            async def test_webhook():
                await bot_manager.run_webhook(
                    "localhost",
                    5000,
                    "test_secret")
            asyncio.run(test_webhook())
        else:
            run_polling()
    except Exception as e:
        logger.critical(f"Ошибка запуска: {str(e)}", exc_info=True)
