from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
from datetime import datetime
import pytz
import sqlite3
import requests
import hashlib
import os
import logging

# Установите нужный часовой пояс
timezone = pytz.timezone('Europe/Moscow')

def format_timestamp(timestamp):
    if not timestamp:
        return "Нет данных"
    try:
        timestamp_obj = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        localized_time = timezone.localize(timestamp_obj)
        formatted_time = localized_time.strftime('%d.%m.%Y %H:%M:%S')
        return formatted_time
    except ValueError as e:
        logger.error(f"Ошибка форматирования времени: {e}")
        return "Ошибка формата времени"

app = Flask(__name__)

load_dotenv()  # Загружаем переменные окружения из .env

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("Необходимо указать TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env файле")

app.secret_key = os.urandom(24)  # Случайный секретный ключ

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Логгирование
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Функция для создания базы данных и таблиц
def init_db():
    conn = sqlite3.connect('orders.db')
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
    conn.close()

# Инициализация базы данных при запуске приложения
init_db()

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

# Модель пользователя
class User(UserMixin):
    def __init__(self, id, username, phone):
        self.id = id
        self.username = username
        self.phone = phone

# Загрузка пользователя для Flask-Login
@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, phone FROM clients WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        logger.debug(f"Загружен пользователь: {user_data}")
        return User(id=user_data[0], username=user_data[1], phone=user_data[2])
    return None

# Хэширование пароля
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Регистрация нового пользователя
def register_user(username, password, phone):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM clients WHERE username = ? OR phone = ?', (username, phone))
    if cursor.fetchone():
        conn.close()
        return False

    hashed_password = hash_password(password)

    cursor.execute('INSERT INTO clients (username, password, phone) VALUES (?, ?, ?)', (username, hashed_password, phone))
    conn.commit()
    conn.close()
    return True

# Авторизация пользователя
def authenticate_user(username, password):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('SELECT id, username, password, phone FROM clients WHERE username = ?', (username,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data and user_data[2] == hash_password(password):
        return User(id=user_data[0], username=user_data[1], phone=user_data[3])
    return None

# Маршрут для регистрации
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        phone = request.form.get('phone')

        if register_user(username, password, phone):
            flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Пользователь с таким именем или телефоном уже существует.', 'error')

    return render_template('register.html')

# Маршрут для авторизации
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = authenticate_user(username, password)
        if user:
            login_user(user)
            flash('Вы успешно вошли в систему.', 'success')
            logger.debug(f"Пользователь {username} авторизован.")
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль.', 'error')
            logger.debug(f"Ошибка авторизации для пользователя {username}.")

    return render_template('login.html')

# Маршрут для выхода
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'success')
    return redirect(url_for('home'))

# Главная страница
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/oil-change')
def oil_change():
    return render_template('oil_change.html')

@app.route('/chain-adjustment')
def chain_adjustment():
    return render_template('chain_adjustment.html')

@app.route('/engine-repair')
def engine_repair():
    return render_template('engine_repair.html')

@app.route('/road-assistance')
def road_assistance():
    return render_template('road_assistance.html')

# Маршрут для оформления заказа
@app.route('/order', methods=['POST'])
@login_required
def order():
    service = request.form.get('service')

    # Сохраняем заказ и получаем его ID
    order_id = save_order_to_db(service)

    message = (
        f"<b>Новый заказ!</b>\n\n"
        f"<b>ID заказа:</b> {order_id}\n"
        f"<b>Услуга:</b> {service}\n"
        f"<b>Имя:</b> {current_user.username}\n"
        f"<b>Телефон:</b> {current_user.phone}\n"
    )

    send_to_telegram(TELEGRAM_CHAT_ID, message)
    logger.debug(f"Создан новый заказ: ID={order_id}, Услуга={service}, Пользователь={current_user.username}")

    return redirect(url_for('thank_you'))

# Функция для сохранения заказа в базу данных
def save_order_to_db(service):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
       INSERT INTO orders (user_id, service)
            VALUES (?, ?)
    ''', (current_user.id, service))

    conn.commit()
    order_id = cursor.lastrowid  # Получаем ID заказа
    conn.close()

    return order_id  # Возвращаем ID заказа

# Функция для получения всех заказов из базы данных
def get_all_orders():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT orders.id, clients.username, clients.phone, orders.service,
               DATETIME(orders.timestamp, 'localtime') AS local_timestamp
        FROM orders
        JOIN clients ON orders.user_id = clients.id
        ORDER BY orders.timestamp DESC
    ''')
    orders = cursor.fetchall()

    conn.close()
    return orders

# Страница благодарности
@app.route('/thank-you')
def thank_you():
    telegram_bot_link = "https://web.telegram.org/k/#@FirstFreeShell_bot"  # Ссылка на бота
    return render_template('thank_you.html', telegram_bot_link=telegram_bot_link)

# Админка
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            orders = get_all_orders()
            formatted_orders = []
            for order in orders:
                order_id, username, phone, service, timestamp = order
                formatted_time = format_timestamp(timestamp)  # Форматируем время
                formatted_orders.append((order_id, username, phone, service, formatted_time))
            return render_template('admin.html', orders=formatted_orders)
        else:
            flash('Неверный пароль администратора.', 'error')
            return redirect(url_for('admin'))
    else:
        return render_template('admin_login.html')

if __name__ == '__main__':
    app.run(debug=True)