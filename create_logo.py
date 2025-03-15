from PIL import Image, ImageDraw, ImageFont

# Размер изображения
width, height = 200, 200

# Создаем изображение с белым фоном
img = Image.new('RGB', (width, height), color=(255, 255, 255))

# Инициализируем объект для рисования
draw = ImageDraw.Draw(img)

# Загружаем шрифт (можно использовать стандартный шрифт)
try:
    font = ImageFont.truetype("arial.ttf", 24)  # Для Windows
except:
    font = ImageFont.load_default()  # Если шрифт не найден

# Текст логотипа
text = "МотоМастер"

# Получаем размер текста с помощью textbbox
left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
text_width = right - left
text_height = bottom - top

# Позиция текста (по центру)
x_text = (width - text_width) / 2
y_text = (height - text_height) / 2 + 20  # Сдвигаем текст немного вниз

# Добавляем текст на изображение
draw.text((x_text, y_text), text, fill=(0, 0, 0), font=font)  # Черный цвет текста

# Загружаем иконку мотоцикла
try:
    icon_path = "static/images/motocycle.png"
    icon = Image.open(icon_path)
    print(f"Иконка успешно загружена из {icon_path}")
    icon = icon.resize((50, 50))  # Масштабируем иконку
    # Позиция иконки (над текстом)
    x_icon = (width - icon.width) / 2
    y_icon = y_text - icon.height - 10  # Иконка выше текста
    # Вставляем иконку на изображение
    img.paste(icon, (int(x_icon), int(y_icon)), icon)
    print("Иконка успешно добавлена на логотип")
except FileNotFoundError:
    print(f"Ошибка: файл {icon_path} не найден.")
except Exception as e:
    print(f"Ошибка при добавлении иконки: {e}")

# Сохраняем изображение
img.save('static/images/logo.png')

print("Логотип создан и сохранен как static/images/logo.png")