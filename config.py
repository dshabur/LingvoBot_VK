# -*- coding: utf-8 -*-
"""
Модуль загрузки конфигурации из переменных окружения.

Секретные данные (токен группы, ID группы) хранятся в файле .env
и подгружаются через библиотеку python-dotenv. Файл .env не должен
попадать в систему контроля версий.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем переменные из .env в корне проекта (рядом с main.py).
# override=True: значения из .env перекрывают переменные окружения ОС (иначе старый
# VK_GROUP_TOKEN в системе может «перебивать» обновлённый токен в файле — типичная
# причина ошибки ApiError [5] invalid access_token после правки .env).
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path, override=True)


def _require_int(name: str) -> int:
    """Читает целое число из окружения; при отсутствии или ошибке — исключение."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        raise ValueError(
            f"Переменная окружения {name} не задана. "
            f"Создайте файл .env по образцу .env.example."
        )
    return int(raw.strip())


def _require_str(name: str) -> str:
    """Читает непустую строку из окружения."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        raise ValueError(
            f"Переменная окружения {name} не задана. "
            f"Создайте файл .env по образцу .env.example."
        )
    # Убираем пробелы, BOM и перевод строки (частая ошибка при копировании из VK)
    cleaned = raw.strip().strip("\ufeff").replace("\r", "").replace("\n", "")
    if not cleaned:
        raise ValueError(f"Переменная окружения {name} пуста после очистки.")
    return cleaned


# Токен сообщества с правами на сообщения и Long Poll (Bots API)
VK_GROUP_TOKEN: str = _require_str("VK_GROUP_TOKEN")

# Числовой ID группы (без минуса), тот же, что в настройках Long Poll API
VK_GROUP_ID: int = _require_int("VK_GROUP_ID")

# Версия VK API (на хостинге можно переопределить переменной VK_API_VERSION)
VK_API_VERSION: str = os.getenv("VK_API_VERSION", "5.199").strip() or "5.199"

# Путь к файлу SQLite (можно переопределить в .env)
DATABASE_PATH: str = os.getenv(
    "DATABASE_PATH",
    str(Path(__file__).resolve().parent / "bot_data.sqlite3"),
)
