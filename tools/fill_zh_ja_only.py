# -*- coding: utf-8 -*-
"""Дополняет пустые zh/ja в vocabulary_extra_data.py (перевод с английского)."""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

_CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE))

from deep_translator import GoogleTranslator  # noqa: E402
from vocabulary_extra_data import ROMANCE_CJK_BY_RU  # noqa: E402
from vocabulary_seed import WORDS_EN  # noqa: E402

en_by_ru = {b.strip().lower(): a for a, b, c, d in WORDS_EN}
zh_t = GoogleTranslator(source="en", target="zh-CN")
ja_t = GoogleTranslator(source="en", target="ja")

updated = dict(ROMANCE_CJK_BY_RU)
todo = [ruk for ruk, t in updated.items() if not t[3] or not t[4]]
print(f"Fill zh/ja for {len(todo)} entries")

for i, ruk in enumerate(todo):
    en = en_by_ru.get(ruk)
    if not en:
        continue
    es, it, pt, zh, ja = updated[ruk]
    try:
        if not zh:
            zh = zh_t.translate(en)
            time.sleep(0.2)
        if not ja:
            ja = ja_t.translate(en)
            time.sleep(0.2)
    except Exception as exc:
        print(f"fail {ruk}: {exc}")
        continue
    updated[ruk] = (es, it, pt, zh, ja)
    if (i + 1) % 25 == 0:
        print(f"  {i + 1}/{len(todo)}", flush=True)

out = _CODE / "vocabulary_extra_data.py"
lines = [
    "# -*- coding: utf-8 -*-",
    '"""RU -> (es, it, pt, zh, ja) для выравнивания словарей."""',
    "from __future__ import annotations",
    "from typing import Dict, Tuple",
    "RomanceCjk = Tuple[str, str, str, str, str]",
    "ROMANCE_CJK_BY_RU: Dict[str, RomanceCjk] = {",
]
for ru in sorted(updated):
    lines.append(f"    {ru!r}: {updated[ru]!r},")
lines.append("}")
out.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", out)
