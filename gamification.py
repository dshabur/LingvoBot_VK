# -*- coding: utf-8 -*-
"""
Геймификация: квест дня, достижения, монеты/магазин, наставник, ритм (комбо, быстрый ответ).
Логика опирается на db_handler и game_logic.add_xp.
"""

from __future__ import annotations

import random
import time
from datetime import date
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

import db_handler
import game_logic

QuestKind = Literal["learn", "quiz_correct", "combo", "fast"]


class DailyQuestDef(TypedDict):
    target: int
    desc: str
    kind: QuestKind


# id → задание дня (случайный выбор при смене календарного дня)
DAILY_QUESTS: Dict[str, DailyQuestDef] = {
    "learn3": {
        "target": 3,
        "desc": "Откройте 3 карточки «Учить слова» за сегодня.",
        "kind": "learn",
    },
    "learn10": {
        "target": 10,
        "desc": "Изучите 10 карточек «Учить слова» за сегодня.",
        "kind": "learn",
    },
    "learn20": {
        "target": 20,
        "desc": "Изучите 20 карточек «Учить слова» за сегодня.",
        "kind": "learn",
    },
    "qc4": {
        "target": 4,
        "desc": "Дайте 4 верных ответа в тесте за сегодня.",
        "kind": "quiz_correct",
    },
    "qc6": {
        "target": 6,
        "desc": "Дайте 6 верных ответов в тесте за сегодня.",
        "kind": "quiz_correct",
    },
    "qc10": {
        "target": 10,
        "desc": "Дайте 10 верных ответов в тесте за сегодня.",
        "kind": "quiz_correct",
    },
    "combo5": {
        "target": 5,
        "desc": "В тесте: 5 верных ответов подряд без ошибок (комбо ×5).",
        "kind": "combo",
    },
    "combo8": {
        "target": 8,
        "desc": "В тесте: 8 верных ответов подряд без ошибок (комбо ×8).",
        "kind": "combo",
    },
    "fast3": {
        "target": 3,
        "desc": "Дайте 3 быстрых верных ответа в тесте (до 18 с на вопрос).",
        "kind": "fast",
    },
    "fast5": {
        "target": 5,
        "desc": "Дайте 5 быстрых верных ответов в тесте (до 18 с на вопрос).",
        "kind": "fast",
    },
}

# Достижения: id → (заголовок, описание)
ACHIEVEMENTS: Dict[str, Tuple[str, str]] = {
    "first_win": ("Первый шаг", "Первый верный ответ в квизе."),
    "streak_3": ("Три дня огня", "Серия активности в квизе: 3 дня."),
    "streak_7": ("Неделя силы", "Серия активности в квизе: 7 дней."),
    "level_game_5": ("Ветеран тренировок", "Игровой уровень не ниже 5."),
    "coins_100": ("Копилка", "Заработано монет за всё время: не меньше 100."),
    "fast_5": ("Молния", "5 быстрых верных ответов (до 18 с с момента вопроса)."),
    "quest_3": ("Исполнитель", "Завершено 3 ежедневных квеста."),
    "combo_5": ("Ритм", "Комбо из 5 верных подряд хотя бы раз."),
}


def mentor_voice(event: str, **kwargs: Any) -> str:
    """Короткие игровые подсказки бота (квест, достижения, ритм, магазин)."""
    if event == "quest_done":
        return (
            "Отлично! Квест дня закрыт — вы реально прокачиваетесь. "
            "Заберите награду в сообщении выше и отдохните пару минут 💪"
        )
    if event == "achievement":
        title = kwargs.get("title", "")
        return f"Ого, открыто достижение «{title}»! Так держать."
    if event == "level_up_game":
        lv = kwargs.get("level", "")
        return f"Новый игровой уровень {lv}! Не останавливайтесь."
    if event == "fast_bonus":
        return "Молниеносно! Ритм — половина успеха ⚡"
    if event == "combo":
        n = kwargs.get("n", 0)
        return f"Комбо ×{n}! Вы в потоке 🔥"
    if event == "shop_hint":
        return "Подсказка куплена. В следующем тесте будет показана первая буква верного ответа."
    if event == "shop_double":
        return "x2 XP на следующий верный ответ — используйте с умом!"
    return "Так держать!"


def title_for_achievement_count(n: int) -> str:
    """Титул игрока по числу достижений."""
    if n >= 7:
        return "Полиглот"
    if n >= 5:
        return "Знаток"
    if n >= 3:
        return "Ученик"
    return "Новичок"


def refresh_mentor_title(user_id: int, db_path: Optional[str] = None) -> str:
    n = db_handler.count_achievements(user_id, db_path=db_path)
    t = title_for_achievement_count(n)
    db_handler.set_mentor_title(user_id, t, db_path=db_path)
    return t


def ensure_daily_quest(user_id: int, db_path: Optional[str] = None) -> None:
    """Выдаёт новый квест на календарный день при необходимости."""
    today = date.today().isoformat()
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        return
    qd = row["daily_quest_date"]
    qid = row["daily_quest_id"]
    if str(qd or "") == today and qid and str(qid) in DAILY_QUESTS:
        return
    new_id = random.choice(list(DAILY_QUESTS.keys()))
    db_handler.set_daily_quest(user_id, today, new_id, 0, 0, db_path=db_path)


def daily_quest_snapshot(user_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        return None
    qid = str(row["daily_quest_id"] or "")
    defn = DAILY_QUESTS.get(qid)
    if not defn:
        return None
    prog = int(row["daily_quest_progress"] or 0)
    done = int(row["daily_quest_done"] or 0)
    return {
        "id": qid,
        "target": defn["target"],
        "desc": defn["desc"],
        "kind": defn["kind"],
        "progress": prog,
        "done": bool(done),
    }


def format_quest_bar(progress: int, target: int) -> str:
    if target <= 0:
        return ""
    filled = min(target, max(0, progress))
    width = min(target, 20)
    if target > 20:
        filled_w = min(width, int(filled / target * width))
        return "█" * filled_w + "░" * (width - filled_w)
    return "█" * filled + "░" * (target - filled)


def format_quest_message(user_id: int, db_path: Optional[str] = None) -> str:
    ensure_daily_quest(user_id, db_path=db_path)
    snap = daily_quest_snapshot(user_id, db_path=db_path)
    if not snap:
        return "🎯 Квест дня скоро будет доступен. Нажмите «Начать»."
    if snap["done"]:
        return (
            "🎯 Квест дня уже выполнен сегодня.\n"
            f"{snap['desc']}\n"
            "Загляните завтра за новым заданием!"
        )
    bar = format_quest_bar(snap["progress"], snap["target"])
    hint = ""
    if snap["kind"] == "combo":
        hint = "\n💡 Неверный ответ в тесте обнуляет серию комбо для этого квеста."
    elif snap["kind"] == "fast":
        hint = "\n💡 Быстрый ответ — верно и не позже 18 секунд с показа вопроса."
    return (
        f"🎯 Квест дня\n{snap['desc']}\n"
        f"Прогресс: {snap['progress']}/{snap['target']}\n{bar}{hint}"
    )


def format_achievements_message(user_id: int, db_path: Optional[str] = None) -> str:
    codes = db_handler.list_achievement_codes(user_id, db_path=db_path)
    if not codes:
        return (
            "🏅 Достижения пока пусты.\n"
            "Ответьте в квизе верно, выполняйте квесты и держите серию — и они появятся."
        )
    lines = [f"🏅 Достижения ({len(codes)}/{len(ACHIEVEMENTS)})\n"]
    for c in codes:
        meta = ACHIEVEMENTS.get(c, (c, ""))
        lines.append(f"• {meta[0]} — {meta[1]}")
    return "\n".join(lines)


def format_shop_message(user_id: int, db_path: Optional[str] = None) -> str:
    row = db_handler.get_user(user_id, db_path=db_path)
    coins = int(row["coins"] or 0) if row else 0
    return (
        f"🛒 Магазин наград\n"
        f"У вас: {coins} монет.\n\n"
        "• Подсказка (35 💰) — в следующем вопросе теста: первая буква верного варианта.\n"
        "• x2 XP (50 💰) — следующий верный ответ в квизе даст удвоенный опыт.\n\n"
        "Выберите кнопку ниже."
    )


SHOP_PRICES = {"hint": 35, "double_xp": 50}


def try_shop_purchase(
    user_id: int,
    item: str,
    db_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Покупка в магазине. item: hint | double_xp
    Возвращает (успех, ключ сообщения или текст ошибки).
    """
    if item not in SHOP_PRICES:
        return False, "unknown_item"
    price = SHOP_PRICES[item]
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        return False, "no_user"
    if int(row["powerup_hint"] or 0) and item == "hint":
        return False, "hint_already"
    if int(row["powerup_double_xp"] or 0) and item == "double_xp":
        return False, "double_already"
    if not db_handler.try_spend_coins(user_id, price, db_path=db_path):
        return False, "no_coins"
    if item == "hint":
        db_handler.set_powerup_hint(user_id, 1, db_path=db_path)
    else:
        db_handler.set_powerup_double_xp(user_id, 1, db_path=db_path)
    return True, item


def _quest_def(qid: str) -> Optional[DailyQuestDef]:
    return DAILY_QUESTS.get(qid)


def _quest_coin_bonus(target: int) -> int:
    if target >= 20:
        return 40
    if target >= 10:
        return 30
    if target >= 8:
        return 28
    return 25


def _quest_xp_bonus(target: int) -> int:
    if target >= 20:
        return 25
    if target >= 10:
        return 20
    return 15


def _maybe_finish_quest(
    user_id: int, msgs: List[str], progress: int, target: int, db_path: Optional[str] = None
) -> None:
    if progress >= target:
        _finalize_quest(user_id, msgs, target=target, db_path=db_path)


def _finalize_quest(
    user_id: int,
    msgs: List[str],
    *,
    target: int = 0,
    db_path: Optional[str] = None,
) -> None:
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None or int(row["daily_quest_done"] or 0):
        return
    if target <= 0:
        qid = str(row["daily_quest_id"] or "")
        defn = _quest_def(qid)
        target = defn["target"] if defn else 0
    coins = _quest_coin_bonus(target)
    xp = _quest_xp_bonus(target)
    db_handler.complete_daily_quest_reward(user_id, coins, 0, db_path=db_path)
    game_logic.add_xp(user_id, xp, db_path=db_path)
    msgs.append(
        f"🎉 Квест дня выполнен!\n"
        f"+{coins} монет, +{xp} XP.\n"
        + mentor_voice("quest_done")
    )
    _check_achievements(user_id, msgs, db_path=db_path)


def _advance_daily_quest(
    user_id: int,
    msgs: List[str],
    *,
    combo: int = 0,
    fast: bool = False,
    db_path: Optional[str] = None,
) -> None:
    """Прогресс квестов, завязанных на тест (верные ответы, комбо, быстрые ответы)."""
    ensure_daily_quest(user_id, db_path=db_path)
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None or int(row["daily_quest_done"] or 0):
        return
    qid = str(row["daily_quest_id"] or "")
    defn = _quest_def(qid)
    if not defn:
        return

    kind = defn["kind"]
    target = defn["target"]

    if kind == "quiz_correct":
        db_handler.bump_daily_quest_progress(user_id, 1, db_path=db_path)
        row2 = db_handler.get_user(user_id, db_path=db_path)
        prog = int(row2["daily_quest_progress"] or 0) if row2 else 0
        _maybe_finish_quest(user_id, msgs, prog, target, db_path=db_path)
    elif kind == "fast":
        if not fast:
            return
        db_handler.bump_daily_quest_progress(user_id, 1, db_path=db_path)
        row2 = db_handler.get_user(user_id, db_path=db_path)
        prog = int(row2["daily_quest_progress"] or 0) if row2 else 0
        _maybe_finish_quest(user_id, msgs, prog, target, db_path=db_path)
    elif kind == "combo":
        db_handler.set_daily_quest_progress(user_id, combo, db_path=db_path)
        _maybe_finish_quest(user_id, msgs, combo, target, db_path=db_path)


def on_learn_card_shown(user_id: int, db_path: Optional[str] = None) -> List[str]:
    """Увеличить прогресс квеста на изучение карточек."""
    ensure_daily_quest(user_id, db_path=db_path)
    msgs: List[str] = []
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None or int(row["daily_quest_done"] or 0):
        return msgs
    qid = str(row["daily_quest_id"] or "")
    defn = _quest_def(qid)
    if not defn or defn["kind"] != "learn":
        return msgs
    target = defn["target"]
    db_handler.bump_daily_quest_progress(user_id, 1, db_path=db_path)
    row2 = db_handler.get_user(user_id, db_path=db_path)
    prog = int(row2["daily_quest_progress"] or 0) if row2 else 0
    if prog >= target:
        _finalize_quest(user_id, msgs, target=target, db_path=db_path)
    return msgs


def on_quiz_correct(
    user_id: int,
    db_path: Optional[str] = None,
) -> Tuple[int, int, bool, bool, List[str]]:
    """
    Обрабатывает верный ответ: время реакции, комбо, монеты, квест, достижения.
    Возвращает (xp_amount, coins_added, had_fast_bonus, had_double_xp, extra_messages).
    """
    extra: List[str] = []
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        return 10, 0, False, False, extra

    prompt_ts = int(row["quiz_prompt_ts"] or 0)
    now = int(time.time())
    fast = bool(prompt_ts and (now - prompt_ts) <= 18)

    combo, best = db_handler.increment_combo_on_correct(user_id, db_path=db_path)

    double_xp = db_handler.take_powerup_double_xp(user_id, db_path=db_path)
    xp_amount = 20 if double_xp else 10

    coins_add = 3
    if fast:
        coins_add += 5
        db_handler.increment_fast_correct(user_id, db_path=db_path)
    if combo >= 3 and combo % 3 == 0:
        coins_add += 2

    db_handler.grant_coins(user_id, coins_add, db_path=db_path)
    db_handler.clear_quiz_prompt_ts(user_id, db_path=db_path)

    _advance_daily_quest(user_id, extra, combo=combo, fast=fast, db_path=db_path)

    if fast:
        extra.insert(0, "⚡ Быстрый ответ! +5 монет.\n" + mentor_voice("fast_bonus"))
    if combo >= 3 and combo % 3 == 0:
        extra.append(mentor_voice("combo", n=combo))
    if double_xp:
        extra.append("Удвоение XP сработало на этом ответе.")

    return xp_amount, coins_add, fast, double_xp, extra


def re_evaluate_achievements(user_id: int, msgs: List[str], db_path: Optional[str] = None) -> None:
    """Проверка достижений после начисления XP (игровой уровень)."""
    _check_achievements(user_id, msgs, db_path=db_path)


def on_quiz_wrong(user_id: int, db_path: Optional[str] = None) -> None:
    row = db_handler.get_user(user_id, db_path=db_path)
    if row and not int(row["daily_quest_done"] or 0):
        qid = str(row["daily_quest_id"] or "")
        defn = _quest_def(qid)
        if defn and defn["kind"] == "combo":
            db_handler.set_daily_quest_progress(user_id, 0, db_path=db_path)
    db_handler.reset_combo_streak(user_id, db_path=db_path)
    db_handler.clear_quiz_prompt_ts(user_id, db_path=db_path)


def _check_achievements(user_id: int, msgs: List[str], db_path: Optional[str] = None) -> None:
    row = db_handler.get_user(user_id, db_path=db_path)
    if row is None:
        return
    analytics = db_handler.get_profile_analytics(user_id, db_path=db_path)
    sum_c = analytics["sum_correct"] if analytics else 0
    streak = int(row["streak_days"] or 0)
    glevel = int(row["level"] or 1)
    life_coins = int(row["lifetime_coins"] or 0)
    fast_n = int(row["fast_correct_count"] or 0)
    quests_done = int(row["quests_completed_total"] or 0)
    best_c = int(row["best_combo"] or 0)

    checks: List[Tuple[str, bool]] = [
        ("first_win", sum_c >= 1),
        ("streak_3", streak >= 3),
        ("streak_7", streak >= 7),
        ("level_game_5", glevel >= 5),
        ("coins_100", life_coins >= 100),
        ("fast_5", fast_n >= 5),
        ("quest_3", quests_done >= 3),
        ("combo_5", best_c >= 5),
    ]
    for code, cond in checks:
        if not cond:
            continue
        if db_handler.try_insert_achievement(user_id, code, db_path=db_path):
            title, _desc = ACHIEVEMENTS.get(code, (code, ""))
            msgs.append(f"🏅 Новое достижение: «{title}»!\n{mentor_voice('achievement', title=title)}")
            refresh_mentor_title(user_id, db_path=db_path)


def first_letter_hint(label: str) -> str:
    """Первая видимая буква/иероглиф для подсказки."""
    for ch in label:
        if ch.strip():
            return ch
    return "?"


def append_hint_to_question(question: str, correct_label: str) -> str:
    fl = first_letter_hint(correct_label)
    return f"💡 Подсказка: первая буква верного варианта — «{fl}»\n\n" + question
