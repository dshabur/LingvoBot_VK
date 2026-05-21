# -*- coding: utf-8 -*-
"""
Синтетическое нагрузочное тестирование без реального VK API.

Сценарии 2.1 / 2.2: имитация MESSAGE_NEW («Статистика») и конкурентных MESSAGE_EVENT
(callback квиз) с моком VkApi; отдельный временный файл SQLite (не bot_data.sqlite3).

Запуск из каталога code:
  python load_test.py
  python load_test.py --duration 10 --rate 50
  python load_test.py --scenario 2.2 --users 30 --rounds 25
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional, Tuple

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

os.chdir(_CODE_DIR)


def _rss_bytes() -> Optional[int]:
    try:
        import psutil  # type: ignore

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return None


def _make_vk_mock() -> Any:
    class _Msgs:
        def send(self, **kwargs: Any) -> None:
            return None

        def sendMessageEventAnswer(self, **kwargs: Any) -> None:
            return None

        def edit(self, **kwargs: Any) -> None:
            return None

    return SimpleNamespace(messages=_Msgs())


def _message_new_event(user_id: int, seq: int, text: str = "статистика") -> Any:
    ts = int(time.time())
    msg = SimpleNamespace(
        text=text,
        peer_id=user_id,
        from_id=user_id,
        date=ts,
        conversation_message_id=seq,
        id=seq,
    )
    return SimpleNamespace(message=msg)


def _quiz_correct_event(
    user_id: int,
    word_id: int,
    event_id: str,
    conv_msg_id: int,
) -> Any:
    payload = json.dumps(
        {"action": "quiz", "word_id": word_id, "is_correct": True},
        ensure_ascii=False,
    )
    obj = SimpleNamespace(
        user_id=user_id,
        peer_id=user_id,
        event_id=event_id,
        conversation_message_id=conv_msg_id,
        payload=payload,
    )
    return SimpleNamespace(object=obj)


async def scenario_2_1(
    router: Any,
    *,
    rate_per_sec: int,
    duration_sec: float,
    user_offset: int,
) -> Tuple[int, int, float, float, List[float]]:
    """Поток «Статистика» ~rate_per_sec сообщений/с с разными user_id."""
    latencies: List[float] = []
    errors = 0
    processed = 0
    t0 = time.perf_counter()
    seq = 0
    end = t0 + duration_sec

    while time.perf_counter() < end:
        batch_start = time.perf_counter()
        tasks: List[asyncio.Task[Any]] = []

        def one(uid: int, s: int) -> None:
            nonlocal errors, processed
            t1 = time.perf_counter()
            try:
                router.handle_message_new(_message_new_event(uid, s))
            except Exception:
                errors += 1
            finally:
                latencies.append(time.perf_counter() - t1)
                processed += 1

        for i in range(rate_per_sec):
            uid = user_offset + seq + i
            s = seq + i
            tasks.append(asyncio.to_thread(one, uid, s))
        seq += rate_per_sec
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - batch_start
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)

    wall = time.perf_counter() - t0
    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if len(lat_sorted) > 1 else 0.0
    return processed, errors, wall, p95, latencies


async def scenario_2_2(
    router: Any,
    *,
    num_users: int,
    rounds: int,
    word_id: int,
) -> Tuple[int, int]:
    """Конкурентные верные ответы квиза от num_users разных user_id."""
    errors = 0
    processed = 0

    for rnd in range(rounds):

        def one_event(uid: int, r: int, idx: int) -> None:
            nonlocal errors, processed
            try:
                ev = _quiz_correct_event(
                    uid,
                    word_id,
                    event_id=f"e{uid}_{r}_{idx}",
                    conv_msg_id=500_000 + (uid % 99_000) * 1_000 + r * 100 + idx,
                )
                router.handle_message_event(ev)
            except Exception:
                errors += 1
            finally:
                processed += 1

        tasks = [
            asyncio.to_thread(one_event, 300_000 + u, rnd, u) for u in range(num_users)
        ]
        await asyncio.gather(*tasks)

    return processed, errors


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Нагрузочное тестирование бота (синтетика)")
    parser.add_argument("--duration", type=float, default=10.0, help="Длительность 2.1, сек")
    parser.add_argument("--rate", type=int, default=50, help="Сообщений «Статистика» в секунду (2.1)")
    parser.add_argument("--scenario", choices=("all", "2.1", "2.2"), default="all")
    parser.add_argument("--users", type=int, default=30, help="Пользователей в 2.2")
    parser.add_argument("--rounds", type=int, default=25, help="Раундов 2.2")
    args = parser.parse_args()

    import config

    fd, db_path = tempfile.mkstemp(prefix="vkbot_load_", suffix=".sqlite3")
    os.close(fd)
    Path(db_path).unlink(missing_ok=True)
    config.DATABASE_PATH = db_path

    import db_handler
    from main import Router

    db_handler.init_db(db_path)

    rows = db_handler.fetch_all_word_ids(db_path)
    if not rows:
        print("БД без слов — тест невозможен")
        return 2
    word_id = rows[0]

    vk = _make_vk_mock()
    router = Router(vk)

    mem_before = _rss_bytes()

    print("=== Нагрузочное тестирование (синтетика, мок VK) ===")
    print(f"БД: {db_path}")
    with db_handler.get_connection(db_path) as conn:
        jm = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        print(f"PRAGMA journal_mode = {jm}")

    r21: Optional[Tuple[int, int, float, float, List[float]]] = None
    r22: Optional[Tuple[int, int]] = None

    if args.scenario in ("all", "2.1"):
        print(f"\n--- 2.1 Стресс MESSAGE_NEW ~{args.rate}/с, {args.duration} с ---")
        m0 = _rss_bytes()
        r21 = asyncio.run(
            scenario_2_1(
                router,
                rate_per_sec=args.rate,
                duration_sec=args.duration,
                user_offset=400_000,
            )
        )
        proc, errs, wall, p95, lats = r21
        m1 = _rss_bytes()
        p50 = sorted(lats)[len(lats) // 2] if lats else 0.0
        print(f"Обработано событий: {proc}, ошибок: {errs}, wall time: {wall:.2f} с")
        print(f"Latency p50: {p50*1000:.1f} ms, p95: {p95*1000:.1f} ms")
        if m0 is not None and m1 is not None:
            print(f"RSS: до ~{m0 // 1024} KiB, после пачки ~{m1 // 1024} KiB (Δ {(m1 - m0) // 1024} KiB)")

    if args.scenario in ("all", "2.2"):
        print(f"\n--- 2.2 Конкурентные callback quiz, {args.users} пользователей x {args.rounds} раундов ---")
        r22 = asyncio.run(
            scenario_2_2(router, num_users=args.users, rounds=args.rounds, word_id=word_id)
        )
        proc2, err2 = r22
        print(f"Обработано: {proc2}, ошибок: {err2}")

    mem_after = _rss_bytes()
    if mem_before is not None and mem_after is not None:
        print(f"\nRSS в конце: ~{mem_after // 1024} KiB (старт сценариев ~{mem_before // 1024} KiB)")

    print("\n--- Сводка для таблицы 2 (скопируйте в пояснительную записку) ---")
    if r21:
        proc, errs, wall, p95, lats = r21
        p50 = sorted(lats)[len(lats) // 2] if lats else 0.0
        crash = "нет" if errs == 0 else f"ошибок {errs}"
        lat_ok = "да" if p95 <= 3.0 else "нет"
        print(
            f"2.1 | Исключения: {crash} | p50={p50*1000:.0f} мс, p95={p95*1000:.0f} мс | "
            f"задержка <= 3 с: {lat_ok} | событий: {proc}"
        )
    if r22:
        proc2, err2 = r22
        lock_ok = (
            "OperationalError (database is locked) не возникал"
            if err2 == 0
            else f"ошибок при обработке: {err2}"
        )
        print(f"2.2 | {lock_ok} | callback-ов: {proc2}")

    try:
        Path(db_path).unlink(missing_ok=True)
    except OSError:
        pass

    if r21 and r21[1] > 0:
        return 1
    if r22 and r22[1] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
