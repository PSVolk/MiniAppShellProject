import threading
import logging
from app import create_app
from telegram_bot import run_bot  # Импортируем новую функцию

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('launcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_flask():
    """Запуск Flask-приложения"""
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    logger.info("Запуск приложения...")

    # Запускаем бот (он сам создаст свой поток)
    bot_thread = run_bot()

    # Запускаем Flask в основном потоке
    try:
        run_flask()
    except KeyboardInterrupt:
        logger.info("Приложение остановлено пользователем")
    except Exception as e:
        logger.critical(f"Ошибка Flask: {e}", exc_info=True)