from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from telegram import Bot
import sqlite3
import requests
import hashlib

app = Flask(__name__)

# Токен вашего Telegram-бота
TELEGRAM_BOT_TOKEN = '7684324256:AAGLrK8CVtZyQFvtdLv3IMQDt0gMuR9ddCY'
# ID чата администратора
TELEGRAM_CHAT_ID = '-4707230825'

app.secret_key = 'ваш_секретный_ключ'  # Замените на случайный секретный ключ

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Функция для создания базы данных и таблиц
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Создаем таблицу для пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE
        )
    ''')

    # Создаем таблицу для заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()

# Инициализация базы данных при запуске приложения
init_db()

# Функция для отправки сообщения в Telegram
def send_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    response = requests.post(url, json=payload)
    return response.json()

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
    cursor.execute('SELECT id, username, phone FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        print(f"Загружен пользователь: {user_data}")  # Отладочное сообщение
        return User(id=user_data[0], username=user_data[1], phone=user_data[2])
    return None

# Хэширование пароля
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Регистрация нового пользователя
def register_user(username, password, phone):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Проверяем, существует ли пользователь
    cursor.execute('SELECT id FROM users WHERE username = ? OR phone = ?', (username, phone))
    if cursor.fetchone():
        conn.close()
        return False

    # Хэшируем пароль
    hashed_password = hash_password(password)

    # Создаем нового пользователя
    cursor.execute('INSERT INTO users (username, password, phone) VALUES (?, ?, ?)', (username, hashed_password, phone))
    conn.commit()
    conn.close()
    return True

# Авторизация пользователя
def authenticate_user(username, password):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    # Ищем пользователя
    cursor.execute('SELECT id, username, password, phone FROM users WHERE username = ?', (username,))
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
    # return redirect(url_for('home'))

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
            print(f"Пользователь {username} авторизован.")  # Отладочное сообщение
            return redirect(url_for('home'))
        else:
            flash('Неверное имя пользователя или пароль.', 'error')
            print(f"Ошибка авторизации для пользователя {username}.")  # Отладочное сообщение

    return render_template('login.html')
    # return redirect(url_for('home'))

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

# Остальные маршруты (например, /order) будут доступны только для авторизованных пользователей
@app.route('/order', methods=['POST'])
@login_required
def order():
    # Получаем данные из формы
    name = request.form.get('name')
    phone = request.form.get('phone')
    service = request.form.get('service')

    # Функция для сохранения заказа в базу данных
def save_order_to_db(service, name, phone):
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO orders (user_id, service)
        VALUES (?, ?)
    ''', (current_user.id, service))

    conn.commit()
    conn.close()

    # Функция для получения всех заказов из базы данных
def get_all_orders():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM orders ORDER BY timestamp DESC')
    orders = cursor.fetchall()

    conn.close()
    return orders

    # Формируем сообщение для Telegram
    message = (
        f"<b>Новый заказ!</b>\n\n"
        f"<b>Услуга:</b> {service}\n"
        f"<b>Имя:</b> {current_user.username}\n"
        f"<b>Телефон:</b> {current_user.phone}\n"
        # f"<b>Комментарий:</b> {comment if comment else 'нет'}"
    )

    send_to_telegram(message)

    # Перенаправляем пользователя на страницу с благодарностью
    return redirect(url_for('thank_you'))
@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/admin')
@login_required
def admin():
    # Получаем все заказы из базы данных
    orders = get_all_orders()
    return render_template('admin.html', orders=orders)

if __name__ == '__main__':
    app.run(debug=True)