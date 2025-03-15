import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler
from database import init_db, get_or_create_client, save_order_to_db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен вашего Telegram-бота
TELEGRAM_BOT_TOKEN = '7684324256:AAGLrK8CVtZyQFvtdLv3IMQDt0gMuR9ddCY'

# Состояния для ConversationHandler
CHOOSING_SERVICE, ENTERING_NAME, ENTERING_PHONE, ENTERING_PASSWORD = range(4)

# Услуги, доступные на сайте
SERVICES = {
    "Замена масла": "oil_change",
    "Регулировка цепи": "chain_adjustment",
    "Ремонт двигателя": "engine_repair",
    "Дорожная помощь": "road_assistance"
}

# Инициализация базы данных
init_db()

# start_keyboard = ReplyKeyboardMarkup([['/start']], resize_keyboard=True, one_time_keyboard=True)

# Обработчик команды /start
async def start(update: Update, context):
    reply_keyboard = [list(SERVICES.keys())]
    await update.message.reply_text(
        "Привет! Я бот мотосервиса 'МотоМастер'. Выберите услугу:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        # reply_markup=start_keyboard
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
    logger.info(f"Введен номер телефона: {phone}")  # Логируем ввод телефона
    context.user_data['phone'] = phone
    await update.message.reply_text("Введите ваш пароль:")
    return ENTERING_PASSWORD

    # Обработчик ввода пароля
async def enter_password(update: Update, context):
    password = update.message.text
    context.user_data['password'] = password

    try:
        # Получаем данные из context.user_data
        username = context.user_data.get('username')
        phone = context.user_data.get('phone')
        service = context.user_data.get('service')
        logger.info(f"Данные для заказа: username={username}, phone={phone}, service={service}")  # Логируем данные

        if not username or not service:
            logger.error("Отсутствуют данные username или service в context.user_data")
            await update.message.reply_text("Произошла ошибка. Пожалуйста, начните заново.")
            return ConversationHandler.END


    # Сохраняем заказ в базу данных
        client_id = get_or_create_client(username, password, phone)
        logger.info(f"Создан/найден клиент с ID: {client_id}")  # Логируем ID клиента
        save_order_to_db(client_id, service)
        logger.info("Заказ успешно сохранен в базу данных")  # Логируем успешное сохранение

        await update.message.reply_text(
        f"Спасибо, {username}! Ваш заказ на услугу '{service}' принят. Мы свяжемся с вами в ближайшее время."
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении заказа: {e}")  # Логируем ошибку
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