# -*- coding: utf-8 -*-
"""
Инкапсуляция работы с SQLite: создание схемы, CRUD-операции.

Используется встроенный модуль sqlite3. Перед использованием внешних ключей
включается PRAGMA foreign_keys = ON.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import config

# SQL-скрипты создания таблиц (требование ТЗ)
SQL_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    state TEXT NOT NULL DEFAULT 'menu',
    study_lang TEXT NOT NULL DEFAULT 'en',
    study_level TEXT NOT NULL DEFAULT 'beginner',
    study_category TEXT NOT NULL DEFAULT '',
    quiz_mode TEXT NOT NULL DEFAULT 'to_rus',
    streak_days INTEGER NOT NULL DEFAULT 0,
    last_streak_date TEXT,
    coins INTEGER NOT NULL DEFAULT 0,
    lifetime_coins INTEGER NOT NULL DEFAULT 0,
    combo_streak INTEGER NOT NULL DEFAULT 0,
    best_combo INTEGER NOT NULL DEFAULT 0,
    quiz_prompt_ts INTEGER NOT NULL DEFAULT 0,
    powerup_hint INTEGER NOT NULL DEFAULT 0,
    powerup_double_xp INTEGER NOT NULL DEFAULT 0,
    daily_quest_date TEXT,
    daily_quest_id TEXT,
    daily_quest_progress INTEGER NOT NULL DEFAULT 0,
    daily_quest_done INTEGER NOT NULL DEFAULT 0,
    quests_completed_total INTEGER NOT NULL DEFAULT 0,
    fast_correct_count INTEGER NOT NULL DEFAULT 0,
    mentor_title TEXT NOT NULL DEFAULT 'Новичок'
);
"""

SQL_CREATE_USER_ACHIEVEMENTS = """
CREATE TABLE IF NOT EXISTS user_achievements (
    user_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    unlocked_at TEXT NOT NULL,
    PRIMARY KEY (user_id, code),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

SQL_CREATE_WORDS = """
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_eng TEXT NOT NULL,
    word_rus TEXT NOT NULL,
    category TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT 'en',
    difficulty TEXT NOT NULL DEFAULT 'beginner'
);
"""

# Составной первичный ключ (user_id, word_id) удобен для UPSERT прогресса
SQL_CREATE_USER_PROGRESS = """
CREATE TABLE IF NOT EXISTS user_progress (
    user_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    wrong_answers INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, word_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);
"""

# Слова, уже показанные в режиме «Учить слова» (чтобы не повторять до конца «колоды»)
SQL_CREATE_USER_LEARN_SEEN = """
CREATE TABLE IF NOT EXISTS user_learn_seen (
    user_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, word_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);
"""

# Коды языков изучения (совпадают с колонкой words.lang)
SUPPORTED_LANGS: Tuple[str, ...] = ("en", "de", "fr", "zh", "es", "it", "pt", "ja")

# Уровни владения (совпадают с words.difficulty и users.study_level)
SUPPORTED_LEVELS: Tuple[str, ...] = ("beginner", "intermediate", "advanced")

# Режим квиза: иностранное → русский или русский → иностранное
QUIZ_MODES: Tuple[str, ...] = ("to_rus", "to_foreign")

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Проверяет наличие столбца (для миграций существующих БД)."""
    cur = conn.execute(f"PRAGMA table_info({table});")
    return any(str(row[1]) == column for row in cur.fetchall())


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Добавляет новые столбцы к старым установкам без потери данных."""
    if not _column_exists(conn, "users", "study_lang"):
        conn.execute(
            "ALTER TABLE users ADD COLUMN study_lang TEXT NOT NULL DEFAULT 'en';"
        )
    if not _column_exists(conn, "words", "lang"):
        conn.execute(
            "ALTER TABLE words ADD COLUMN lang TEXT NOT NULL DEFAULT 'en';"
        )
    if not _column_exists(conn, "users", "study_level"):
        conn.execute(
            "ALTER TABLE users ADD COLUMN study_level TEXT NOT NULL DEFAULT 'beginner';"
        )
    if not _column_exists(conn, "words", "difficulty"):
        conn.execute(
            "ALTER TABLE words ADD COLUMN difficulty TEXT NOT NULL DEFAULT 'beginner';"
        )
    if not _column_exists(conn, "users", "study_category"):
        conn.execute(
            "ALTER TABLE users ADD COLUMN study_category TEXT NOT NULL DEFAULT '';"
        )
    if not _column_exists(conn, "users", "quiz_mode"):
        conn.execute(
            "ALTER TABLE users ADD COLUMN quiz_mode TEXT NOT NULL DEFAULT 'to_rus';"
        )
    if not _column_exists(conn, "users", "streak_days"):
        conn.execute(
            "ALTER TABLE users ADD COLUMN streak_days INTEGER NOT NULL DEFAULT 0;"
        )
    if not _column_exists(conn, "users", "last_streak_date"):
        conn.execute("ALTER TABLE users ADD COLUMN last_streak_date TEXT;")
    if not _column_exists(conn, "user_progress", "wrong_answers"):
        conn.execute(
            "ALTER TABLE user_progress ADD COLUMN wrong_answers INTEGER NOT NULL DEFAULT 0;"
        )
    _gamification_migrate_users(conn)


def _gamification_migrate_users(conn: sqlite3.Connection) -> None:
    """Поля геймификации: монеты, комбо, квест дня, титул наставника."""
    cols = (
        ("coins", "INTEGER NOT NULL DEFAULT 0"),
        ("lifetime_coins", "INTEGER NOT NULL DEFAULT 0"),
        ("combo_streak", "INTEGER NOT NULL DEFAULT 0"),
        ("best_combo", "INTEGER NOT NULL DEFAULT 0"),
        ("quiz_prompt_ts", "INTEGER NOT NULL DEFAULT 0"),
        ("powerup_hint", "INTEGER NOT NULL DEFAULT 0"),
        ("powerup_double_xp", "INTEGER NOT NULL DEFAULT 0"),
        ("daily_quest_date", "TEXT"),
        ("daily_quest_id", "TEXT"),
        ("daily_quest_progress", "INTEGER NOT NULL DEFAULT 0"),
        ("daily_quest_done", "INTEGER NOT NULL DEFAULT 0"),
        ("quests_completed_total", "INTEGER NOT NULL DEFAULT 0"),
        ("fast_correct_count", "INTEGER NOT NULL DEFAULT 0"),
        ("mentor_title", "TEXT NOT NULL DEFAULT 'Новичок'"),
    )
    for name, decl in cols:
        if not _column_exists(conn, "users", name):
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {decl};")


def _dedupe_words_by_lang_word_eng(conn: sqlite3.Connection) -> None:
    """Удаляет дубликаты (lang, word_eng), оставляя строку с минимальным id."""
    cur = conn.execute(
        """
        SELECT lang, word_eng, MIN(id) AS keep_id
        FROM words
        GROUP BY lang, word_eng
        HAVING COUNT(*) > 1;
        """
    )
    for row in cur.fetchall():
        lang, word_eng, keep_id = str(row[0]), str(row[1]), int(row[2])
        conn.execute(
            """
            DELETE FROM words
            WHERE lang = ? AND word_eng = ? AND id != ?;
            """,
            (lang, word_eng, keep_id),
        )


def _ensure_words_lang_word_unique_index(conn: sqlite3.Connection) -> None:
    """Уникальность пары (язык, слово) для INSERT OR IGNORE при наполнении словаря."""
    _dedupe_words_by_lang_word_eng(conn)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_words_lang_word_eng "
        "ON words (lang, word_eng);"
    )


def _seed_vocabulary_from_module(conn: sqlite3.Connection) -> None:
    """Добавляет слова из vocabulary_seed (новые строки; дубликаты по паре lang+word_eng игнорируются)."""
    from vocabulary_more import WORDS_ES, WORDS_IT, WORDS_JA, WORDS_PT, WORDS_ZH
    from vocabulary_seed import WORDS_DE, WORDS_EN, WORDS_FR

    try:
        from vocabulary_extra import (
            EXTRA_DE,
            EXTRA_EN,
            EXTRA_ES,
            EXTRA_FR,
            EXTRA_IT,
            EXTRA_JA,
            EXTRA_PT,
            EXTRA_ZH,
        )
    except ImportError:
        EXTRA_EN = EXTRA_DE = EXTRA_FR = EXTRA_ES = EXTRA_IT = EXTRA_PT = EXTRA_ZH = EXTRA_JA = ()

    for lang, rows in (
        ("en", (*WORDS_EN, *EXTRA_EN)),
        ("de", (*WORDS_DE, *EXTRA_DE)),
        ("fr", (*WORDS_FR, *EXTRA_FR)),
        ("zh", (*WORDS_ZH, *EXTRA_ZH)),
        ("es", (*WORDS_ES, *EXTRA_ES)),
        ("it", (*WORDS_IT, *EXTRA_IT)),
        ("pt", (*WORDS_PT, *EXTRA_PT)),
        ("ja", (*WORDS_JA, *EXTRA_JA)),
    ):
        conn.executemany(
            """
            INSERT OR IGNORE INTO words (word_eng, word_rus, category, lang, difficulty)
            VALUES (?, ?, ?, ?, ?);
            """,
            [(a, b, c, lang, d) for a, b, c, d in rows],
        )


def _redistribute_word_difficulty_by_lang(conn: sqlite3.Connection) -> None:
    """
    Для каждого языка выставляет сложность по порядку id: по 4 слова на уровень.
    Вызывается после миграции, если все слова остались с дефолтом beginner.
    """
    for lang in SUPPORTED_LANGS:
        cur = conn.execute(
            "SELECT id FROM words WHERE lang = ? ORDER BY id;",
            (lang,),
        )
        ids = [int(r[0]) for r in cur.fetchall()]
        if len(ids) < 4:
            continue
        cur2 = conn.execute(
            """
            SELECT COUNT(*) AS c FROM words
            WHERE lang = ? AND difficulty != 'beginner';
            """,
            (lang,),
        )
        if int(cur2.fetchone()[0]) > 0:
            continue
        n = len(ids)
        b_end = max(1, n // 3)
        i_end = max(b_end + 1, (2 * n) // 3)
        for idx, wid in enumerate(ids):
            if idx < b_end:
                d = "beginner"
            elif idx < i_end:
                d = "intermediate"
            else:
                d = "advanced"
            conn.execute(
                "UPDATE words SET difficulty = ? WHERE id = ?;",
                (d, wid),
            )


def _connect(db_path: str) -> sqlite3.Connection:
    """Создаёт соединение с параметрами, удобными для приложения."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL + busy_timeout — меньше блокировок при конкурентных записях (Long Poll + callback).
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=15000;")
    return conn


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Контекстный менеджер соединения с БД.
    Автоматически выполняет commit при успешном выходе и rollback при ошибке.
    """
    path = db_path or config.DATABASE_PATH
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Создаёт таблицы при отсутствии и наполняет словарь из модуля vocabulary_seed
    (INSERT OR IGNORE — без дубликатов при повторных запусках).
    """
    with get_connection(db_path) as conn:
        conn.executescript(
            SQL_CREATE_USERS
            + SQL_CREATE_WORDS
            + SQL_CREATE_USER_PROGRESS
            + SQL_CREATE_USER_LEARN_SEEN
            + SQL_CREATE_USER_ACHIEVEMENTS
        )
        _migrate_schema(conn)
        _ensure_words_lang_word_unique_index(conn)
        _seed_vocabulary_from_module(conn)
        _redistribute_word_difficulty_by_lang(conn)


def ensure_user(user_id: int, db_path: Optional[str] = None) -> None:
    """
    Регистрирует пользователя в БД, если его ещё нет (INSERT OR IGNORE).
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (
                user_id, xp, level, state, study_lang, study_level,
                study_category, quiz_mode, streak_days, last_streak_date,
                coins, lifetime_coins, combo_streak, best_combo, quiz_prompt_ts,
                powerup_hint, powerup_double_xp, daily_quest_date, daily_quest_id,
                daily_quest_progress, daily_quest_done, quests_completed_total,
                fast_correct_count, mentor_title
            )
            VALUES (
                ?, 0, 1, 'menu', 'en', 'beginner', '', 'to_rus', 0, NULL,
                0, 0, 0, 0, 0, 0, 0, NULL, NULL, 0, 0, 0, 0, 'Новичок'
            );
            """,
            (user_id,),
        )


def get_user(user_id: int, db_path: Optional[str] = None) -> Optional[sqlite3.Row]:
    """Возвращает строку пользователя или None."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT user_id, xp, level, state, study_lang, study_level,
                   study_category, quiz_mode, streak_days, last_streak_date,
                   coins, lifetime_coins, combo_streak, best_combo, quiz_prompt_ts,
                   powerup_hint, powerup_double_xp, daily_quest_date, daily_quest_id,
                   daily_quest_progress, daily_quest_done, quests_completed_total,
                   fast_correct_count, mentor_title
            FROM users WHERE user_id = ?;
            """,
            (user_id,),
        )
        return cur.fetchone()


def set_user_study_lang(user_id: int, lang: str, db_path: Optional[str] = None) -> None:
    """Сохраняет выбранный язык изучения (код из SUPPORTED_LANGS)."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET study_lang = ? WHERE user_id = ?;",
            (lang, user_id),
        )


def set_user_study_level(user_id: int, level: str, db_path: Optional[str] = None) -> None:
    """Сохраняет уровень владения (beginner / intermediate / advanced)."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET study_level = ? WHERE user_id = ?;",
            (level, user_id),
        )


def set_user_study_category(user_id: int, category: str, db_path: Optional[str] = None) -> None:
    """Тема словаря для квиза и карточек: пустая строка — все категории."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET study_category = ? WHERE user_id = ?;",
            (category, user_id),
        )


def set_user_quiz_mode(user_id: int, mode: str, db_path: Optional[str] = None) -> None:
    """Режим квиза: to_rus (перевод на русский) или to_foreign (с русского на иностранный)."""
    if mode not in QUIZ_MODES:
        return
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET quiz_mode = ? WHERE user_id = ?;",
            (mode, user_id),
        )


def record_streak_activity(user_id: int, db_path: Optional[str] = None) -> int:
    """
    Учитывает активность за календарный день (серия дней подряд с ответом в квизе).
    Возвращает актуальное значение streak_days после обновления.
    """
    from datetime import date, timedelta

    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT streak_days, last_streak_date FROM users WHERE user_id = ?;",
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return 0
        streak = int(row["streak_days"] or 0)
        last = row["last_streak_date"]
        last_s = str(last).strip() if last else ""
        if last_s == today:
            new_streak = streak
        elif last_s == yesterday:
            new_streak = streak + 1
        else:
            new_streak = 1
        conn.execute(
            """
            UPDATE users SET streak_days = ?, last_streak_date = ?
            WHERE user_id = ?;
            """,
            (new_streak, today, user_id),
        )
    return new_streak


def list_categories_for_lang(lang: str, db_path: Optional[str] = None) -> List[str]:
    """Уникальные категории слов для языка (для выбора темы)."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT DISTINCT category FROM words
            WHERE lang = ? AND TRIM(category) != ''
            ORDER BY category COLLATE NOCASE;
            """,
            (lang,),
        )
        return [str(r["category"]) for r in cur.fetchall()]


def count_weak_quiz_words(
    user_id: int,
    lang: str,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Число «слабых» слов: в прогрессе correct_answers < wrong_answers."""
    with get_connection(db_path) as conn:
        extra = ""
        params: List[Any] = [user_id, lang]
        if difficulty:
            extra += " AND w.difficulty = ? "
            params.append(difficulty)
        if category:
            extra += " AND w.category = ? "
            params.append(category)
        cur = conn.execute(
            f"""
            SELECT COUNT(*) AS c FROM words w
            INNER JOIN user_progress p ON p.word_id = w.id AND p.user_id = ?
            WHERE w.lang = ? AND p.correct_answers < p.wrong_answers
            {extra};
            """,
            params,
        )
        return int(cur.fetchone()["c"])


def get_random_weak_word_id(
    user_id: int,
    lang: str,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[int]:
    """Случайное слабое слово для квиза или None."""
    with get_connection(db_path) as conn:
        extra = ""
        params: List[Any] = [user_id, lang]
        if difficulty:
            extra += " AND w.difficulty = ? "
            params.append(difficulty)
        if category:
            extra += " AND w.category = ? "
            params.append(category)
        cur = conn.execute(
            f"""
            SELECT w.id FROM words w
            INNER JOIN user_progress p ON p.word_id = w.id AND p.user_id = ?
            WHERE w.lang = ? AND p.correct_answers < p.wrong_answers
            {extra}
            ORDER BY RANDOM() LIMIT 1;
            """,
            params,
        )
        row = cur.fetchone()
        return int(row["id"]) if row else None


def get_profile_analytics(
    user_id: int,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Сводка для экрана профиля: streak, суммы ответов, точность, топ слов."""
    with get_connection(db_path) as conn:
        u = conn.execute(
            """
            SELECT streak_days, last_streak_date FROM users WHERE user_id = ?;
            """,
            (user_id,),
        ).fetchone()
        if u is None:
            return None
        agg = conn.execute(
            """
            SELECT
                COUNT(*) AS words_with_progress,
                COALESCE(SUM(correct_answers), 0) AS sum_correct,
                COALESCE(SUM(wrong_answers), 0) AS sum_wrong
            FROM user_progress WHERE user_id = ?;
            """,
            (user_id,),
        ).fetchone()
        assert agg is not None
        sum_c = int(agg["sum_correct"] or 0)
        sum_w = int(agg["sum_wrong"] or 0)
        total = sum_c + sum_w
        acc = (100.0 * sum_c / total) if total > 0 else None
        top = conn.execute(
            """
            SELECT w.word_eng, w.word_rus, p.correct_answers, p.wrong_answers
            FROM user_progress p
            JOIN words w ON w.id = p.word_id
            WHERE p.user_id = ?
            ORDER BY p.correct_answers DESC, p.wrong_answers ASC, w.word_eng COLLATE NOCASE
            LIMIT 5;
            """,
            (user_id,),
        ).fetchall()
        top_list = [
            {
                "word_eng": str(r["word_eng"]),
                "word_rus": str(r["word_rus"]),
                "correct": int(r["correct_answers"]),
                "wrong": int(r["wrong_answers"]),
            }
            for r in top
        ]
        return {
            "streak_days": int(u["streak_days"] or 0),
            "last_streak_date": u["last_streak_date"],
            "words_with_progress": int(agg["words_with_progress"] or 0),
            "sum_correct": sum_c,
            "sum_wrong": sum_w,
            "accuracy_pct": acc,
            "top_words": top_list,
        }


def set_quiz_prompt_ts(user_id: int, ts: int, db_path: Optional[str] = None) -> None:
    """Время отправки вопроса квиза (Unix) — для бонуса за быстрый ответ."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET quiz_prompt_ts = ? WHERE user_id = ?;",
            (int(ts), user_id),
        )


def clear_quiz_prompt_ts(user_id: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET quiz_prompt_ts = 0 WHERE user_id = ?;",
            (user_id,),
        )


def grant_coins(user_id: int, amount: int, db_path: Optional[str] = None) -> int:
    """Начисляет монеты и lifetime_coins; возвращает новый баланс coins."""
    if amount <= 0:
        row = get_user(user_id, db_path=db_path)
        return int(row["coins"]) if row else 0
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users SET coins = coins + ?, lifetime_coins = lifetime_coins + ?
            WHERE user_id = ?;
            """,
            (amount, amount, user_id),
        )
        cur = conn.execute("SELECT coins FROM users WHERE user_id = ?;", (user_id,))
        r = cur.fetchone()
        return int(r["coins"]) if r else 0


def try_spend_coins(user_id: int, amount: int, db_path: Optional[str] = None) -> bool:
    """Списывает монеты, если хватает. Возвращает True при успехе."""
    if amount <= 0:
        return True
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT coins FROM users WHERE user_id = ?;", (user_id,))
        row = cur.fetchone()
        if row is None or int(row["coins"] or 0) < amount:
            return False
        conn.execute(
            "UPDATE users SET coins = coins - ? WHERE user_id = ?;",
            (amount, user_id),
        )
    return True


def set_powerup_hint(user_id: int, value: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET powerup_hint = ? WHERE user_id = ?;",
            (1 if value else 0, user_id),
        )


def set_powerup_double_xp(user_id: int, value: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET powerup_double_xp = ? WHERE user_id = ?;",
            (1 if value else 0, user_id),
        )


def consume_powerup_hint(user_id: int, db_path: Optional[str] = None) -> bool:
    """Сбрасывает флаг подсказки, если был установлен; возвращает True, если была активна."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT powerup_hint FROM users WHERE user_id = ?;",
            (user_id,),
        )
        row = cur.fetchone()
        if not row or not int(row["powerup_hint"] or 0):
            return False
        conn.execute(
            "UPDATE users SET powerup_hint = 0 WHERE user_id = ?;",
            (user_id,),
        )
    return True


def take_powerup_double_xp(user_id: int, db_path: Optional[str] = None) -> bool:
    """Если активен x2 XP — снимает флаг и возвращает True."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT powerup_double_xp FROM users WHERE user_id = ?;",
            (user_id,),
        )
        row = cur.fetchone()
        if not row or not int(row["powerup_double_xp"] or 0):
            return False
        conn.execute(
            "UPDATE users SET powerup_double_xp = 0 WHERE user_id = ?;",
            (user_id,),
        )
    return True


def increment_combo_on_correct(user_id: int, db_path: Optional[str] = None) -> Tuple[int, int]:
    """
    Увеличивает combo_streak, обновляет best_combo при рекорде.
    Возвращает (combo_streak, best_combo).
    """
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET combo_streak = combo_streak + 1 WHERE user_id = ?;",
            (user_id,),
        )
        cur = conn.execute(
            "SELECT combo_streak, best_combo FROM users WHERE user_id = ?;",
            (user_id,),
        )
        row = cur.fetchone()
        assert row is not None
        cs = int(row["combo_streak"] or 0)
        best = int(row["best_combo"] or 0)
        if cs > best:
            conn.execute(
                "UPDATE users SET best_combo = ? WHERE user_id = ?;",
                (cs, user_id),
            )
            best = cs
    return cs, best


def reset_combo_streak(user_id: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET combo_streak = 0 WHERE user_id = ?;",
            (user_id,),
        )


def increment_fast_correct(user_id: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET fast_correct_count = fast_correct_count + 1 WHERE user_id = ?;",
            (user_id,),
        )


def set_daily_quest(
    user_id: int,
    quest_date: str,
    quest_id: str,
    progress: int = 0,
    done: int = 0,
    db_path: Optional[str] = None,
) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users SET
                daily_quest_date = ?,
                daily_quest_id = ?,
                daily_quest_progress = ?,
                daily_quest_done = ?
            WHERE user_id = ?;
            """,
            (quest_date, quest_id, progress, done, user_id),
        )


def bump_daily_quest_progress(user_id: int, delta: int, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users SET daily_quest_progress = daily_quest_progress + ?
            WHERE user_id = ? AND daily_quest_done = 0;
            """,
            (delta, user_id),
        )


def set_daily_quest_progress(
    user_id: int, progress: int, db_path: Optional[str] = None
) -> None:
    """Устанавливает прогресс квеста (для комбо и сброса при ошибке)."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users SET daily_quest_progress = ?
            WHERE user_id = ? AND daily_quest_done = 0;
            """,
            (max(0, progress), user_id),
        )


def complete_daily_quest_reward(
    user_id: int,
    coin_bonus: int,
    xp_bonus: int,
    db_path: Optional[str] = None,
) -> None:
    """Помечает квест выполненным, копит счётчик завершённых квестов, начисляет монеты."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users SET
                daily_quest_done = 1,
                quests_completed_total = quests_completed_total + 1,
                coins = coins + ?,
                lifetime_coins = lifetime_coins + ?
            WHERE user_id = ?;
            """,
            (coin_bonus, coin_bonus, user_id),
        )


def set_mentor_title(user_id: int, title: str, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET mentor_title = ? WHERE user_id = ?;",
            (title[:80], user_id),
        )


def try_insert_achievement(
    user_id: int,
    code: str,
    db_path: Optional[str] = None,
) -> bool:
    """Добавляет достижение; True если строка новая."""
    from datetime import datetime

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    c = code[:64]
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT 1 FROM user_achievements WHERE user_id = ? AND code = ?;",
            (user_id, c),
        )
        if cur.fetchone():
            return False
        conn.execute(
            "INSERT INTO user_achievements (user_id, code, unlocked_at) VALUES (?, ?, ?);",
            (user_id, c, now),
        )
    return True


def list_achievement_codes(user_id: int, db_path: Optional[str] = None) -> List[str]:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT code FROM user_achievements WHERE user_id = ? ORDER BY unlocked_at;",
            (user_id,),
        )
        return [str(r["code"]) for r in cur.fetchall()]


def count_achievements(user_id: int, db_path: Optional[str] = None) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "SELECT COUNT(*) AS c FROM user_achievements WHERE user_id = ?;",
            (user_id,),
        )
        return int(cur.fetchone()["c"])


def set_user_state(user_id: int, state: str, db_path: Optional[str] = None) -> None:
    """Обновляет поле state (контекст диалога в меню / квизе и т.д.)."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET state = ? WHERE user_id = ?;",
            (state, user_id),
        )


def update_user_xp_level(
    user_id: int,
    xp: int,
    level: int,
    db_path: Optional[str] = None,
) -> None:
    """Обновляет опыт и уровень пользователя после расчёта в game_logic."""
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE users SET xp = ?, level = ? WHERE user_id = ?;",
            (xp, level, user_id),
        )


def count_words(
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """
    Возвращает количество слов в словаре.
    Можно отфильтровать по языку, уровню сложности и категории (пустая — без фильтра).
    """
    cat_sql = " AND category = ? " if category else ""
    cat_params: List[Any] = [category] if category else []
    with get_connection(db_path) as conn:
        if lang is None and difficulty is None and not category:
            cur = conn.execute("SELECT COUNT(*) AS c FROM words;")
        elif lang is not None and difficulty is not None:
            cur = conn.execute(
                f"SELECT COUNT(*) AS c FROM words WHERE lang = ? AND difficulty = ? {cat_sql};",
                ([lang, difficulty] + cat_params),
            )
        elif lang is not None:
            cur = conn.execute(
                f"SELECT COUNT(*) AS c FROM words WHERE lang = ? {cat_sql};",
                [lang] + cat_params,
            )
        elif difficulty is not None:
            cur = conn.execute(
                f"SELECT COUNT(*) AS c FROM words WHERE difficulty = ? {cat_sql};",
                [difficulty] + cat_params,
            )
        else:
            cur = conn.execute(
                f"SELECT COUNT(*) AS c FROM words WHERE 1=1 {cat_sql};",
                cat_params,
            )
        return int(cur.fetchone()["c"])


def get_word_by_id(word_id: int, db_path: Optional[str] = None) -> Optional[sqlite3.Row]:
    """Возвращает слово по первичному ключу."""
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            SELECT id, word_eng, word_rus, category, lang, difficulty
            FROM words WHERE id = ?;
            """,
            (word_id,),
        )
        return cur.fetchone()


def get_random_word_id(
    exclude_ids: Optional[List[int]] = None,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[int]:
    """
    Случайный id из таблицы words (опционально исключая заданные id).
    Используется для выбора вопроса в квизе и для режима «Учить слова».
    """
    exclude_ids = exclude_ids or []
    with get_connection(db_path) as conn:
        extra = ""
        params: List[Any] = []
        if lang:
            extra += " AND lang = ? "
            params.append(lang)
        if difficulty:
            extra += " AND difficulty = ? "
            params.append(difficulty)
        if category:
            extra += " AND category = ? "
            params.append(category)
        if not exclude_ids:
            cur = conn.execute(
                f"SELECT id FROM words WHERE 1=1 {extra} ORDER BY RANDOM() LIMIT 1;",
                params,
            )
        else:
            placeholders = ",".join("?" * len(exclude_ids))
            cur = conn.execute(
                f"""
                SELECT id FROM words
                WHERE id NOT IN ({placeholders}) {extra}
                ORDER BY RANDOM() LIMIT 1;
                """,
                exclude_ids + params,
            )
        row = cur.fetchone()
        return int(row["id"]) if row else None


def get_distractor_rus_words(
    correct_word_id: int,
    count: int,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[str]:
    """
    Возвращает до `count` русских переводов других слов (дистракторы).
    Если уникальных слов в БД мало, возвращается меньше значений — вызывающий
    код должен обработать (в квизе нужно минимум 4 варианта).
    """
    cat_sql = " AND category = ? " if category else ""
    cat_par: List[Any] = [category] if category else []
    with get_connection(db_path) as conn:
        if lang is None and difficulty is None:
            cur = conn.execute(
                f"""
                SELECT word_rus FROM words
                WHERE id != ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id] + cat_par + [count]),
            )
        elif lang is not None and difficulty is not None:
            cur = conn.execute(
                f"""
                SELECT word_rus FROM words
                WHERE id != ? AND lang = ? AND difficulty = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, lang, difficulty] + cat_par + [count]),
            )
        elif lang is not None:
            cur = conn.execute(
                f"""
                SELECT word_rus FROM words
                WHERE id != ? AND lang = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, lang] + cat_par + [count]),
            )
        else:
            cur = conn.execute(
                f"""
                SELECT word_rus FROM words
                WHERE id != ? AND difficulty = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, difficulty] + cat_par + [count]),
            )
        return [str(r["word_rus"]) for r in cur.fetchall()]


def get_distractor_eng_words(
    correct_word_id: int,
    count: int,
    lang: Optional[str] = None,
    difficulty: Optional[str] = None,
    category: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[str]:
    """Иностранные слова-дистракторы (для режима «с русского на язык»)."""
    cat_sql = " AND category = ? " if category else ""
    cat_par: List[Any] = [category] if category else []
    with get_connection(db_path) as conn:
        if lang is None and difficulty is None:
            cur = conn.execute(
                f"""
                SELECT word_eng FROM words
                WHERE id != ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id] + cat_par + [count]),
            )
        elif lang is not None and difficulty is not None:
            cur = conn.execute(
                f"""
                SELECT word_eng FROM words
                WHERE id != ? AND lang = ? AND difficulty = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, lang, difficulty] + cat_par + [count]),
            )
        elif lang is not None:
            cur = conn.execute(
                f"""
                SELECT word_eng FROM words
                WHERE id != ? AND lang = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, lang] + cat_par + [count]),
            )
        else:
            cur = conn.execute(
                f"""
                SELECT word_eng FROM words
                WHERE id != ? AND difficulty = ? {cat_sql}
                ORDER BY RANDOM()
                LIMIT ?;
                """,
                ([correct_word_id, difficulty] + cat_par + [count]),
            )
        return [str(r["word_eng"]) for r in cur.fetchall()]


def next_learn_card_word_id(
    user_id: int,
    lang: str,
    study_level: str,
    study_category: str = "",
    db_path: Optional[str] = None,
) -> Optional[int]:
    """
    Выбирает следующее слово для карточки «Учить слова» без повторов в пределах «колоды».

    Область колоды: сначала слова с выбранным языком и уровнем сложности; если таких нет —
    все слова выбранного языка. Непустая study_category ограничивает колоду этой темой.
    Пока не показаны все слова области, уже показанные не
    предлагаются снова. Когда непоказанных не осталось, отметки для этой области сбрасываются,
    и круг начинается заново.

    Используется одна транзакция BEGIN IMMEDIATE: выбор слова и запись в user_learn_seen
    выполняются атомарно, чтобы при двух быстрых запросах не выбралось одно и то же слово.
    """
    path = db_path or config.DATABASE_PATH
    conn = _connect(path)
    cat = study_category.strip()
    cat_sql = " AND category = ? " if cat else ""

    def word_filter_params(lang_code: str, level: Optional[str] = None) -> Tuple[Any, ...]:
        """Порядок плейсхолдеров: lang [, difficulty] [, category]."""
        if level is not None:
            return (lang_code, level, cat) if cat else (lang_code, level)
        return (lang_code, cat) if cat else (lang_code,)

    def pick_params(lang_code: str, level: Optional[str] = None) -> Tuple[Any, ...]:
        """Порядок: lang [, difficulty] [, category], user_id."""
        if level is not None:
            return (lang_code, level, cat, user_id) if cat else (lang_code, level, user_id)
        return (lang_code, cat, user_id) if cat else (lang_code, user_id)

    def reset_params(lang_code: str, level: Optional[str] = None) -> Tuple[Any, ...]:
        """Порядок: user_id, lang [, difficulty] [, category]."""
        if level is not None:
            return (user_id, lang_code, level, cat) if cat else (user_id, lang_code, level)
        return (user_id, lang_code, cat) if cat else (user_id, lang_code)

    try:
        conn.execute("BEGIN IMMEDIATE")

        def count_scope(use_level: bool) -> int:
            if use_level:
                cur = conn.execute(
                    f"SELECT COUNT(*) AS c FROM words WHERE lang = ? AND difficulty = ? {cat_sql};",
                    word_filter_params(lang, study_level),
                )
            else:
                cur = conn.execute(
                    f"SELECT COUNT(*) AS c FROM words WHERE lang = ? {cat_sql};",
                    word_filter_params(lang),
                )
            return int(cur.fetchone()["c"])

        def pick_unseen(use_level: bool) -> Optional[int]:
            if use_level:
                cur = conn.execute(
                    f"""
                    SELECT w.id FROM words w
                    WHERE w.lang = ? AND w.difficulty = ? {cat_sql}
                    AND NOT EXISTS (
                        SELECT 1 FROM user_learn_seen s
                        WHERE s.user_id = ? AND s.word_id = w.id
                    )
                    ORDER BY RANDOM() LIMIT 1;
                    """,
                    pick_params(lang, study_level),
                )
            else:
                cur = conn.execute(
                    f"""
                    SELECT w.id FROM words w
                    WHERE w.lang = ? {cat_sql}
                    AND NOT EXISTS (
                        SELECT 1 FROM user_learn_seen s
                        WHERE s.user_id = ? AND s.word_id = w.id
                    )
                    ORDER BY RANDOM() LIMIT 1;
                    """,
                    pick_params(lang),
                )
            row = cur.fetchone()
            return int(row[0]) if row else None

        def reset_seen_for_scope(use_level: bool) -> None:
            if use_level:
                conn.execute(
                    f"""
                    DELETE FROM user_learn_seen
                    WHERE user_id = ?
                    AND word_id IN (
                        SELECT id FROM words WHERE lang = ? AND difficulty = ? {cat_sql}
                    );
                    """,
                    reset_params(lang, study_level),
                )
            else:
                conn.execute(
                    f"""
                    DELETE FROM user_learn_seen
                    WHERE user_id = ?
                    AND word_id IN (SELECT id FROM words WHERE lang = ? {cat_sql});
                    """,
                    reset_params(lang),
                )

        def take_from_scope(use_level: bool) -> Optional[int]:
            if use_level:
                if count_scope(True) == 0:
                    return None
            else:
                if count_scope(False) == 0:
                    return None
            wid = pick_unseen(use_level)
            if wid is not None:
                return wid
            reset_seen_for_scope(use_level)
            return pick_unseen(use_level)

        use_level_first = count_scope(True) >= 1
        word_id: Optional[int] = None
        if use_level_first:
            word_id = take_from_scope(True)
        if word_id is None:
            word_id = take_from_scope(False)

        if word_id is not None:
            conn.execute(
                """
                INSERT OR IGNORE INTO user_learn_seen (user_id, word_id)
                VALUES (?, ?);
                """,
                (user_id, word_id),
            )
        conn.commit()
        return word_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def increment_user_progress(
    user_id: int,
    word_id: int,
    db_path: Optional[str] = None,
) -> None:
    """
    Увеличивает счётчик верных ответов по паре (user_id, word_id).
    INSERT при первом появлении, UPDATE при последующих.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_progress (user_id, word_id, correct_answers, wrong_answers)
            VALUES (?, ?, 1, 0)
            ON CONFLICT(user_id, word_id) DO UPDATE SET
                correct_answers = correct_answers + 1;
            """,
            (user_id, word_id),
        )


def increment_user_wrong(
    user_id: int,
    word_id: int,
    db_path: Optional[str] = None,
) -> None:
    """Увеличивает счётчик неверных ответов по слову в квизе."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_progress (user_id, word_id, correct_answers, wrong_answers)
            VALUES (?, ?, 0, 1)
            ON CONFLICT(user_id, word_id) DO UPDATE SET
                wrong_answers = wrong_answers + 1;
            """,
            (user_id, word_id),
        )


def fetch_all_word_ids(db_path: Optional[str] = None) -> List[int]:
    """Список всех id слов (для отладки или статистики)."""
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT id FROM words ORDER BY id;")
        return [int(r["id"]) for r in cur.fetchall()]
