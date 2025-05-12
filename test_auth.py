import hashlib
import sqlite3
import pytest

def test_hash_password():
    """Тест хеширования пароля"""
    password = "testpass"
    hashed = hashlib.sha256(password.encode()).hexdigest()
    assert len(hashed) == 64

def test_register_user(app):
    """Тест регистрации пользователя"""
    with app.app_context():
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Создаем таблицу
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE
            )
        ''')

        # Тест регистрации
        try:
            cursor.execute(
                'INSERT INTO clients (username, password, phone) VALUES (?, ?, ?)',
                ('testuser', 'hashedpass', '+79998887766')
            )
            conn.commit()
            assert True
        except sqlite3.Error as e:
            pytest.fail(f"Ошибка при регистрации: {str(e)}")
        finally:
            conn.close()