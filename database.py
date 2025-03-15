import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
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

# Получение или создание клиента
def get_or_create_client(username, password, phone):
    try:
        logger.info(f"Получены данные: username={username}, password={password}, phone={phone}")
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()

        cursor.execute('SELECT id FROM clients WHERE username = ? OR phone = ?', (username, phone))
        client = cursor.fetchone()

        if not client:
            logger.info(f"Создание нового клиента")
            cursor.execute('INSERT INTO clients (username, password, phone) VALUES (?, ?, ?)', (username, password, phone))
            user_id = cursor.lastrowid
        else:
            logger.info(f"Найден существующий клиент: id={client[0]}")
            user_id = client[0]

        conn.commit()
        return user_id
    except sqlite3.Error as e:

        logger.error(f"Ошибка при работе с базой данных: {e}")
        return None
    finally:
        conn.close()


# Сохранение заказа в базу данных
def save_order_to_db(user_id, service):
    try:
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO orders (user_id, service)
            VALUES (?, ?)
        ''', (user_id, service))

        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Ошибка при сохранении заказа: {e}")
    finally:
        conn.close()

# Получение всех заказов
def get_all_orders():
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT orders.id, clients.username, clients.phone, orders.service, orders.timestamp
        FROM orders
        JOIN clients ON orders.user_id = clients.id
        ORDER BY orders.timestamp DESC
    ''')
    orders = cursor.fetchall()

    conn.close()
    return orders