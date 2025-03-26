from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
from datetime import datetime
import pytz
import sqlite3
import hashlib
import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import threading

# Инициализация приложения
app = Flask(__name__)
load_dotenv()

# Конфигурация
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Инициализация базы данных
def init_db():
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES clients (id)
            )
        ''')
        conn.commit()

init_db()

# Модель пользователя
class User(UserMixin):
    def __init__(self, id, username, phone):
        self.id = id
        self.username = username
        self.phone = phone

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, phone FROM clients WHERE id = ?', (user_id,))
        if user_data := cursor.fetchone():
            return User(*user_data)
    return None

# Telegram бот (режим вебхуков)
def setup_bot_webhook():
    try:
        bot = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text('Бот активен через вебхуки!')
        
        bot.add_handler(CommandHandler("start", start))
        
        # Устанавливаем вебхук
        webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/telegram_webhook"
        bot.run_webhook(
            listen="0.0.0.0",
            port=5001,
            webhook_url=webhook_url,
            secret_token=os.getenv('WEBHOOK_SECRET')
        )
        logger.info("Telegram бот настроен на вебхуки")
    except Exception as e:
        logger.error(f"Ошибка настройки бота: {e}")

# Обработчик вебхука для Telegram
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token') != os.getenv('WEBHOOK_SECRET'):
        return "Unauthorized", 403
    
    update = Update.de_json(request.get_json(), bot)
    bot.process_update(update)
    return "OK", 200

# Остальные маршруты Flask (как в предыдущем коде)
# ... (ваши существующие маршруты Flask)

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    # На Render используем только Flask с вебхуками
    run_flask()
