# -*- coding: utf-8 -*-
"""Заполняет ROMANCE_CJK_BY_RU для всех EN-слов без перевода в ES/ZH/JA."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE))

from deep_translator import GoogleTranslator  # noqa: E402
from vocabulary_more import WORDS_ES, WORDS_IT, WORDS_JA, WORDS_PT, WORDS_ZH  # noqa: E402
from vocabulary_seed import WORDS_EN, WORDS_FR  # noqa: E402

OUT = _CODE / "vocabulary_extra_data.py"

existing_ru = {b.strip().lower() for _, b, _, _ in WORDS_ES}
existing_ru |= {b.strip().lower() for _, b, _, _ in WORDS_ZH}

fr_by_ru = {b.strip().lower(): a for a, b, c, d in WORDS_FR}

need: list[tuple[str, str, str, str]] = []
for en, ru, cat, diff in WORDS_EN:
    ruk = ru.strip().lower()
    if ruk in existing_ru:
        continue
    need.append((en, ru, cat, diff))

print(f"Translating {len(need)} words...")

translators = {
    "es": GoogleTranslator(source="en", target="es"),
    "it": GoogleTranslator(source="en", target="it"),
    "pt": GoogleTranslator(source="en", target="pt"),
    "zh": GoogleTranslator(source="en", target="zh-CN"),
    "ja": GoogleTranslator(source="en", target="ja"),
}

entries: dict[str, tuple[str, str, str, str, str]] = {}

for i, (en, ru, cat, diff) in enumerate(need):
    ruk = ru.strip().lower()
    try:
        es = translators["es"].translate(en)
        time.sleep(0.15)
        it = translators["it"].translate(en)
        time.sleep(0.15)
        pt = translators["pt"].translate(en)
        time.sleep(0.15)
        zh = translators["zh"].translate(en)
        time.sleep(0.15)
        ja = translators["ja"].translate(en)
        time.sleep(0.15)
    except Exception as exc:
        print(f"  skip {en!r}: {exc}")
        fr = fr_by_ru.get(ruk, en)
        es = it = pt = fr
        zh = ja = ""
    entries[ruk] = (es, it, pt, zh, ja)
    if (i + 1) % 20 == 0:
        print(f"  {i + 1}/{len(need)}")

lines = [
    "# -*- coding: utf-8 -*-",
    '"""RU -> (es, it, pt, zh, ja) для выравнивания словарей (auto + seed)."""',
    "from __future__ import annotations",
    "from typing import Dict, Tuple",
    "RomanceCjk = Tuple[str, str, str, str, str]",
    "ROMANCE_CJK_BY_RU: Dict[str, RomanceCjk] = {",
]
for ru in sorted(entries):
    lines.append(f"    {ru!r}: {entries[ru]!r},")
lines.append("}")
OUT.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", OUT, "entries", len(entries))
