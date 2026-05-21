# -*- coding: utf-8 -*-
"""Строит ROMANCE_CJK_BY_RU в vocabulary_extra_data.py из EN + индексов языков."""

from __future__ import annotations

import sys
from pathlib import Path

_CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE))

from vocabulary_seed import WORDS_EN, WORDS_FR  # noqa: E402
from vocabulary_more import WORDS_ES, WORDS_IT, WORDS_JA, WORDS_PT, WORDS_ZH  # noqa: E402

# ru_lower -> (es, it, pt, zh, ja)
MAP: dict[str, tuple[str, str, str, str, str]] = {}


def add(ru: str, es: str, it: str, pt: str, zh: str, ja: str) -> None:
    MAP[ru.strip().lower()] = (es, it, pt, zh, ja)


def idx(rows):
    return {(b.strip().lower(), c): a for a, b, c, d in rows}


es_i, it_i, pt_i, zh_i, ja_i = idx(WORDS_ES), idx(WORDS_IT), idx(WORDS_PT), idx(WORDS_ZH), idx(WORDS_JA)
fr_i = idx(WORDS_FR)

# Заполнить из существующих словарей
for a, b, c, d in WORDS_ES:
    key = b.strip().lower()
    if key not in MAP:
        MAP[key] = (a, it_i.get((b.strip().lower(), c), a), pt_i.get((b.strip().lower(), c), a), zh_i.get((b.strip().lower(), c), ""), ja_i.get((b.strip().lower(), c), ""))
for a, b, c, d in WORDS_IT:
    key = b.strip().lower()
    if key in MAP:
        es, _, pt, zh, ja = MAP[key]
        MAP[key] = (es or a, a, pt or a, zh, ja)
    else:
        MAP[key] = (es_i.get((key, c), a), a, pt_i.get((key, c), a), "", "")
for a, b, c, d in WORDS_PT:
    key = b.strip().lower()
    if key in MAP:
        t = MAP[key]
        MAP[key] = (t[0], t[1], a, t[3], t[4])
    else:
        MAP[key] = ("", "", a, "", "")

# Для оставшихся EN — взять FR как подсказку для ES (латинские языки), ZH/JA из FR нет — пропуск
# Добавим крупный блок вручную через импорт из generate_vocabulary_extra ROMANCE_ZH_JA

from tools.generate_vocabulary_extra import ROMANCE_ZH_JA, _NEW  # type: ignore

for en, ru, cat, diff, *_ in _NEW:
    if en == "work_verb":
        en = "work"
    add(ru, *ROMANCE_ZH_JA[en.casefold()])

# EN seed: если есть только FR, используем FR для ES/IT/PT (частичное совпадение лексики)
for en, ru, cat, diff in WORDS_EN:
    ruk = ru.strip().lower()
    if ruk in MAP:
        continue
    fr = fr_i.get((ruk, cat))
    if fr:
        # грубая латинская подстановка: часто ES/IT/PT близки к FR для базовой лексики
        add(ruk, fr, fr, fr, "", "")

missing = [ru for en, ru, cat, diff in WORDS_EN if ru.strip().lower() not in MAP or not MAP[ru.strip().lower()][3]]
print("MAP size", len(MAP), "missing zh/ja", len(missing))

out = _CODE / "vocabulary_extra_data.py"
lines = [
    "# -*- coding: utf-8 -*-",
    '"""Сопоставление русского перевода с формами ES/IT/PT/ZH/JA (генерируется)."""',
    "from __future__ import annotations",
    "from typing import Dict, Tuple",
    "RomanceCjk = Tuple[str, str, str, str, str]",
    "ROMANCE_CJK_BY_RU: Dict[str, RomanceCjk] = {",
]
for ru, t in sorted(MAP.items()):
    lines.append(f"    {ru!r}: {t!r},")
lines.append("}")
out.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", out)
