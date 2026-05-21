# -*- coding: utf-8 -*-
"""Строит ROMANCE_CJK_BY_RU: ES/IT/PT из FR, ZH/JA — из существующих словарей и _NEW."""

from __future__ import annotations

import sys
from pathlib import Path

_CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE))

from vocabulary_seed import WORDS_DE, WORDS_EN, WORDS_FR  # noqa: E402
from vocabulary_more import WORDS_ES, WORDS_IT, WORDS_JA, WORDS_PT, WORDS_ZH  # noqa: E402

sys.path.insert(0, str(_CODE / "tools"))
from generate_vocabulary_extra import ROMANCE_ZH_JA, _NEW  # noqa: E402

WordKey = tuple[str, str]


def idx(rows):
    return {(b.strip().lower(), c): a for a, b, c, d in rows}


es_i, it_i, pt_i, zh_i, ja_i = idx(WORDS_ES), idx(WORDS_IT), idx(WORDS_PT), idx(WORDS_ZH), idx(WORDS_JA)
fr_i, de_i = idx(WORDS_FR), idx(WORDS_DE)
en_by_ru = {b.strip().lower(): a for a, b, c, d in WORDS_EN}

MAP: dict[str, tuple[str, str, str, str, str]] = {}

for en, ru, cat, diff, de, fr, es, it, pt, zh, ja in _NEW:
    MAP[ru.strip().lower()] = (es, it, pt, zh, ja)

for en, ru, cat, diff in WORDS_EN:
    ruk = ru.strip().lower()
    key: WordKey = (ruk, cat)
    if ruk in MAP:
        continue
    if key in es_i:
        es = es_i[key]
        it = it_i.get(key, es)
        pt = pt_i.get(key, es)
        zh = zh_i.get(key, "")
        ja = ja_i.get(key, "")
        MAP[ruk] = (es, it, pt, zh or "", ja or "")
        continue
    if en.casefold() in ROMANCE_ZH_JA:
        MAP[ruk] = ROMANCE_ZH_JA[en.casefold()]
        continue
    fr = fr_i.get(key) or de_i.get(key)
    if fr:
        zh = zh_i.get(key, "")
        ja = ja_i.get(key, "")
        MAP[ruk] = (fr, fr, fr, zh or "", ja or "")

out = _CODE / "vocabulary_extra_data.py"
lines = [
    "# -*- coding: utf-8 -*-",
    '"""RU -> (es, it, pt, zh, ja) для выравнивания словарей."""',
    "from __future__ import annotations",
    "from typing import Dict, Tuple",
    "RomanceCjk = Tuple[str, str, str, str, str]",
    "ROMANCE_CJK_BY_RU: Dict[str, RomanceCjk] = {",
]
for ru in sorted(MAP):
    lines.append(f"    {ru!r}: {MAP[ru]!r},")
lines.append("}")
out.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", out, "entries", len(MAP))
