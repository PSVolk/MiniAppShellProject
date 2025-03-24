import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler
from database import init_db, save_order_to_db
from dotenv import load_dotenv
import sqlite3
import logging
import hashlib
import os

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
load_dotenv()  # Загружаем переменные окружения из .env

# Токен вашего Telegram-бота
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# ID чата администратора
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

WEBHOOK_URL = 'https://https://motomaster.onrender.com/webhook'

def set_webhook():
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook'
    payload = {
        'url': WEBHOOK_URL
    }
    response = requests.post(url, json=payload)
    return response.json()

# Вызовите эту функцию при запуске приложения
set_webhook()

# Состояния для ConversationHandler
CHOOSING_SERVICE, ENTERING_NAME, ENTERING_PHONE, ENTERING_PASSWORD = range(4)

def check_telegram_api():
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при проверке API Telegram: {e}")
        return None

# Вызовите эту функцию при запуске приложения
bot_info = check_telegram_api()
if bot_info:
    logger.info(f"Бот подключен: {bot_info}")
else:
    logger.error("Не удалось подключиться к API Telegram")

# Услуги, доступные на сайте
SERVICES = {
    "Замена масла": "oil_change",
    "Регулировка цепи": "chain_adjustment",
    "Ремонт двигателя": "engine_repair",
    "Помощь на дороге": "road_assistance"
}

# Инициализация базы данных
init_db()

# Фиксированная клавиатура с кнопкой "Старт"
start_keyboard = ReplyKeyboardMarkup([['/start']], resize_keyboard=True, one_time_keyboard=True)

# Клавиатура с кнопками услуг
services_keyboard = ReplyKeyboardMarkup(
    [[service] for service in SERVICES.keys()],  # Создаем кнопки для каждой услуги
    resize_keyboard=True,
    one_time_keyboard=True
)

# Хэширование пароля
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Проверка данных клиента
def authenticate_client(username, phone, password):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, username, phone, password FROM clients 
        WHERE username = ? AND phone = ? AND password = ?
    ''', (username, phone, hash_password(password)))

    client = cursor.fetchone()
    conn.close()

    if client:
        return client[0]  # Возвращаем user_id
    return None  # Клиент не найден

# Сохранение заказа в базу данных и возврат ID заказа
def save_order_to_db(user_id, service):
    try:
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders (user_id, service)
            VALUES (?, ?)
        ''', (user_id, service))

        order_id = cursor.lastrowid  # Получаем ID заказа
        conn.commit()
        return order_id  # Возвращаем ID заказа
    except sqlite3.Error as e:
        logger.error(f"Ошибка при сохранении заказа в базу данных: {e}")
        raise
    finally:
        conn.close()

# Функция для отправки сообщения в Telegram
def send_to_telegram(chat_id, message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при отправке сообщения в Telegram: {e}")
        return None

# Обработчик команды /start
async def start(update: Update, context):
    # Отправляем приветственное сообщение с кнопкой "Старт"
    await update.message.reply_text(
        "Привет! Я бот мотосервиса 'МотоМастер'. Выберите услугу:",
        reply_markup=services_keyboard  # Показываем кнопки услуг
    )
    return CHOOSING_SERVICE

# Обработчик выбора услуги
async def choose_service(update: Update, context):
    service = update.message.text
    if service not in SERVICES:
        await update.message.reply_text("Пожалуйста, выберите услугу из списка.")
        return CHOOSING_SERVICE

    context.user_data['service'] = service
    await update.message.reply_text("Введите ваше имя:")
    return ENTERING_NAME

# Обработчик ввода имени
async def enter_name(update: Update, context):
    username = update.message.text
    context.user_data['username'] = username
    await update.message.reply_text("Введите ваш номер телефона:")
    return ENTERING_PHONE

# Обработчик ввода телефона
async def enter_phone(update: Update, context):
    phone = update.message.text
    context.user_data['phone'] = phone
    # Запрашиваем пароль и скрываем клавиатуру
    await update.message.reply_text(
        "Введите ваш пароль (текст будет удален):",
        reply_markup=ReplyKeyboardRemove()  # Скрываем клавиатуру
    )
    return ENTERING_PASSWORD

# Обработчик ввода пароля
async def enter_password(update: Update, context):
    password = update.message.text
    context.user_data['password'] = password

    # Удаляем сообщение с паролем
    await update.message.delete()

    # Получаем данные из context.user_data
    username = context.user_data.get('username')
    phone = context.user_data.get('phone')
    service = context.user_data.get('service')

    if not username or not phone or not service:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните заново.")
        return ConversationHandler.END

    # Проверяем данные клиента
    user_id = authenticate_client(username, phone, password)
    if not user_id:
        await update.message.reply_text(
            "Ошибка: Клиент не найден. Пожалуйста, проверьте введенные данные или зарегистрируйтесь на сайте."
        )
        return ConversationHandler.END

    try:
        # Сохраняем заказ в базу данных и получаем ID заказа
        order_id = save_order_to_db(user_id, service)
        logger.info("Заказ успешно сохранен в базу данных")

        # Сообщение об успешном оформлении заказа с ID заказа
        await update.message.reply_text(
            f"Спасибо, {username}! Ваш заказ на услугу '{service}' принят.\n"
            f"ID вашего заказа: {order_id}\n"
            "Мы свяжемся с вами в ближайшее время."
        )

        # Сообщение администратору с ID заказа
        admin_message = (
            f"<b>Новый заказ!</b>\n\n"
            f"<b>ID заказа:</b> {order_id}\n"
            f"<b>Услуга:</b> {service}\n"
            f"<b>Имя:</b> {username}\n"
            f"<b>Телефон:</b> {phone}\n"
        )
        send_to_telegram(TELEGRAM_CHAT_ID, admin_message)

        # Возвращаем пользователя в начальное состояние с кнопкой "Старт"
        await update.message.reply_text(
            "Чтобы оформить новый заказ, нажмите кнопку 'Старт'.",
            reply_markup=start_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении заказа: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении заказа. Пожалуйста, попробуйте позже.")
    return ConversationHandler.END

# Обработчик команды /cancel
async def cancel(update: Update, context):
    await update.message.reply_text("Заказ отменен.")
    return ConversationHandler.END

# Настройка и запуск бота
if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # ConversationHandler для обработки заказа
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
    application.run_polling()
