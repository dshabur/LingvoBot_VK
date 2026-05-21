# VK Long Poll бот: один процесс, SQLite по умолчанию в WORKDIR.
# Сборка: docker build -t vk-lang-bot .
# Запуск: см. комментарий внизу.

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY . .

# Том для сохранения БД между перезапусками: -v vkbot_data:/data
# и переменная DATABASE_PATH=/data/bot_data.sqlite3
CMD ["python", "-u", "main.py"]
