import pytest
import sqlite3
from app import create_app


@pytest.fixture
def app():
    """Фикстура для создания тестового приложения"""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'DATABASE': ':memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'JSON_AS_ASCII': False
    })

    # Инициализация БД перед каждым тестом
    with app.app_context():
        conn = sqlite3.connect(':memory:')
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

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app, client):
    """Фикстура для аутентифицированного клиента"""
    with app.app_context():
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Убедимся, что таблица существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE
            )
        ''')

        # Регистрация тестового пользователя
        cursor.execute(
            'INSERT INTO clients (username, password, phone) VALUES (?, ?, ?)',
            ('testuser', 'hashedpassword', '+79991112233')
        )
        conn.commit()
        conn.close()

    # Аутентификация
    with client:
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        yield client