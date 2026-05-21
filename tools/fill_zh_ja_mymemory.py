# -*- coding: utf-8 -*-
"""Быстрое заполнение zh/ja через MyMemory (без долгих пауз Google)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_CODE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_CODE))

from deep_translator import MyMemoryTranslator  # noqa: E402
from vocabulary_extra_data import ROMANCE_CJK_BY_RU  # noqa: E402
from vocabulary_seed import WORDS_EN  # noqa: E402

en_by_ru = {b.strip().lower(): a for a, b, c, d in WORDS_EN}
zh_t = MyMemoryTranslator(source="english", target="chinese simplified")
ja_t = MyMemoryTranslator(source="english", target="japanese")

updated = dict(ROMANCE_CJK_BY_RU)
todo = [ruk for ruk, t in updated.items() if not t[3] or not t[4]]
print(f"Fill zh/ja for {len(todo)} entries", flush=True)

for i, ruk in enumerate(todo):
    en = en_by_ru.get(ruk)
    if not en:
        continue
    es, it, pt, zh, ja = updated[ruk]
    try:
        if not zh:
            zh = zh_t.translate(en) or zh
        if not ja:
            ja = ja_t.translate(en) or ja
    except Exception as exc:
        print(f"fail {en!r}: {exc}", flush=True)
    updated[ruk] = (es, it, pt, zh or updated[ruk][3], ja or updated[ruk][4])
    if (i + 1) % 10 == 0:
        print(f"  {i + 1}/{len(todo)}", flush=True)
    time.sleep(0.05)

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
print("Wrote", out, flush=True)
