# -*- coding: utf-8 -*-
"""
Генерация JSON-клавиатур для Bots API (VkKeyboard).

- Обычная (reply) клавиатура — главное меню под строкой ввода.
- Inline-клавиатура — варианты ответа в квизе (callback-кнопки с payload).

Payload для квиза — JSON-объект (сериализуется в строку VK API):
{"action": "quiz", "word_id": <int>, "is_correct": true/false}

Payload выбора языка:
{"action": "set_lang", "lang": "en"|"de"|"fr"|"zh"|"es"|"it"|"pt"|"ja"}

Payload выбора уровня:
{"action": "set_level", "level": "beginner"|"intermediate"|"advanced"}

Payload выбора темы (категория словаря):
{"action": "set_category", "category": "<строка>"} или "__all__" для всех тем.

Payload листания тем:
{"action": "category_page", "page": <int>}

Payload магазина:
{"action": "shop_buy", "item": "hint"|"double_xp"}
"""

from __future__ import annotations

import json
from typing import List, TypedDict

from vk_api.keyboard import VkKeyboard, VkKeyboardColor


class QuizOption(TypedDict):
    """Один вариант ответа в квизе (подпись кнопки + признак верности)."""

    label: str
    is_correct: bool


def get_main_menu_keyboard() -> VkKeyboard:
    """
    Главное меню: текстовые кнопки под строкой ввода.
    При нажатии в чат уходит текст с кнопки — его обрабатывает Router в main.py.

    VK ограничивает число кнопок reply-клавиатуры (не более 10) — иначе [911].
    «Команды» и «Достижения» — по тексту /help, «помощь», /achievements, «достижения».
    """
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("Учить слова", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Тест", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Мой профиль", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("Магазин", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("Язык", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Уровень", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("Тема", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("Режим теста", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("Слабые слова", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Квест дня", color=VkKeyboardColor.POSITIVE)
    return keyboard


def get_language_inline_keyboard() -> VkKeyboard:
    """
    Inline-кнопки выбора языка изучения (callback → action set_lang).
    """
    keyboard = VkKeyboard(inline=True)
    langs = [
        ("🇬🇧 EN", "en"),
        ("🇩🇪 DE", "de"),
        ("🇫🇷 FR", "fr"),
        ("🇨🇳 ZH", "zh"),
        ("🇪🇸 ES", "es"),
        ("🇮🇹 IT", "it"),
        ("🇵🇹 PT", "pt"),
        ("🇯🇵 JA", "ja"),
    ]
    for i, (label, code) in enumerate(langs):
        keyboard.add_callback_button(
            label=label,
            color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"action": "set_lang", "lang": code}, ensure_ascii=False),
        )
        if i == 3:
            keyboard.add_line()
    return keyboard


def get_level_inline_keyboard() -> VkKeyboard:
    """Inline-кнопки выбора уровня владения (callback → action set_level)."""
    keyboard = VkKeyboard(inline=True)
    levels = [
        ("A1–A2", "beginner"),
        ("B1–B2", "intermediate"),
        ("C1–C2", "advanced"),
    ]
    for label, code in levels:
        keyboard.add_callback_button(
            label=label,
            color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"action": "set_level", "level": code}, ensure_ascii=False),
        )
    return keyboard


def get_quiz_mode_inline_keyboard() -> VkKeyboard:
    """Inline: режим формулировки вопроса в квизе."""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button(
        label="Иностр. → русский",
        color=VkKeyboardColor.SECONDARY,
        payload=json.dumps({"action": "set_quiz_mode", "mode": "to_rus"}, ensure_ascii=False),
    )
    keyboard.add_callback_button(
        label="Русский → иностр.",
        color=VkKeyboardColor.SECONDARY,
        payload=json.dumps({"action": "set_quiz_mode", "mode": "to_foreign"}, ensure_ascii=False),
    )
    return keyboard


# VK: не более 10 inline-кнопок в одном сообщении ([911]).
_CATEGORIES_PER_INLINE_PAGE = 6


def category_picker_page_count(categories: List[str]) -> int:
    """Число страниц выбора темы при лимите кнопок VK."""
    n = len(categories)
    if n <= 0:
        return 1
    return max(1, (n + _CATEGORIES_PER_INLINE_PAGE - 1) // _CATEGORIES_PER_INLINE_PAGE)


def format_category_picker_text(categories: List[str], page: int) -> str:
    """Текст над inline-клавиатурой выбора темы."""
    total_pages = category_picker_page_count(categories)
    page = max(0, min(page, total_pages - 1))
    base = (
        "Выберите тему словаря (карточки и квиз будут в рамках темы, "
        "если в ней достаточно слов):"
    )
    if total_pages <= 1:
        return base
    return (
        f"{base}\n"
        f"Страница {page + 1} из {total_pages} · всего тем: {len(categories)}."
    )


def get_category_inline_keyboard(categories: List[str], page: int = 0) -> VkKeyboard:
    """
    Inline: выбор темы словаря (с постраничной навигацией).

    На странице: «Все темы», до 6 категорий, при необходимости «Назад» / «Далее» (≤10 кнопок).
    """
    total_pages = category_picker_page_count(categories)
    page = max(0, min(page, total_pages - 1))
    start = page * _CATEGORIES_PER_INLINE_PAGE
    chunk = categories[start : start + _CATEGORIES_PER_INLINE_PAGE]

    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button(
        label="Все темы",
        color=VkKeyboardColor.PRIMARY,
        payload=json.dumps({"action": "set_category", "category": "__all__"}, ensure_ascii=False),
    )
    keyboard.add_line()
    for i, cat in enumerate(chunk):
        label = cat[:35] + "…" if len(cat) > 35 else cat
        keyboard.add_callback_button(
            label=label,
            color=VkKeyboardColor.SECONDARY,
            payload=json.dumps({"action": "set_category", "category": cat}, ensure_ascii=False),
        )
        if i % 2 == 1 and i + 1 < len(chunk):
            keyboard.add_line()

    if total_pages > 1:
        keyboard.add_line()
        if page > 0:
            keyboard.add_callback_button(
                label="◀ Назад",
                color=VkKeyboardColor.SECONDARY,
                payload=json.dumps({"action": "category_page", "page": page - 1}, ensure_ascii=False),
            )
        if page < total_pages - 1:
            keyboard.add_callback_button(
                label="Далее ▶",
                color=VkKeyboardColor.SECONDARY,
                payload=json.dumps(
                    {"action": "category_page", "page": page + 1},
                    ensure_ascii=False,
                ),
            )
    return keyboard


def get_shop_inline_keyboard() -> VkKeyboard:
    """Inline: покупки в магазине наград."""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_callback_button(
        label="Подсказка (35💰)",
        color=VkKeyboardColor.SECONDARY,
        payload=json.dumps({"action": "shop_buy", "item": "hint"}, ensure_ascii=False),
    )
    keyboard.add_callback_button(
        label="x2 XP (50💰)",
        color=VkKeyboardColor.SECONDARY,
        payload=json.dumps({"action": "shop_buy", "item": "double_xp"}, ensure_ascii=False),
    )
    return keyboard


def get_quiz_inline_keyboard(word_id: int, options: List[QuizOption]) -> VkKeyboard:
    """
    Inline-клавиатура с callback-кнопками для квиза.

    :param word_id: id слова из таблицы words (для обновления прогресса).
    :param options: до 4 вариантов (логика перемешивания — в game_logic / main).
    """
    keyboard = VkKeyboard(inline=True)

    for i, opt in enumerate(options):
        payload = {
            "action": "quiz",
            "word_id": word_id,
            "is_correct": opt["is_correct"],
        }
        # VK ограничивает длину label; при необходимости укорачиваем отображаемый текст
        label = opt["label"][:40] if len(opt["label"]) > 40 else opt["label"]
        # Все кнопки одного цвета — иначе «правильный» вариант был бы виден до ответа
        keyboard.add_callback_button(
            label=label,
            color=VkKeyboardColor.SECONDARY,
            payload=json.dumps(payload, ensure_ascii=False),
        )
        # Два кнопки в ряд — компактная сетка 2x2 для четырёх вариантов
        if i % 2 == 1 and i + 1 < len(options):
            keyboard.add_line()

    return keyboard


def get_empty_keyboard_json() -> str:
    """JSON пустой клавиатуры — снимает inline/reply с сообщения при редактировании."""
    return VkKeyboard.get_empty_keyboard()
