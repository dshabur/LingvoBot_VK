# -*- coding: utf-8 -*-
"""
Точка входа чат-бота ВКонтакте: Long Polling (VkBotLongPoll), маршрутизация (Router).

Обрабатываются:
- MESSAGE_NEW — текстовые сообщения и нажатия кнопок reply-клавиатуры;
- MESSAGE_EVENT — нажатия inline callback-кнопок (квиз), payload в формате JSON.

Для callback требуется вызвать messages.sendMessageEventAnswer в течение ~5 с,
иначе на кнопке остаётся индикатор загрузки.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
import unicodedata
from collections import deque
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.exceptions import ApiError
from vk_api.utils import get_random_id

import config
import db_handler
import game_logic
import gamification
from greetings import GREETING_PHRASES
from keyboards import (
    format_category_picker_text,
    get_category_inline_keyboard,
    get_empty_keyboard_json,
    get_language_inline_keyboard,
    get_level_inline_keyboard,
    get_main_menu_keyboard,
    get_quiz_inline_keyboard,
    get_quiz_mode_inline_keyboard,
    get_shop_inline_keyboard,
)

# Логирование в stdout (удобно при запуске на сервере или в консоли Windows)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)

# Порог схожести (0–1) для нечёткого распознавания команд и синонимов.
FUZZY_MATCH_MIN: float = 0.75
# Ниже этого лучшего совпадения с эталонами считаем ввод «бессмысленным» (случайные буквы и т.п.).
MEANINGLESS_BEST_SCORE_BELOW: float = 0.42

FALLBACK_MEANINGLESS_MESSAGE: str = (
    'Извините, я вас не понял. Пожалуйста, воспользуйтесь кнопками меню или напишите "Помощь".'
)

HELP_TEXT = (
    "Доступные команды:\n"
    "• Начать / /start — регистрация и открытие меню (в т.ч. приветствие на разных языках, напр. こんにちは, hello)\n"
    "• Язык / /lang — выбрать язык изучения (EN, DE, FR, ZH, ES, IT, PT, JA; китайский — мандарин, упрощённые иероглифы)\n"
    "• Уровень / /level — ваш уровень владения (A1–A2 / B1–B2 / C1–C2)\n"
    "• Тема / /theme — тема словаря (категория) для квиза и карточек; «Все темы» снимает фильтр\n"
    "• Режим теста / /quizmode — иностранное слово → русский или наоборот\n"
    "• Слабые слова / /weak — квиз по словам, где у вас больше ошибок, чем верных ответов\n"
    "• Учить слова / /learn — карточка случайного слова\n"
    "• Тест / /test — мини-квиз (часто подбирает «слабые» слова, если они есть в статистике)\n"
    "• Мой профиль / /profile — уровень, XP, монеты, серия, квест, достижения, титул наставника\n"
    "• Квест дня / /quest — случайное задание на день (карточки, тест, комбо, быстрые ответы)\n"
    "• Достижения / /achievements — список открытых наград\n"
    "• Магазин / /shop — монеты за верные ответы; подсказка и x2 XP\n"
    "• Команды / /help — список команд\n"
    "• /menu — показать главное меню"
)

BOT_COMMANDS = [
    {"command": "start", "description": "Запустить бота и открыть меню"},
    {"command": "menu", "description": "Показать главное меню"},
    {"command": "lang", "description": "Выбрать язык изучения"},
    {"command": "level", "description": "Выбрать уровень владения"},
    {"command": "theme", "description": "Тема словаря (категория)"},
    {"command": "quizmode", "description": "Режим теста (направление перевода)"},
    {"command": "weak", "description": "Тест по слабым словам"},
    {"command": "learn", "description": "Показать карточку слова"},
    {"command": "test", "description": "Запустить тест"},
    {"command": "profile", "description": "Показать профиль"},
    {"command": "quest", "description": "Квест дня"},
    {"command": "achievements", "description": "Достижения"},
    {"command": "shop", "description": "Магазин наград"},
    {"command": "help", "description": "Показать список команд"},
]

# Намерение → эталонные фразы (нижний регистр, ё→е). Slash-команды обрабатываются отдельно, точное совпадение.
# «start»: базовые фразы + многоязычные приветствия из greetings.py.
_COMMAND_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "start": (
        "начать",
        "привет",
        "здравствуйте",
        "здравствуй",
        "start",
        "старт",
    )
    + GREETING_PHRASES,
    "menu": ("меню", "menu", "главное меню"),
    "learn": ("учить слова", "изучать слова", "карточка", "словарь", "learn"),
    "test": ("тест", "квиз", "тестирование", "test", "quiz"),
    "profile": (
        "мой профиль",
        "профиль",
        "статистика",
        "стата",
        "statistics",
        "stats",
        "profile",
        "xp",
        "опыт",
    ),
    "lang": ("язык", "language", "lang"),
    "level": ("уровень", "level", "сложность"),
    "theme": (
        "тема",
        "темы",
        "категория",
        "категории",
        "theme",
        "topic",
        "tema",
    ),
    "quizmode": (
        "режим теста",
        "режим квиза",
        "направление перевода",
        "quizmode",
        "quiz mode",
    ),
    "weak": (
        "слабые слова",
        "слабые",
        "повторить сложное",
        "сложные слова",
        "сложное",
        "weak",
        "weak words",
    ),
    "quest": (
        "квест дня",
        "квест",
        "задание дня",
        "ежедневное задание",
        "quest",
        "daily quest",
    ),
    "achievements": (
        "достижения",
        "ачивки",
        "награды",
        "achievements",
        "badges",
    ),
    "shop": (
        "магазин",
        "монеты",
        "награды магазин",
        "shop",
        "store",
    ),
    "help": ("команды", "помощь", "help", "инструкция", "справка"),
}

# Сообщение целиком совпадает с «похожим, но не командой» — не считать это выбором intent.
_AMBIGUOUS_WHOLE_MESSAGE: Dict[str, frozenset[str]] = {
    "test": frozenset({"текст", "text"}),
}

# Точное сопоставление подписи reply-клавиатуры → intent (после _collapse_letters_only + _norm_cmd_text).
# Устраняет случаи, когда fuzzy-сходство «Тема»/«тест» даёт пограничный балл или VK шлёт нестандартный вариант.
REPLY_MENU_NORMALIZED_TO_INTENT: Dict[str, str] = {
    "учить слова": "learn",
    "тест": "test",
    "мой профиль": "profile",
    "магазин": "shop",
    "язык": "lang",
    "уровень": "level",
    "тема": "theme",
    "режим теста": "quizmode",
    "слабые слова": "weak",
    "квест дня": "quest",
}


def _norm_cmd_text(s: str) -> str:
    """Нормализация для сравнения команд (Unicode NFKC + casefold для разных алфавитов)."""
    t = unicodedata.normalize("NFKC", (s or "").strip())
    return t.casefold().replace("ё", "е")


def _collapse_letters_only(s: str) -> str:
    """
    Убирает всё, кроме букв (Unicode L*): пунктуация, цифры, скобки и т.д.
    Слова из букв склеиваются через пробел — так « ПРИВЕТ!!! ))0) » даёт «ПРИВЕТ».
    """
    parts: List[str] = []
    buf: List[str] = []
    for ch in s:
        if unicodedata.category(ch).startswith("L"):
            buf.append(ch)
        else:
            if buf:
                parts.append("".join(buf))
                buf = []
    if buf:
        parts.append("".join(buf))
    return " ".join(parts)


def _extract_slash_command(s: str) -> Optional[str]:
    """
    Извлекает /команду с начала строки (после пробелов). Хвост из !? не мешает: «/start!!!» → /start.
    """
    t = s.strip().strip("\ufeff")
    m = re.match(r"/(\w+)", t, flags=re.IGNORECASE)
    if not m:
        return None
    return f"/{m.group(1).lower()}"


def _phrase_segments(phrase: str) -> List[str]:
    """Целая фраза и значимые части (слова от 3 символов) для опечаток в одном слове."""
    n = _norm_cmd_text(phrase)
    parts: List[str] = [n]
    for w in n.split():
        if len(w) >= 3:
            parts.append(w)
    return parts


def _similarity_segment_to_phrase(segment: str, phrase: str) -> float:
    """Схожесть одного сегмента текста с эталонной фразой или её частями."""
    seg = _norm_cmd_text(segment)
    if not seg:
        return 0.0
    best = 0.0
    for part in _phrase_segments(phrase):
        if not part:
            continue
        best = max(best, SequenceMatcher(None, seg, part).ratio())
    return best


def resolve_command_intent(text: str) -> Tuple[Optional[str], float]:
    """
    Определяет намерение по тексту сообщения.

    Slash-команды (/start, /menu, …) — только точное совпадение (регистр не важен).
    Остальной текст — после удаления небукв и приведения регистра; далее лучшее
    совпадение с эталонами; при score >= FUZZY_MATCH_MIN возвращается намерение.
    """
    raw = (text or "").strip().strip("\ufeff")
    if not raw:
        return None, 0.0

    slash_exact = {
        "/start": "start",
        "/menu": "menu",
        "/learn": "learn",
        "/test": "test",
        "/profile": "profile",
        "/lang": "lang",
        "/level": "level",
        "/theme": "theme",
        "/quizmode": "quizmode",
        "/weak": "weak",
        "/quest": "quest",
        "/achievements": "achievements",
        "/shop": "shop",
        "/help": "help",
    }
    slash = _extract_slash_command(raw)
    if slash is not None:
        intent = slash_exact.get(slash)
        return (intent, 1.0) if intent else (None, 0.0)

    letters_only = _collapse_letters_only(raw)
    low = _norm_cmd_text(letters_only)
    if not low:
        return None, 0.0

    if low in REPLY_MENU_NORMALIZED_TO_INTENT:
        return REPLY_MENU_NORMALIZED_TO_INTENT[low], 1.0

    best_intent: Optional[str] = None
    best_score = 0.0

    def consider_score(score: float, intent: str) -> None:
        nonlocal best_intent, best_score
        if score > best_score:
            best_score = score
            best_intent = intent

    for intent, phrases in _COMMAND_SYNONYMS.items():
        for phrase in phrases:
            consider_score(_similarity_segment_to_phrase(low, phrase), intent)

    # Слова и короткие фразы в сообщении («покажи статистику», «мой профиль пожалуйста»)
    words = re.findall(r"\w+", low, flags=re.UNICODE)
    for w in words:
        if len(w) < 2:
            continue
        for intent, phrases in _COMMAND_SYNONYMS.items():
            for phrase in phrases:
                consider_score(_similarity_segment_to_phrase(w, phrase), intent)

    if best_intent and best_intent in _AMBIGUOUS_WHOLE_MESSAGE:
        if low in _AMBIGUOUS_WHOLE_MESSAGE[best_intent]:
            return None, best_score

    if best_score >= FUZZY_MATCH_MIN:
        return best_intent, best_score
    return None, best_score


def is_meaningless_unknown_input(raw: str, best_match_score: float) -> bool:
    """
    Бессмысленный ввод: только эмодзи/знаки/цифры без букв, либо «каша» из букв
    без заметного сходства с известными командами. Неизвестная /slash-команда сюда не входит.
    """
    t = (raw or "").strip().strip("\ufeff")
    if not t:
        return True
    if _extract_slash_command(t) is not None:
        return False
    letters = _collapse_letters_only(t).strip()
    if not letters:
        return True
    return best_match_score < MEANINGLESS_BEST_SCORE_BELOW


def _parse_payload(raw: Any) -> Optional[Dict[str, Any]]:
    """Преобразует payload из VK (строка JSON или dict) в словарь."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Не удалось разобрать payload: %s", raw)
            return None
    return None


def publish_bot_commands(vk: Any) -> None:
    """
    Публикует список команд в интерфейсе VK.

    В разных версиях API/SDK может использоваться разное имя метода,
    поэтому применяем безопасный fallback. Ошибка публикации не должна
    останавливать Long Poll бота.
    """
    commands_json = json.dumps(BOT_COMMANDS, ensure_ascii=False)

    # Основной вариант, который встречается в некоторых SDK/платформах.
    try:
        vk.messages.setCommands(
            commands=commands_json,
            lang_id=0,
        )
        logger.info("Команды бота опубликованы через messages.setCommands")
        return
    except Exception as exc:
        logger.info("Автопубликация через messages.setCommands недоступна: %s", exc)

    # Fallback для API, где доступен альтернативный метод.
    try:
        vk.messages.setConversationCommands(
            group_id=config.VK_GROUP_ID,
            commands=commands_json,
        )
        logger.info("Команды бота опубликованы через messages.setConversationCommands")
    except Exception as exc:
        logger.info(
            "VK API не поддержал программную публикацию команд (%s). "
            "Команды остаются доступны через /help и кнопки меню; "
            "при необходимости добавьте их вручную в интерфейсе сообщества.",
            exc,
        )


class Router:
    """
    Маршрутизатор событий: сопоставляет текст и callback-действия обработчикам.

    Хранит ссылку на VkApi для вызова messages.* методов.
    """

    def __init__(self, vk: Any) -> None:
        self._vk = vk
        # Время старта процесса: используем для отсечения «старых» событий,
        # которые могут доехать после перезапуска Long Poll.
        self._started_at_ts = int(time.time())
        # Храним JSON главного меню и подставляем его по умолчанию
        # почти во все исходящие сообщения, чтобы кнопки были всегда «под рукой».
        self._main_menu_keyboard = get_main_menu_keyboard().get_keyboard()
        # Кэш последних входящих id сообщений для защиты от повторной обработки.
        self._recent_message_ids: deque[str] = deque(maxlen=500)
        self._recent_message_ids_set: set[str] = set()
        # Сериализация выдачи карточек «Учить слова» по пользователю (дубли событий Long Poll)
        self._learn_locks_guard = threading.Lock()
        self._learn_locks: Dict[int, threading.Lock] = {}

    def _lock_for_learn(self, user_id: int) -> threading.Lock:
        """Отдельный mutex на пользователя для атомарной выдачи следующей карточки."""
        with self._learn_locks_guard:
            if user_id not in self._learn_locks:
                self._learn_locks[user_id] = threading.Lock()
            return self._learn_locks[user_id]

    @staticmethod
    def _study_lang(user_id: int) -> str:
        """Код языка изучения пользователя (см. db_handler.SUPPORTED_LANGS)."""
        db_handler.ensure_user(user_id)
        row = db_handler.get_user(user_id)
        if row is None:
            return "en"
        try:
            lang = row["study_lang"]
        except (KeyError, IndexError):
            lang = "en"
        lang_str = str(lang).strip() if lang else "en"
        return lang_str if lang_str in db_handler.SUPPORTED_LANGS else "en"

    @staticmethod
    def _study_level(user_id: int) -> str:
        """Уровень владения языком (beginner / intermediate / advanced)."""
        db_handler.ensure_user(user_id)
        row = db_handler.get_user(user_id)
        if row is None:
            return "beginner"
        try:
            lvl = row["study_level"]
        except (KeyError, IndexError):
            lvl = "beginner"
        s = str(lvl).strip() if lvl else "beginner"
        return s if s in db_handler.SUPPORTED_LEVELS else "beginner"

    @staticmethod
    def _study_category(user_id: int) -> str:
        """Выбранная тема словаря (пустая строка — все темы)."""
        db_handler.ensure_user(user_id)
        row = db_handler.get_user(user_id)
        if row is None:
            return ""
        try:
            c = row["study_category"]
        except (KeyError, IndexError):
            return ""
        return str(c).strip() if c else ""

    @staticmethod
    def _quiz_mode(user_id: int) -> str:
        """Режим квиза: to_rus или to_foreign."""
        db_handler.ensure_user(user_id)
        row = db_handler.get_user(user_id)
        if row is None:
            return "to_rus"
        try:
            m = row["quiz_mode"]
        except (KeyError, IndexError):
            return "to_rus"
        s = str(m).strip() if m else "to_rus"
        return s if s in db_handler.QUIZ_MODES else "to_rus"

    def _is_duplicate_message(self, peer_id: int, message_obj: Any) -> bool:
        """
        Проверяет, обрабатывали ли уже это входящее сообщение.
        Используем conversation_message_id (или id как fallback).
        """
        msg_local_id = getattr(message_obj, "conversation_message_id", None)
        if msg_local_id is None:
            msg_local_id = getattr(message_obj, "id", None)
        if msg_local_id is None:
            return False

        dedup_key = f"{peer_id}:{msg_local_id}"
        if dedup_key in self._recent_message_ids_set:
            return True

        # Поддерживаем структуру set + deque (быстрый lookup и ограничение памяти).
        if len(self._recent_message_ids) == self._recent_message_ids.maxlen:
            oldest = self._recent_message_ids.popleft()
            self._recent_message_ids_set.discard(oldest)
        self._recent_message_ids.append(dedup_key)
        self._recent_message_ids_set.add(dedup_key)
        return False

    def send_message(self, peer_id: int, text: str, keyboard: Optional[str] = None) -> None:
        """Отправляет сообщение в диалог; keyboard — JSON-строка от VkKeyboard.get_keyboard()."""
        params: Dict[str, Any] = {
            "peer_id": peer_id,
            "random_id": get_random_id(),
            "message": text,
        }
        params["keyboard"] = keyboard if keyboard is not None else self._main_menu_keyboard
        try:
            self._vk.messages.send(**params)
        except ApiError as exc:
            code = getattr(exc, "code", None)
            # [912] Chat bot feature: в настройках сообщества отключены возможности бота.
            if code == 912:
                logger.warning(
                    "VK вернул [912] Chat bot feature. Отправляю сообщение без клавиатуры."
                )
                fallback_params = dict(params)
                fallback_params.pop("keyboard", None)
                self._vk.messages.send(**fallback_params)
                return
            # [911] Неверный формат клавиатуры (слишком много кнопок и т.п.) — главное меню или текст.
            if code == 911:
                logger.warning(
                    "VK вернул [911] Keyboard format is invalid. Повтор с главным меню или без клавиатуры."
                )
                fallback_params = dict(params)
                fallback_params["keyboard"] = self._main_menu_keyboard
                try:
                    self._vk.messages.send(**fallback_params)
                    return
                except ApiError:
                    fallback_params.pop("keyboard", None)
                    self._vk.messages.send(**fallback_params)
                    return
            raise

    def _send_category_picker(self, peer_id: int, user_id: int, page: int = 0) -> None:
        """Сообщение с inline-выбором темы словаря для текущего языка пользователя."""
        sl = self._study_lang(user_id)
        cats = db_handler.list_categories_for_lang(sl)
        if not cats:
            self.send_message(
                peer_id,
                f"Для языка «{game_logic.get_lang_label(sl)}» в базе нет категорий. "
                f"Фильтр темы недоступен.",
                get_main_menu_keyboard().get_keyboard(),
            )
            return
        self.send_message(
            peer_id,
            format_category_picker_text(cats, page),
            get_category_inline_keyboard(cats, page=page).get_keyboard(),
        )

    def handle_message_new(self, event: Any) -> None:
        """Входящее сообщение (пользователь написал текст или нажал reply-кнопку)."""
        msg = event.message
        if not msg:
            return

        text = (msg.text or "").strip()
        peer_id = msg.peer_id
        user_id = msg.from_id
        msg_ts = int(getattr(msg, "date", 0) or 0)

        if not text:
            return

        # При рестарте Long Poll может прислать старые апдейты. Игнорируем всё,
        # что пришло заметно раньше запуска текущего процесса.
        if msg_ts and msg_ts < self._started_at_ts - 3:
            logger.info(
                "Пропуск старого события: peer_id=%s, msg_ts=%s, started_at=%s",
                peer_id,
                msg_ts,
                self._started_at_ts,
            )
            return

        if self._is_duplicate_message(peer_id, msg):
            logger.info("Пропуск дубликата входящего сообщения: peer_id=%s", peer_id)
            return

        # Игнорируем сообщения от сообществ (на всякий случай)
        if user_id < 0:
            return

        intent, match_score = resolve_command_intent(text)
        if intent is not None and match_score < 1.0:
            logger.info(
                "Нечёткое совпадение команды: intent=%s score=%.3f text=%r",
                intent,
                match_score,
                text[:120],
            )

        if intent == "start":
            db_handler.ensure_user(user_id)
            db_handler.set_user_state(user_id, "menu")
            gamification.ensure_daily_quest(user_id)
            self.send_message(
                peer_id,
                "Добро пожаловать! Выберите действие в меню ниже.",
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        if intent == "menu":
            db_handler.ensure_user(user_id)
            db_handler.set_user_state(user_id, "menu")
            self.send_message(
                peer_id,
                "Главное меню открыто. Выберите действие.",
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        if intent == "learn":
            db_handler.ensure_user(user_id)
            db_handler.set_user_state(user_id, "learn")
            with self._lock_for_learn(user_id):
                sl = self._study_lang(user_id)
                lvl = self._study_level(user_id)
                cat = self._study_category(user_id)
                wid = game_logic.pick_random_word_id_for_learn(sl, lvl, user_id, study_category=cat)
                if wid is None:
                    empty_msg = game_logic.format_learn_empty_message(sl, lvl, cat)
                    self.send_message(
                        peer_id,
                        empty_msg,
                        get_main_menu_keyboard().get_keyboard(),
                    )
                    return
                card = game_logic.get_study_card_text(wid)
                if card:
                    self.send_message(peer_id, card, get_main_menu_keyboard().get_keyboard())
                    for extra in gamification.on_learn_card_shown(user_id):
                        self.send_message(peer_id, extra, get_main_menu_keyboard().get_keyboard())
            return

        if intent == "test":
            db_handler.ensure_user(user_id)
            db_handler.set_user_state(user_id, "quiz")
            self._start_quiz(peer_id, user_id, weak_only=False)
            return

        if intent == "weak":
            db_handler.ensure_user(user_id)
            db_handler.set_user_state(user_id, "quiz")
            self._start_quiz(peer_id, user_id, weak_only=True)
            return

        if intent == "theme":
            db_handler.ensure_user(user_id)
            self._send_category_picker(peer_id, user_id, page=0)
            return

        if intent == "quizmode":
            db_handler.ensure_user(user_id)
            self.send_message(
                peer_id,
                "Режим теста: в какую сторону переводить в вопросе?",
                get_quiz_mode_inline_keyboard().get_keyboard(),
            )
            return

        if intent == "quest":
            db_handler.ensure_user(user_id)
            gamification.ensure_daily_quest(user_id)
            self.send_message(
                peer_id,
                gamification.format_quest_message(user_id),
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        if intent == "achievements":
            db_handler.ensure_user(user_id)
            self.send_message(
                peer_id,
                gamification.format_achievements_message(user_id),
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        if intent == "shop":
            db_handler.ensure_user(user_id)
            gamification.ensure_daily_quest(user_id)
            self.send_message(
                peer_id,
                gamification.format_shop_message(user_id),
                get_shop_inline_keyboard().get_keyboard(),
            )
            return

        if intent == "profile":
            db_handler.ensure_user(user_id)
            row = db_handler.get_user(user_id)
            if row:
                sl = self._study_lang(user_id)
                st = self._study_level(user_id)
                cat = self._study_category(user_id)
                qm = self._quiz_mode(user_id)
                theme_line = f"Тема словаря: {cat}\n" if cat else "Тема словаря: все темы\n"
                mode_line = f"Режим теста: {game_logic.get_quiz_mode_label(qm)}\n"
                coins = int(row["coins"] or 0)
                mentor_title = str(row["mentor_title"] or "Новичок")
                best_combo = int(row["best_combo"] or 0)
                game_line = (
                    f"Монеты: {coins}\n"
                    f"Рекорд комбо: {best_combo}\n"
                    f"Титул: {mentor_title}\n"
                )
                analytics = db_handler.get_profile_analytics(user_id)
                streak_line = ""
                stats_block = ""
                if analytics:
                    streak_line = (
                        f"Серия дней с ответом в квизе: {analytics['streak_days']} "
                        f"(последняя активность: "
                        f"{analytics['last_streak_date'] or '—'})\n"
                    )
                    sc, sw = analytics["sum_correct"], analytics["sum_wrong"]
                    tot = sc + sw
                    acc = analytics["accuracy_pct"]
                    acc_s = f"{acc:.0f}%" if acc is not None else "—"
                    stats_block = (
                        f"\n📊 Краткая аналитика\n"
                        f"Слов в прогрессе: {analytics['words_with_progress']}\n"
                        f"Верных ответов в квизе: {sc}, ошибок: {sw} "
                        f"(точность: {acc_s})\n"
                    )
                    if analytics["top_words"]:
                        stats_block += "Чаще всего верно отвечали по:\n"
                        for tw in analytics["top_words"]:
                            stats_block += (
                                f"  • {tw['word_eng']} — {tw['word_rus']} "
                                f"({tw['correct']}✓ / {tw['wrong']}✗)\n"
                            )
                self.send_message(
                    peer_id,
                    (
                        f"👤 Ваш профиль\n"
                        f"Язык изучения: {game_logic.get_lang_label(sl)}\n"
                        f"Уровень владения: {game_logic.get_level_label(st)}\n"
                        f"{theme_line}"
                        f"{mode_line}"
                        f"{game_line}"
                        f"{streak_line}"
                        f"Уровень в игре: {row['level']}\n"
                        f"Опыт (XP): {row['xp']}\n"
                        f"До следующего уровня в игре нужно набрать ещё "
                        f"{game_logic.xp_threshold_for_current_level(int(row['level'])) - int(row['xp'])} XP "
                        f"(порог: {game_logic.xp_threshold_for_current_level(int(row['level']))} XP)."
                        f"{stats_block}"
                    ),
                    get_main_menu_keyboard().get_keyboard(),
                )
            return

        if intent == "lang":
            db_handler.ensure_user(user_id)
            self.send_message(
                peer_id,
                "Выберите язык изучения (словарь и тест будут для этого языка):",
                get_language_inline_keyboard().get_keyboard(),
            )
            return

        if intent == "level":
            db_handler.ensure_user(user_id)
            self.send_message(
                peer_id,
                "Выберите ваш уровень владения — бот будет предлагать слова соответствующей сложности:",
                get_level_inline_keyboard().get_keyboard(),
            )
            return

        if intent == "help":
            self.send_message(
                peer_id,
                HELP_TEXT,
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        if is_meaningless_unknown_input(text, match_score):
            logger.info(
                "Бессмысленный ввод: peer_id=%s score=%.3f text=%r",
                peer_id,
                match_score,
                text[:120],
            )
            self.send_message(
                peer_id,
                FALLBACK_MEANINGLESS_MESSAGE,
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        self.send_message(
            peer_id,
            "Не понял команду. Напишите «Начать» или /menu.\n\n" + HELP_TEXT,
            get_main_menu_keyboard().get_keyboard(),
        )

    def _start_quiz(self, peer_id: int, user_id: int, *, weak_only: bool = False) -> None:
        """Выбирает случайное слово и отправляет вопрос с inline-клавиатурой."""
        study_lang = self._study_lang(user_id)
        study_level = self._study_level(user_id)
        study_category = self._study_category(user_id)
        quiz_mode = self._quiz_mode(user_id)

        if db_handler.count_words(lang=study_lang) < 4:
            self.send_message(
                peer_id,
                f"Для языка «{game_logic.get_lang_label(study_lang)}» в словаре меньше четырёх слов — "
                f"квиз недоступен. Добавьте записи в таблицу words или выберите другой язык (кнопка «Язык»).",
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        pick = game_logic.pick_random_word_id_for_quiz(
            study_lang,
            study_level,
            user_id,
            study_category,
            weak_only=weak_only,
            prefer_weak=not weak_only,
        )
        wid = pick.word_id
        if wid is None:
            self.send_message(
                peer_id,
                "Не удалось подобрать слово для теста (мало слов с учётом темы и уровня). "
                "Смените тему или уровень.",
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        built = game_logic.build_quiz_options(wid, quiz_mode=quiz_mode)
        if not built:
            self.send_message(
                peer_id,
                "Не удалось собрать варианты ответа (мало разных слов в словаре для этой темы). "
                "Смените тему на «Все темы» или выберите другой язык.",
                get_main_menu_keyboard().get_keyboard(),
            )
            return

        question, options = built
        row_u = db_handler.get_user(user_id)
        if row_u and int(row_u["powerup_hint"] or 0):
            correct_label = next((o["label"] for o in options if o["is_correct"]), "")
            if correct_label:
                question = gamification.append_hint_to_question(question, correct_label)
            db_handler.consume_powerup_hint(user_id)

        prefix_parts: List[str] = []
        if weak_only and pick.weak_fallback:
            prefix_parts.append(
                "Пока нет «слабых» слов (где ошибок больше, чем верных) — обычный вопрос из словаря.\n"
            )
        if pick.lost_category:
            prefix_parts.append(
                "В выбранной теме меньше четырёх слов для квиза — пул слов расширен.\n"
            )
        if pick.used_level is None:
            prefix_parts.append(
                "⚠️ Для вашего уровня владения в базе мало слов; вопрос подобран из всего словаря "
                f"языка «{game_logic.get_lang_label(study_lang)}».\n\n"
            )
        prefix = "".join(prefix_parts)
        keyboard = get_quiz_inline_keyboard(wid, options)
        self.send_message(peer_id, prefix + question, keyboard.get_keyboard())
        db_handler.set_quiz_prompt_ts(user_id, int(time.time()))

    def handle_message_event(self, event: Any) -> None:
        """
        Нажатие на callback-кнопку (inline). Обрабатываем action=quiz:
        начисление XP, правка сообщения, при необходимости поздравление с уровнем.
        """
        obj = event.object
        user_id = int(obj.user_id)
        peer_id = int(obj.peer_id)
        event_id = obj.event_id
        conversation_message_id = obj.conversation_message_id

        payload = _parse_payload(obj.payload)
        if not payload:
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": "Пустой ответ"},
            )
            return

        action = payload.get("action")

        if action == "set_lang":
            lang = str(payload.get("lang", "")).strip()
            if lang not in db_handler.SUPPORTED_LANGS:
                self._answer_event(
                    event_id,
                    user_id,
                    peer_id,
                    {"type": "show_snackbar", "text": "Неизвестный язык"},
                )
                return
            db_handler.ensure_user(user_id)
            db_handler.set_user_study_lang(user_id, lang)
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {
                    "type": "show_snackbar",
                    "text": f"Язык: {game_logic.get_lang_label(lang)}",
                },
            )
            self.send_message(
                peer_id,
                f"Язык изучения: {game_logic.get_lang_label(lang)}. "
                f"Откройте «Учить слова» или «Тест».",
            )
            return

        if action == "set_level":
            level = str(payload.get("level", "")).strip()
            if level not in db_handler.SUPPORTED_LEVELS:
                self._answer_event(
                    event_id,
                    user_id,
                    peer_id,
                    {"type": "show_snackbar", "text": "Неизвестный уровень"},
                )
                return
            db_handler.ensure_user(user_id)
            db_handler.set_user_study_level(user_id, level)
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {
                    "type": "show_snackbar",
                    "text": f"Уровень: {game_logic.get_level_label(level)}",
                },
            )
            self.send_message(
                peer_id,
                f"Уровень владения: {game_logic.get_level_label(level)}. "
                f"Слова и тест подстроены под этот уровень (при нехватке слов — из всего словаря языка).",
            )
            return

        if action == "category_page":
            try:
                page = int(payload.get("page", 0))
            except (TypeError, ValueError):
                page = 0
            db_handler.ensure_user(user_id)
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": f"Страница {page + 1}"},
            )
            self._send_category_picker(peer_id, user_id, page=page)
            return

        if action == "set_category":
            raw_cat = payload.get("category", "")
            if raw_cat == "__all__":
                cat_val = ""
            else:
                cat_val = str(raw_cat).strip()
            db_handler.ensure_user(user_id)
            sl = self._study_lang(user_id)
            if cat_val:
                allowed = set(db_handler.list_categories_for_lang(sl))
                if cat_val not in allowed:
                    self._answer_event(
                        event_id,
                        user_id,
                        peer_id,
                        {"type": "show_snackbar", "text": "Неизвестная тема"},
                    )
                    return
            db_handler.set_user_study_category(user_id, cat_val)
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {
                    "type": "show_snackbar",
                    "text": "Все темы" if not cat_val else f"Тема: {cat_val[:40]}",
                },
            )
            confirm = (
                "Тема сброшена: учитываются все категории.\n"
                if not cat_val
                else f"Тема: {cat_val}.\n"
            )
            if cat_val:
                lvl = self._study_level(user_id)
                n_all = db_handler.count_words(lang=sl, category=cat_val)
                n_lvl = db_handler.count_words(lang=sl, category=cat_val, difficulty=lvl)
                if n_all == 0:
                    confirm += (
                        f"⚠️ В теме «{cat_val}» для языка «{game_logic.get_lang_label(sl)}» "
                        f"пока нет слов — выберите другую тему.\n"
                    )
                elif n_lvl == 0:
                    confirm += (
                        f"На уровне «{game_logic.get_level_label(lvl)}» в этой теме слов нет "
                        f"(всего в теме: {n_all}); «Учить» и «Тест» возьмут слова другого уровня.\n"
                    )
            confirm += "Откройте «Учить слова» или «Тест»."
            self.send_message(peer_id, confirm)
            return

        if action == "set_quiz_mode":
            mode = str(payload.get("mode", "")).strip()
            if mode not in db_handler.QUIZ_MODES:
                self._answer_event(
                    event_id,
                    user_id,
                    peer_id,
                    {"type": "show_snackbar", "text": "Неизвестный режим"},
                )
                return
            db_handler.ensure_user(user_id)
            db_handler.set_user_quiz_mode(user_id, mode)
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {
                    "type": "show_snackbar",
                    "text": game_logic.get_quiz_mode_label(mode)[:80],
                },
            )
            self.send_message(
                peer_id,
                f"Режим теста: {game_logic.get_quiz_mode_label(mode)}. Запустите «Тест».",
            )
            return

        if action == "shop_buy":
            item = str(payload.get("item", "")).strip()
            db_handler.ensure_user(user_id)
            ok, err_key = gamification.try_shop_purchase(user_id, item)
            if not ok:
                err_map = {
                    "unknown_item": "Неизвестный товар",
                    "no_user": "Сначала нажмите «Начать»",
                    "hint_already": "Подсказка уже куплена",
                    "double_already": "x2 XP уже активен",
                    "no_coins": "Недостаточно монет",
                }
                self._answer_event(
                    event_id,
                    user_id,
                    peer_id,
                    {
                        "type": "show_snackbar",
                        "text": err_map.get(err_key, "Ошибка покупки"),
                    },
                )
                return
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": "Покупка совершена!"},
            )
            if item == "hint":
                self.send_message(peer_id, gamification.mentor_voice("shop_hint"))
            else:
                self.send_message(peer_id, gamification.mentor_voice("shop_double"))
            return

        if action != "quiz":
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": "Неизвестное действие"},
            )
            return

        word_id = int(payload["word_id"])
        is_correct = bool(payload["is_correct"])

        if conversation_message_id is None:
            logger.warning("message_event без conversation_message_id — правка сообщения невозможна")
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": "Сообщение недоступно для редактирования"},
            )
            return

        if is_correct:
            db_handler.ensure_user(user_id)
            db_handler.record_streak_activity(user_id)
            db_handler.increment_user_progress(user_id, word_id)
            xp_amount, coins_add, had_fast, had_double, gextras = gamification.on_quiz_correct(user_id)
            xp_res = game_logic.add_xp(user_id, xp_amount)

            row_after = db_handler.get_user(user_id)
            combo_n = int(row_after["combo_streak"] or 0) if row_after else 0
            snack = f"Верно! +{xp_amount} XP · +{coins_add} монет"
            if combo_n >= 2:
                snack += f" · x{combo_n}"
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": snack[:250]},
            )

            result_text = (
                "✅ Верно!\n"
                f"+{xp_res.xp_added} XP. Текущий опыт: {xp_res.new_xp}, уровень: {xp_res.new_level}.\n"
                f"Монеты за ответ: +{coins_add}."
            )
            if had_fast:
                result_text += "\n⚡ Ритм: быстрый ответ — бонус к монетам."
            if had_double:
                result_text += "\n✨ Удвоение опыта сработало."
            self._edit_quiz_message(peer_id, conversation_message_id, result_text)

            for msg in gextras:
                self.send_message(peer_id, msg)

            ach_msgs: List[str] = []
            gamification.re_evaluate_achievements(user_id, ach_msgs)
            for m in ach_msgs:
                self.send_message(peer_id, m)

            if xp_res.leveled_up:
                self.send_message(
                    peer_id,
                    f"🎉 Поздравляем! Новый уровень: {xp_res.new_level} "
                    f"(было {xp_res.old_level}). Так держать!",
                )
                self.send_message(
                    peer_id,
                    gamification.mentor_voice("level_up_game", level=xp_res.new_level),
                )
            else:
                self.send_message(peer_id, "Выберите следующее действие в меню ниже.")
        else:
            self._answer_event(
                event_id,
                user_id,
                peer_id,
                {"type": "show_snackbar", "text": "Неверно"},
            )
            db_handler.ensure_user(user_id)
            db_handler.record_streak_activity(user_id)
            gamification.on_quiz_wrong(user_id)
            db_handler.increment_user_wrong(user_id, word_id)
            word = db_handler.get_word_by_id(word_id)
            extra = ""
            if word:
                extra = f"\nПравильный вариант: {word['word_rus']} — {word['word_eng']}"
            self._edit_quiz_message(
                peer_id,
                conversation_message_id,
                f"❌ Неверно.{extra}",
            )
            self.send_message(peer_id, "Попробуйте ещё раз или выберите другой раздел в меню.")

    def _answer_event(
        self,
        event_id: str,
        user_id: int,
        peer_id: int,
        event_data_obj: Dict[str, Any],
    ) -> None:
        """Ответ на callback: снимает загрузку с кнопки; event_data — JSON для snackbar и др."""
        self._vk.messages.sendMessageEventAnswer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            event_data=json.dumps(event_data_obj, ensure_ascii=False),
        )

    def _edit_quiz_message(
        self,
        peer_id: int,
        conversation_message_id: int,
        new_text: str,
    ) -> None:
        """Редактирует сообщение с вопросом: показывает результат, убирает клавиатуру."""
        try:
            self._vk.messages.edit(
                peer_id=peer_id,
                conversation_message_id=conversation_message_id,
                message=new_text,
                keyboard=get_empty_keyboard_json(),
                group_id=config.VK_GROUP_ID,
            )
        except Exception as exc:
            logger.exception("messages.edit не удался: %s", exc)


def run_bot() -> None:
    """Инициализация VkApi, Long Poll и основной цикл."""
    db_handler.init_db()

    vk_session = vk_api.VkApi(
        token=config.VK_GROUP_TOKEN,
        api_version=config.VK_API_VERSION,
    )
    vk = vk_session.get_api()
    publish_bot_commands(vk)
    longpoll = VkBotLongPoll(vk_session, config.VK_GROUP_ID)
    router = Router(vk)

    logger.info("Бот запущен, group_id=%s", config.VK_GROUP_ID)

    for event in longpoll.listen():
        try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                router.handle_message_new(event)
            elif event.type == VkBotEventType.MESSAGE_EVENT:
                router.handle_message_event(event)
        except Exception as exc:
            logger.exception("Ошибка обработки события: %s", exc)


if __name__ == "__main__":
    run_bot()
