# -*- coding: utf-8 -*-
"""
Игровая логика: расчёт опыта (XP), уровней и сборка данных для квиза.

Формула порога уровня (по ТЗ): необходимый для повышения опыт = текущий_уровень * 100.
При достижении порога уровень увеличивается на 1, остаток XP переносится (вычитается
пройденный порог).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

import db_handler
from keyboards import QuizOption

# Подписи языков для карточек и вопросов (код в БД — колонка words.lang)
LANG_LABELS: dict[str, str] = {
    "en": "Английский",
    "de": "Немецкий",
    "fr": "Французский",
    "zh": "Китайский (мандарин, упрощ.)",
    "es": "Испанский",
    "it": "Итальянский",
    "pt": "Португальский",
    "ja": "Японский",
}

# Уровни сложности словаря (совпадают с words.difficulty)
LEVEL_LABELS: dict[str, str] = {
    "beginner": "Начальный (A1–A2)",
    "intermediate": "Средний (B1–B2)",
    "advanced": "Продвинутый (C1–C2)",
}


def get_lang_label(lang_code: str) -> str:
    """Человекочитаемое название языка по коду."""
    return LANG_LABELS.get(lang_code, lang_code)


def get_quiz_mode_label(mode: str) -> str:
    """Подпись режима квиза для профиля и подсказок."""
    if mode == "to_foreign":
        return "С русского на иностранный"
    return "Иностранное слово → русский"


def get_level_label(level_code: str) -> str:
    """Человекочитаемое название уровня владения."""
    return LEVEL_LABELS.get(level_code, level_code)


@dataclass
class QuizPick:
    """Результат выбора слова для квиза (уровень колоды, подсказки при расширении пула)."""

    used_level: Optional[str]
    word_id: Optional[int]
    lost_category: bool = False
    lost_level: bool = False
    weak_fallback: bool = False


@dataclass
class XpResult:
    """Результат начисления опыта для отображения пользователю и логики бота."""

    user_id: int
    xp_added: int
    new_xp: int
    new_level: int
    old_level: int
    leveled_up: bool
    levels_gained: int


def xp_threshold_for_current_level(level: int) -> int:
    """
    Сколько опыта нужно накопить на текущем уровне, чтобы перейти на следующий.
    По ТЗ: текущий уровень * 100.
    """
    return max(1, level) * 100


def add_xp(user_id: int, amount: int, db_path: Optional[str] = None) -> XpResult:
    """
    Начисляет пользователю `amount` XP и при необходимости повышает уровень.

    Алгоритм:
    1. Загрузить текущие xp и level.
    2. Прибавить amount.
    3. Пока xp >= порога (level * 100), вычесть порог и увеличить level на 1.

    :param user_id: VK user id.
    :param amount: величина прироста (для верного ответа в квизе — 10).
    :returns: структура XpResult с флагом leveled_up и числом gained levels.
    """
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        db_handler.ensure_user(user_id, db_path=db_path)
        row = db_handler.get_user(user_id, db_path=db_path)
    assert row is not None

    xp = int(row["xp"]) + int(amount)
    level = int(row["level"])
    old_level = level
    levels_gained = 0

    # Повышение уровня: «остаток» xp сохраняется после вычитания порога
    while xp >= xp_threshold_for_current_level(level):
        need = xp_threshold_for_current_level(level)
        xp -= need
        level += 1
        levels_gained += 1

    db_handler.update_user_xp_level(user_id, xp, level, db_path=db_path)

    return XpResult(
        user_id=user_id,
        xp_added=amount,
        new_xp=xp,
        new_level=level,
        old_level=old_level,
        leveled_up=level > old_level,
        levels_gained=levels_gained,
    )


def _collect_unique_labels(
    pool: List[str],
    correct: str,
    need: int = 3,
) -> List[str]:
    """До `need` уникальных подписей, отличных от правильного ответа."""
    seen = {correct.casefold()}
    out: List[str] = []
    for label in pool:
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
        if len(out) >= need:
            break
    return out


def _gather_rus_distractors(
    word_id: int,
    lang: str,
    difficulty: str,
    category: Optional[str],
    correct_rus: str,
    db_path: Optional[str] = None,
) -> List[str]:
    """
    Дистракторы для режима «на русский».
    Сначала та же тема и сложность; при нехватке — без темы, затем только язык.
    """
    tiers: List[Tuple[Optional[str], Optional[str], Optional[str]]] = [
        (lang, difficulty, category),
        (lang, difficulty, None),
        (lang, None, None),
    ]
    seen_cats: set[Tuple[Optional[str], Optional[str], Optional[str]]] = set()
    pool: List[str] = []
    for tier in tiers:
        if tier in seen_cats:
            continue
        seen_cats.add(tier)
        lang_f, diff_f, cat_f = tier
        batch = db_handler.get_distractor_rus_words(
            word_id, 32, lang=lang_f, difficulty=diff_f, category=cat_f, db_path=db_path
        )
        pool.extend(batch)
        if len(_collect_unique_labels(pool, correct_rus, 3)) >= 3:
            break
    return _collect_unique_labels(pool, correct_rus, 3)


def _gather_eng_distractors(
    word_id: int,
    lang: str,
    difficulty: str,
    category: Optional[str],
    correct_eng: str,
    db_path: Optional[str] = None,
) -> List[str]:
    """Дистракторы для режима «с русского на язык» (с ослаблением фильтров)."""
    tiers: List[Tuple[Optional[str], Optional[str], Optional[str]]] = [
        (lang, difficulty, category),
        (lang, difficulty, None),
        (lang, None, None),
    ]
    seen_cats: set[Tuple[Optional[str], Optional[str], Optional[str]]] = set()
    pool: List[str] = []
    for tier in tiers:
        if tier in seen_cats:
            continue
        seen_cats.add(tier)
        lang_f, diff_f, cat_f = tier
        batch = db_handler.get_distractor_eng_words(
            word_id, 32, lang=lang_f, difficulty=diff_f, category=cat_f, db_path=db_path
        )
        pool.extend(batch)
        if len(_collect_unique_labels(pool, correct_eng, 3)) >= 3:
            break
    return _collect_unique_labels(pool, correct_eng, 3)


def build_quiz_options(
    word_id: int,
    quiz_mode: str = "to_rus",
    db_path: Optional[str] = None,
) -> Optional[Tuple[str, List[QuizOption]]]:
    """
    Формирует текст вопроса и 4 варианта ответа (1 верный + 3 дистрактора из БД).

    quiz_mode: to_rus — перевод на русский; to_foreign — дан русский перевод, выбрать слово на языке.

    :returns: (вопрос_строка, список из 4 QuizOption) или None, если слова в БД мало.
    """
    word = db_handler.get_word_by_id(word_id, db_path=db_path)
    if word is None:
        return None

    lang = str(word["lang"])
    difficulty = str(word["difficulty"])
    wcat = str(word["category"]).strip() or None
    correct_rus = str(word["word_rus"])
    correct_eng = str(word["word_eng"])
    label = get_lang_label(lang)
    lvl = get_level_label(str(word["difficulty"]))

    if quiz_mode == "to_foreign":
        unique = _gather_eng_distractors(
            word_id, lang, difficulty, wcat, correct_eng, db_path=db_path
        )
        if len(unique) < 3:
            return None
        options: List[QuizOption] = [{"label": correct_eng, "is_correct": True}]
        for w in unique[:3]:
            options.append({"label": w, "is_correct": False})
        random.shuffle(options)
        question = (
            f"({label}, {lvl}) Дано по-русски: «{correct_rus}».\n"
            f"Выберите слово на языке изучения:"
        )
        return question, options

    unique_rus = _gather_rus_distractors(
        word_id, lang, difficulty, wcat, correct_rus, db_path=db_path
    )
    if len(unique_rus) < 3:
        return None

    options_rus: List[QuizOption] = [{"label": correct_rus, "is_correct": True}]
    for rus in unique_rus[:3]:
        options_rus.append({"label": rus, "is_correct": False})

    random.shuffle(options_rus)
    foreign = word["word_eng"]
    question = (
        f"({label}, {lvl}) Переведите слово: «{foreign}»\n"
        f"Выберите правильный перевод:"
    )
    return question, options_rus


def pick_random_word_id_for_quiz(
    study_lang: str,
    study_level: str,
    user_id: int,
    study_category: str = "",
    *,
    weak_only: bool = False,
    prefer_weak: bool = True,
    db_path: Optional[str] = None,
) -> QuizPick:
    """
    Случайное слово для квиза с учётом языка, уровня, темы и опционально «слабых» слов.

    Слабое слово: в user_progress correct_answers < wrong_answers.
    При weak_only без слабых — обычный выбор с флагом weak_fallback.
    В обычном режиме с вероятностью ~50 % предпочитает слабое слово, если оно есть.
    """
    cat = study_category.strip() or None

    def cnt(level: Optional[str], category: Optional[str]) -> int:
        return db_handler.count_words(
            lang=study_lang,
            difficulty=level,
            category=category,
            db_path=db_path,
        )

    def pick_id(level: Optional[str], category: Optional[str]) -> Optional[int]:
        return db_handler.get_random_word_id(
            lang=study_lang,
            difficulty=level,
            category=category,
            db_path=db_path,
        )

    def try_weak_pick() -> Optional[Tuple[Optional[str], int]]:
        """Возвращает (used_level, word_id) или None."""
        attempts: List[Tuple[Optional[str], Optional[str]]] = []
        if cat:
            attempts.append((study_level, cat))
            attempts.append((None, cat))
        attempts.append((study_level, None))
        attempts.append((None, None))
        tried: set[Tuple[Optional[str], Optional[str]]] = set()
        for lev, c in attempts:
            key = (lev, c)
            if key in tried:
                continue
            tried.add(key)
            if db_handler.count_weak_quiz_words(user_id, study_lang, lev, c, db_path) < 1:
                continue
            wid = db_handler.get_random_weak_word_id(
                user_id, study_lang, difficulty=lev, category=c, db_path=db_path
            )
            if wid is None:
                continue
            used = study_level if lev == study_level else None
            return used, wid
        return None

    if weak_only:
        wr = try_weak_pick()
        if wr is not None:
            return QuizPick(wr[0], wr[1], False, False, False)
        # fallback на обычный пул
        res = _pick_normal_quiz_word(study_lang, study_level, cat, cnt, pick_id)
        if res.word_id is None:
            return res
        return QuizPick(
            res.used_level,
            res.word_id,
            res.lost_category,
            res.lost_level,
            weak_fallback=True,
        )

    if prefer_weak and random.random() < 0.5:
        wr = try_weak_pick()
        if wr is not None:
            return QuizPick(wr[0], wr[1], False, False, False)

    return _pick_normal_quiz_word(study_lang, study_level, cat, cnt, pick_id)


def _pick_normal_quiz_word(
    study_lang: str,
    study_level: str,
    cat: Optional[str],
    cnt,
    pick_id,
) -> QuizPick:
    """Подбор слова для квиза с расширением пула (тема → весь уровень → язык)."""
    attempts: List[Tuple[Optional[str], Optional[str]]] = []
    if cat:
        attempts.append((study_level, cat))
        attempts.append((study_level, None))
        attempts.append((None, cat))
        attempts.append((None, None))
    else:
        attempts.append((study_level, None))
        attempts.append((None, None))

    tried: set[Tuple[Optional[str], Optional[str]]] = set()
    chosen: Optional[Tuple[Optional[str], Optional[str], int]] = None
    for lev, c in attempts:
        key = (lev, c)
        if key in tried:
            continue
        tried.add(key)
        if cnt(lev, c) < 4:
            continue
        wid = pick_id(lev, c)
        if wid is None:
            continue
        chosen = (lev, c, wid)
        break

    if chosen is None:
        return QuizPick(None, None, False, False, False)

    lev, c, wid = chosen
    used_level = study_level if lev == study_level else None
    lost_category = bool(cat) and c is None
    lost_level = lev is None
    return QuizPick(used_level, wid, lost_category, lost_level, False)


def format_learn_empty_message(
    study_lang: str,
    study_level: str,
    study_category: str,
    db_path: Optional[str] = None,
) -> str:
    """Пояснение, почему не удалось выдать карточку «Учить слова»."""
    cat = (study_category or "").strip()
    if not cat:
        return (
            f"Словарь пуст для языка «{get_lang_label(study_lang)}» и уровня "
            f"«{get_level_label(study_level)}». Смените язык или уровень."
        )
    n_all = db_handler.count_words(lang=study_lang, category=cat, db_path=db_path)
    n_lvl = db_handler.count_words(
        lang=study_lang, category=cat, difficulty=study_level, db_path=db_path
    )
    if n_all == 0:
        return (
            f"В теме «{cat}» для языка «{get_lang_label(study_lang)}» нет слов. "
            f"Выберите другую тему («Тема») или язык."
        )
    if n_lvl == 0:
        return (
            f"В теме «{cat}» нет слов уровня «{get_level_label(study_level)}» "
            f"(в теме всего {n_all} слов другого уровня). Смените «Уровень» или «Тема»."
        )
    return (
        f"Не удалось подобрать слово в теме «{cat}». "
        f"Попробуйте ещё раз или смените тему («Тема»)."
    )


def pick_random_word_id_for_learn(
    study_lang: str,
    study_level: str,
    user_id: int,
    study_category: str = "",
    db_path: Optional[str] = None,
) -> Optional[int]:
    """
    Следующее слово для карточки «Учить слова».

    Слова не повторяются, пока не показаны все слова выбранной «колоды» (язык + уровень,
    либо весь язык при отсутствии слов на уровне). Непустая study_category сужает колоду темой.
    """
    return db_handler.next_learn_card_word_id(
        user_id,
        study_lang,
        study_level,
        study_category=study_category,
        db_path=db_path,
    )


def get_study_card_text(word_id: int, db_path: Optional[str] = None) -> Optional[str]:
    """Текст карточки для режима «Учить слова» (иностранное слово + русский перевод)."""
    word = db_handler.get_word_by_id(word_id, db_path=db_path)
    if word is None:
        return None
    lang = str(word["lang"])
    label = get_lang_label(lang)
    lvl = get_level_label(str(word["difficulty"]))
    return (
        f"📚 Карточка слова\n"
        f"Язык: {label}\n"
        f"Уровень: {lvl}\n"
        f"Слово: {word['word_eng']}\n"
        f"Перевод: {word['word_rus']}\n"
        f"Категория: {word['category']}"
    )
