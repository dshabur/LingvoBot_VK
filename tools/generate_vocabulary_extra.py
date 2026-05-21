# -*- coding: utf-8 -*-
"""Генерирует vocabulary_extra.py — расширение словарей всех языков."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

_CODE = Path(__file__).resolve().parent.parent
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from vocabulary_seed import WORDS_DE, WORDS_EN, WORDS_FR  # noqa: E402
from vocabulary_more import WORDS_ES, WORDS_IT, WORDS_JA, WORDS_PT, WORDS_ZH  # noqa: E402

try:
    from vocabulary_extra_data import ROMANCE_CJK_BY_RU  # noqa: E402
except ImportError:
    ROMANCE_CJK_BY_RU: Dict[str, Tuple[str, str, str, str, str]] = {}

WordRow = Tuple[str, str, str, str]

# en -> es, it, pt, zh, ja (дополняет выравнивание по DE/FR)
ROMANCE_ZH_JA: Dict[str, Tuple[str, str, str, str, str]] = {}


def _rz(en: str, es: str, it: str, pt: str, zh: str, ja: str) -> None:
    ROMANCE_ZH_JA[en.casefold()] = (es, it, pt, zh, ja)


# --- Пакет новых слов (EN + все языки) ---
_NEW = [
    ("juice", "сок", "еда", "beginner", "Saft", "jus", "zumo", "succo", "sumo", "果汁", "ジュース"),
    ("pear", "груша", "еда", "beginner", "Birne", "poire", "pera", "pera", "pêra", "梨", "なし"),
    ("grape", "виноград", "еда", "beginner", "Traube", "raisin", "uva", "uva", "uva", "葡萄", "ぶどう"),
    ("wine", "вино", "еда", "beginner", "Wein", "vin", "vino", "vino", "vinho", "葡萄酒", "ワイン"),
    ("beer", "пиво", "еда", "beginner", "Bier", "bière", "cerveza", "birra", "cerveja", "啤酒", "ビール"),
    ("honey", "мёд", "еда", "beginner", "Honig", "miel", "miel", "miele", "mel", "蜂蜜", "はちみつ"),
    ("cake", "торт", "еда", "beginner", "Kuchen", "gâteau", "pastel", "torta", "bolo", "蛋糕", "ケーキ"),
    ("chicken", "курица", "еда", "beginner", "Huhn", "poulet", "pollo", "pollo", "frango", "鸡肉", "にわとり"),
    ("beef", "говядина", "еда", "beginner", "Rindfleisch", "bœuf", "carne de res", "manzo", "carne", "牛肉", "ぎゅうにく"),
    ("pork", "свинина", "еда", "beginner", "Schweinefleisch", "porc", "cerdo", "maiale", "porco", "猪肉", "ぶたにく"),
    ("salad", "салат", "еда", "beginner", "Salat", "salade", "ensalada", "insalata", "salada", "沙拉", "サラダ"),
    ("pizza", "пицца", "еда", "beginner", "Pizza", "pizza", "pizza", "pizza", "pizza", "披萨", "ピザ"),
    ("chocolate", "шоколад", "еда", "beginner", "Schokolade", "chocolat", "chocolate", "cioccolato", "chocolate", "巧克力", "チョコレート"),
    ("grandmother", "бабушка", "семья", "beginner", "Großmutter", "grand-mère", "abuela", "nonna", "avó", "奶奶", "おばあさん"),
    ("grandfather", "дедушка", "семья", "beginner", "Großvater", "grand-père", "abuelo", "nonno", "avô", "爷爷", "おじいさん"),
    ("husband", "муж", "семья", "beginner", "Ehemann", "mari", "esposo", "marito", "marido", "丈夫", "おっと"),
    ("wife", "жена", "семья", "beginner", "Ehefrau", "femme", "esposa", "moglie", "esposa", "妻子", "つま"),
    ("uncle", "дядя", "семья", "beginner", "Onkel", "oncle", "tío", "zio", "tio", "叔叔", "おじ"),
    ("aunt", "тётя", "семья", "beginner", "Tante", "tante", "tía", "zia", "tia", "阿姨", "おば"),
    ("cousin", "двоюродный брат", "семья", "intermediate", "Cousin", "cousin", "primo", "cugino", "primo", "表兄弟", "いとこ"),
    ("apartment", "квартира", "быт", "beginner", "Wohnung", "appartement", "apartamento", "appartamento", "apartamento", "公寓", "アパート"),
    ("floor", "пол", "быт", "beginner", "Boden", "sol", "suelo", "pavimento", "chão", "地板", "ゆか"),
    ("wall", "стена", "быт", "beginner", "Wand", "mur", "pared", "muro", "parede", "墙", "かべ"),
    ("roof", "крыша", "быт", "beginner", "Dach", "toit", "tejado", "tetto", "telhado", "屋顶", "やね"),
    ("garden", "сад", "быт", "beginner", "Garten", "jardin", "jardín", "giardino", "jardim", "花园", "にわ"),
    ("lamp", "лампа", "быт", "beginner", "Lampe", "lampe", "lámpara", "lampada", "lâmpada", "灯", "ランプ"),
    ("mirror", "зеркало", "быт", "beginner", "Spiegel", "miroir", "espejo", "specchio", "espelho", "镜子", "かがみ"),
    ("soap", "мыло", "быт", "beginner", "Seife", "savon", "jabón", "sapone", "sabão", "肥皂", "せっけん"),
    ("towel", "полотенце", "быт", "beginner", "Handtuch", "serviette", "toalla", "asciugamano", "toalha", "毛巾", "タオル"),
    ("cloud", "облако", "природа", "beginner", "Wolke", "nuage", "nube", "nuvola", "nuvem", "云", "くも"),
    ("sky", "небо", "природа", "beginner", "Himmel", "ciel", "cielo", "cielo", "céu", "天空", "そら"),
    ("earth", "земля", "природа", "beginner", "Erde", "terre", "tierra", "terra", "terra", "地球", "ちきゅう"),
    ("fire", "огонь", "природа", "beginner", "Feuer", "feu", "fuego", "fuoco", "fogo", "火", "ひ"),
    ("ice", "лёд", "природа", "beginner", "Eis", "glace", "hielo", "ghiaccio", "gelo", "冰", "こおり"),
    ("lake", "озеро", "природа", "beginner", "See", "lac", "lago", "lago", "lago", "湖", "みずうみ"),
    ("beach", "пляж", "природа", "beginner", "Strand", "plage", "playa", "spiaggia", "praia", "海滩", "はまべ"),
    ("rabbit", "кролик", "животные", "beginner", "Kaninchen", "lapin", "conejo", "coniglio", "coelho", "兔子", "うさぎ"),
    ("mouse", "мышь", "животные", "beginner", "Maus", "souris", "ratón", "topo", "rato", "老鼠", "ねずみ"),
    ("bear", "медведь", "животные", "beginner", "Bär", "ours", "oso", "orso", "urso", "熊", "くま"),
    ("wolf", "волк", "животные", "beginner", "Wolf", "loup", "lobo", "lupo", "lobo", "狼", "おおかみ"),
    ("elephant", "слон", "животные", "beginner", "Elefant", "éléphant", "elefante", "elefante", "elefante", "大象", "ぞう"),
    ("lion", "лев", "животные", "beginner", "Löwe", "lion", "león", "leone", "leão", "狮子", "ライオン"),
    ("tiger", "тигр", "животные", "beginner", "Tiger", "tigre", "tigre", "tigre", "tigre", "老虎", "トラ"),
    ("orange_color", "оранжевый", "цвета", "beginner", "orange", "orange", "naranja", "arancione", "laranja", "橙色", "オレンジ"),
    ("purple", "фиолетовый", "цвета", "beginner", "lila", "violet", "morado", "viola", "roxo", "紫色", "むらさき"),
    ("brown", "коричневый", "цвета", "beginner", "braun", "marron", "marrón", "marrone", "castanho", "棕色", "ちゃいろ"),
    ("gray", "серый", "цвета", "beginner", "grau", "gris", "gris", "grigio", "cinzento", "灰色", "はいいろ"),
    ("pink", "розовый", "цвета", "beginner", "rosa", "rose", "rosa", "rosa", "rosa", "粉色", "ピンク"),
    ("long", "длинный", "описание", "beginner", "lang", "long", "largo", "lungo", "longo", "长", "ながい"),
    ("short", "короткий", "описание", "beginner", "kurz", "court", "corto", "corto", "curto", "短", "みじかい"),
    ("hot", "горячий", "описание", "beginner", "heiß", "chaud", "caliente", "caldo", "quente", "热", "あつい"),
    ("cold", "холодный", "описание", "beginner", "kalt", "froid", "frío", "freddo", "frio", "冷", "つめたい"),
    ("fast", "быстрый", "описание", "beginner", "schnell", "rapide", "rápido", "veloce", "rápido", "快", "はやい"),
    ("slow", "медленный", "описание", "beginner", "langsam", "lent", "lento", "lento", "lento", "慢", "おそい"),
    ("easy", "лёгкий", "описание", "beginner", "leicht", "facile", "fácil", "facile", "fácil", "容易", "かんたん"),
    ("difficult", "трудный", "описание", "beginner", "schwierig", "difficile", "difícil", "difficile", "difícil", "难", "むずかしい"),
    ("angry", "злой", "эмоции", "beginner", "wütend", "en colère", "enfadado", "arrabbiato", "zangado", "生气", "おこっている"),
    ("afraid", "испуганный", "эмоции", "beginner", "ängstlich", "effrayé", "asustado", "spaventato", "assustado", "害怕", "こわい"),
    ("tired", "уставший", "эмоции", "beginner", "müde", "fatigué", "cansado", "stanco", "cansado", "累", "つかれた"),
    ("love", "любовь", "эмоции", "beginner", "Liebe", "amour", "amor", "amore", "amor", "爱", "あい"),
    ("run", "бежать", "глаголы", "beginner", "rennen", "courir", "correr", "correre", "correr", "跑", "はしる"),
    ("walk", "ходить", "глаголы", "beginner", "gehen", "marcher", "caminar", "camminare", "andar", "走", "あるく"),
    ("read", "читать", "глаголы", "beginner", "lesen", "lire", "leer", "leggere", "ler", "读", "よむ"),
    ("write", "писать", "глаголы", "beginner", "schreiben", "écrire", "escribir", "scrivere", "escrever", "写", "かく"),
    ("speak", "говорить", "глаголы", "beginner", "sprechen", "parler", "hablar", "parlare", "falar", "说", "はなす"),
    ("listen", "слушать", "глаголы", "beginner", "zuhören", "écouter", "escuchar", "ascoltare", "ouvir", "听", "きく"),
    ("think", "думать", "глаголы", "beginner", "denken", "penser", "pensar", "pensare", "pensar", "想", "かんがえる"),
    ("work_verb", "работать", "глаголы", "beginner", "arbeiten", "travailler", "trabajar", "lavorare", "trabalhar", "工作", "はたらく"),
    ("study", "учиться", "глаголы", "beginner", "lernen", "étudier", "estudiar", "studiare", "estudar", "学习", "べんきょうする"),
    ("buy", "покупать", "глаголы", "beginner", "kaufen", "acheter", "comprar", "comprare", "comprar", "买", "かう"),
    ("sell", "продавать", "глаголы", "intermediate", "verkaufen", "vendre", "vender", "vendere", "vender", "卖", "うる"),
    ("six", "шесть", "числа", "beginner", "sechs", "six", "seis", "sei", "seis", "六", "ろく"),
    ("seven", "семь", "числа", "beginner", "sieben", "sept", "siete", "sette", "sete", "七", "なな"),
    ("eight", "восемь", "числа", "beginner", "acht", "huit", "ocho", "otto", "oito", "八", "はち"),
    ("nine", "девять", "числа", "beginner", "neun", "neuf", "nueve", "nove", "nove", "九", "きゅう"),
    ("ten", "десять", "числа", "beginner", "zehn", "dix", "diez", "dieci", "dez", "十", "じゅう"),
    ("hundred", "сто", "числа", "intermediate", "hundert", "cent", "cien", "cento", "cem", "百", "ひゃく"),
    ("week", "неделя", "время", "beginner", "Woche", "semaine", "semana", "settimana", "semana", "星期", "しゅう"),
    ("month", "месяц", "время", "beginner", "Monat", "mois", "mes", "mese", "mês", "月", "つき"),
    ("year", "год", "время", "beginner", "Jahr", "an", "año", "anno", "ano", "年", "とし"),
    ("hour", "час", "время", "beginner", "Stunde", "heure", "hora", "ora", "hora", "小时", "じかん"),
    ("minute", "минута", "время", "beginner", "Minute", "minute", "minuto", "minuto", "minuto", "分钟", "ふん"),
    ("spring", "весна", "время", "beginner", "Frühling", "printemps", "primavera", "primavera", "primavera", "春天", "はる"),
    ("summer", "лето", "время", "beginner", "Sommer", "été", "verano", "estate", "verão", "夏天", "なつ"),
    ("autumn", "осень", "время", "beginner", "Herbst", "automne", "otoño", "autunno", "outono", "秋天", "あき"),
    ("winter", "зима", "время", "beginner", "Winter", "hiver", "invierno", "inverno", "inverno", "冬天", "ふゆ"),
    ("lesson", "урок", "школа", "beginner", "Unterricht", "leçon", "lección", "lezione", "lição", "课", "じゅぎょう"),
    ("exam", "экзамен", "школа", "intermediate", "Prüfung", "examen", "examen", "esame", "exame", "考试", "しけん"),
    ("university", "университет", "школа", "intermediate", "Universität", "université", "universidad", "università", "universidade", "大学", "だいがく"),
    ("shirt", "рубашка", "одежда", "beginner", "Hemd", "chemise", "camisa", "camicia", "camisa", "衬衫", "シャツ"),
    ("pants", "брюки", "одежда", "beginner", "Hose", "pantalon", "pantalones", "pantaloni", "calças", "裤子", "ズボン"),
    ("dress", "платье", "одежда", "beginner", "Kleid", "robe", "vestido", "vestito", "vestido", "连衣裙", "ワンピース"),
    ("shoes", "обувь", "одежда", "beginner", "Schuhe", "chaussures", "zapatos", "scarpe", "sapatos", "鞋", "くつ"),
    ("hat", "шляпа", "одежда", "beginner", "Hut", "chapeau", "sombrero", "cappello", "chapéu", "帽子", "ぼうし"),
    ("coat", "пальто", "одежда", "beginner", "Mantel", "manteau", "abrigo", "cappotto", "casaco", "大衣", "コート"),
    ("head", "голова", "тело", "beginner", "Kopf", "tête", "cabeza", "testa", "cabeça", "头", "あたま"),
    ("hand", "рука", "тело", "beginner", "Hand", "main", "mano", "mano", "mão", "手", "て"),
    ("foot", "нога", "тело", "beginner", "Fuß", "pied", "pie", "piede", "pé", "脚", "あし"),
    ("eye", "глаз", "тело", "beginner", "Auge", "œil", "ojo", "occhio", "olho", "眼睛", "め"),
    ("ear", "ухо", "тело", "beginner", "Ohr", "oreille", "oreja", "orecchio", "orelha", "耳朵", "みみ"),
    ("nose", "нос", "тело", "beginner", "Nase", "nez", "nariz", "naso", "nariz", "鼻子", "はな"),
    ("mouth", "рот", "тело", "beginner", "Mund", "bouche", "boca", "bocca", "boca", "嘴", "くち"),
    ("heart", "сердце", "тело", "beginner", "Herz", "cœur", "corazón", "cuore", "coração", "心", "こころ"),
    ("back", "спина", "тело", "beginner", "Rücken", "dos", "espalda", "schiena", "costas", "背", "せなか"),
    ("car", "машина", "транспорт", "beginner", "Auto", "voiture", "coche", "macchina", "carro", "汽车", "くるま"),
    ("bus", "автобус", "транспорт", "beginner", "Bus", "bus", "autobús", "autobus", "autocarro", "公共汽车", "バス"),
    ("train", "поезд", "транспорт", "beginner", "Zug", "train", "tren", "treno", "comboio", "火车", "でんしゃ"),
    ("bicycle", "велосипед", "транспорт", "beginner", "Fahrrad", "vélo", "bicicleta", "bicicletta", "bicicleta", "自行车", "じてんしゃ"),
    ("road", "дорога", "транспорт", "beginner", "Straße", "route", "carretera", "strada", "estrada", "路", "みち"),
    ("map", "карта", "транспорт", "beginner", "Karte", "carte", "mapa", "mappa", "mapa", "地图", "ちず"),
    ("hotel", "отель", "путешествия", "beginner", "Hotel", "hôtel", "hotel", "hotel", "hotel", "酒店", "ホテル"),
    ("passport", "паспорт", "путешествия", "intermediate", "Reisepass", "passeport", "pasaporte", "passaporto", "passaporte", "护照", "パスポート"),
    ("money", "деньги", "город", "beginner", "Geld", "argent", "dinero", "denaro", "dinheiro", "钱", "おかね"),
    ("shop", "магазин", "город", "beginner", "Laden", "magasin", "tienda", "negozio", "loja", "商店", "みせ"),
    ("market", "рынок", "город", "beginner", "Markt", "marché", "mercado", "mercato", "mercado", "市场", "いちば"),
    ("police", "полиция", "город", "intermediate", "Polizei", "police", "policía", "polizia", "polícia", "警察", "けいさつ"),
    ("pharmacy", "аптека", "город", "beginner", "Apotheke", "pharmacie", "farmacia", "farmacia", "farmácia", "药店", "やっきょく"),
    ("restaurant", "ресторан", "город", "beginner", "Restaurant", "restaurant", "restaurante", "ristorante", "restaurante", "餐厅", "レストラン"),
    ("cinema", "кинотеатр", "город", "beginner", "Kino", "cinéma", "cine", "cinema", "cinema", "电影院", "えいがかん"),
    ("museum", "музей", "город", "intermediate", "Museum", "musée", "museo", "museo", "museu", "博物馆", "はくぶつかん"),
    ("park", "парк", "город", "beginner", "Park", "parc", "parque", "parco", "parque", "公园", "こうえん"),
    ("sport", "спорт", "спорт", "beginner", "Sport", "sport", "deporte", "sport", "desporto", "运动", "スポーツ"),
    ("football", "футбол", "спорт", "beginner", "Fußball", "football", "fútbol", "calcio", "futebol", "足球", "サッカー"),
    ("swimming", "плавание", "спорт", "beginner", "Schwimmen", "natation", "natación", "nuoto", "natação", "游泳", "すいえい"),
    ("music", "музыка", "культура", "beginner", "Musik", "musique", "música", "musica", "música", "音乐", "おんがく"),
    ("song", "песня", "культура", "beginner", "Lied", "chanson", "canción", "canzone", "canção", "歌", "うた"),
    ("film", "фильм", "культура", "beginner", "Film", "film", "película", "film", "filme", "电影", "えいが"),
    ("art", "искусство", "культура", "intermediate", "Kunst", "art", "arte", "arte", "arte", "艺术", "げいじゅつ"),
    ("history", "история", "культура", "intermediate", "Geschichte", "histoire", "historia", "storia", "história", "历史", "れきし"),
    ("science", "наука", "наука", "intermediate", "Wissenschaft", "science", "ciencia", "scienza", "ciência", "科学", "かがく"),
    ("nature", "природа", "природа", "intermediate", "Natur", "nature", "naturaleza", "natura", "natureza", "自然", "しぜん"),
    ("environment", "окружающая среда", "природа", "advanced", "Umwelt", "environnement", "medio ambiente", "ambiente", "ambiente", "环境", "かんきょう"),
    ("energy", "энергия", "наука", "intermediate", "Energie", "énergie", "energía", "energia", "energia", "能源", "エネルギー"),
    ("data", "данные", "наука", "intermediate", "Daten", "données", "datos", "dati", "dados", "数据", "データ"),
    ("software", "программное обеспечение", "наука", "advanced", "Software", "logiciel", "software", "software", "software", "软件", "ソフトウェア"),
    ("network", "сеть", "наука", "advanced", "Netzwerk", "réseau", "red", "rete", "rede", "网络", "ネットワーク"),
    ("security", "безопасность", "абстракции", "advanced", "Sicherheit", "sécurité", "seguridad", "sicurezza", "segurança", "安全", "あんぜん"),
    ("freedom", "свобода", "абстракции", "advanced", "Freiheit", "liberté", "libertad", "libertà", "liberdade", "自由", "じゆう"),
    ("justice", "справедливость", "общество", "advanced", "Gerechtigkeit", "justice", "justicia", "giustizia", "justiça", "正义", "せいぎ"),
    ("democracy", "демократия", "общество", "advanced", "Demokratie", "démocratie", "democracia", "democrazia", "democracia", "民主", "みんしゅ"),
    ("economy", "экономика", "общество", "advanced", "Wirtschaft", "économie", "economía", "economia", "economia", "经济", "けいざい"),
    ("society", "общество", "общество", "intermediate", "Gesellschaft", "société", "sociedad", "società", "sociedade", "社会", "しゃかい"),
    ("relationship", "отношения", "общение", "intermediate", "Beziehung", "relation", "relación", "relazione", "relação", "关系", "かんけい"),
    ("agreement", "соглашение", "общение", "intermediate", "Vereinbarung", "accord", "acuerdo", "accordo", "acordo", "协议", "きょうてい"),
    ("negotiation", "переговоры", "работа", "advanced", "Verhandlung", "négociation", "negociación", "negoziazione", "negociação", "谈判", "こうしょう"),
    ("leadership", "лидерство", "работа", "advanced", "Führung", "leadership", "liderazgo", "leadership", "liderança", "领导力", "リーダーシップ"),
    ("innovation", "инновация", "работа", "advanced", "Innovation", "innovation", "innovación", "innovazione", "inovação", "创新", "イノベーション"),
    ("strategy", "стратегия", "работа", "advanced", "Strategie", "stratégie", "estrategia", "strategia", "estratégia", "战略", "せんりゃく"),
    ("analysis", "анализ", "наука", "advanced", "Analyse", "analyse", "análisis", "analisi", "análise", "分析", "ぶんせき"),
    ("perspective", "перспектива", "абстракции", "advanced", "Perspektive", "perspective", "perspectiva", "prospettiva", "perspetiva", "视角", "てんぼう"),
]

for row in _NEW:
    en, ru, cat, diff, de, fr, es, it, pt, zh, ja = row
    _rz(en, es, it, pt, zh, ja)


def _index_by_ru(rows: List[WordRow]) -> Dict[Tuple[str, str], WordRow]:
    return {(b.strip().lower(), c): (a, b, c, d) for a, b, c, d in rows}


def _dedupe(rows: List[WordRow]) -> List[WordRow]:
    seen = set()
    out: List[WordRow] = []
    for a, b, c, d in rows:
        k = (a.casefold(), b.casefold())
        if k in seen:
            continue
        seen.add(k)
        out.append((a, b, c, d))
    return out


def _minus(base: List[WordRow], extra: List[WordRow]) -> List[WordRow]:
    keys = {(a.casefold(), b.casefold()) for a, b, c, d in base}
    return [r for r in extra if (r[0].casefold(), r[1].casefold()) not in keys]


def _build_aligned_extra(
    en_master: List[WordRow],
    base: List[WordRow],
    lang: str,
    de_idx: Dict[Tuple[str, str], WordRow],
    fr_idx: Dict[Tuple[str, str], WordRow],
    rom_idx: Dict[Tuple[str, str], WordRow],
) -> List[WordRow]:
    out: List[WordRow] = []
    for en, ru, cat, diff in en_master:
        key = (ru.strip().lower(), cat)
        if lang == "en":
            word = en
        elif lang == "de":
            word = de_idx.get(key, (en, ru, cat, diff))[0]
        elif lang == "fr":
            word = fr_idx.get(key, (en, ru, cat, diff))[0]
        elif lang in ("es", "it", "pt"):
            rom = ROMANCE_CJK_BY_RU.get(ru.strip().lower())
            if key in rom_idx:
                word = rom_idx[key][0]
            elif en.casefold() in ROMANCE_ZH_JA:
                idx = {"es": 0, "it": 1, "pt": 2}[lang]
                word = ROMANCE_ZH_JA[en.casefold()][idx]
            elif rom:
                idx = {"es": 0, "it": 1, "pt": 2}[lang]
                word = rom[idx]
            else:
                continue
        elif lang == "zh":
            rom = ROMANCE_CJK_BY_RU.get(ru.strip().lower())
            if en.casefold() in ROMANCE_ZH_JA:
                word = ROMANCE_ZH_JA[en.casefold()][3]
            elif rom and rom[3]:
                word = rom[3]
            elif key in rom_idx:
                word = rom_idx[key][0]
            else:
                continue
        elif lang == "ja":
            rom = ROMANCE_CJK_BY_RU.get(ru.strip().lower())
            if en.casefold() in ROMANCE_ZH_JA:
                word = ROMANCE_ZH_JA[en.casefold()][4]
            elif rom and rom[4]:
                word = rom[4]
            elif key in rom_idx:
                word = rom_idx[key][0]
            else:
                continue
        else:
            continue
        out.append((word, ru, cat, diff))
    return _minus(base, _dedupe(out))


def main() -> None:
    de_idx = _index_by_ru(WORDS_DE)
    fr_idx = _index_by_ru(WORDS_FR)
    es_idx = _index_by_ru(WORDS_ES)
    it_idx = _index_by_ru(WORDS_IT)
    pt_idx = _index_by_ru(WORDS_PT)
    zh_idx = _index_by_ru(WORDS_ZH)
    ja_idx = _index_by_ru(WORDS_JA)

    en_master = list(WORDS_EN)
    existing = {w.casefold() for w, *_ in en_master}
    for en, ru, cat, diff, *_ in _NEW:
        if en.casefold() not in existing:
            en_master.append((en, ru, cat, diff))
            existing.add(en.casefold())

    extra_en = _minus(WORDS_EN, [(e, r, c, d) for e, r, c, d in en_master if (e, r, c) not in {(x.casefold(), y) for x, y, _, _ in WORDS_EN}])
    # проще: все новые EN из _NEW
    extra_en = _minus(WORDS_EN, [tuple(row[:4]) for row in _NEW])

    extra_de = _build_aligned_extra(en_master, WORDS_DE, "de", de_idx, fr_idx, es_idx)
    extra_fr = _build_aligned_extra(en_master, WORDS_FR, "fr", de_idx, fr_idx, es_idx)
    extra_es = _build_aligned_extra(en_master, WORDS_ES, "es", de_idx, fr_idx, es_idx)
    extra_it = _build_aligned_extra(en_master, WORDS_IT, "it", de_idx, fr_idx, it_idx)
    extra_pt = _build_aligned_extra(en_master, WORDS_PT, "pt", de_idx, fr_idx, pt_idx)
    extra_zh = _build_aligned_extra(en_master, WORDS_ZH, "zh", de_idx, fr_idx, zh_idx)
    extra_ja = _build_aligned_extra(en_master, WORDS_JA, "ja", de_idx, fr_idx, ja_idx)

    out_path = _CODE / "vocabulary_extra.py"
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""Дополнительные слова (генерируется tools/generate_vocabulary_extra.py)."""',
        "from __future__ import annotations",
        "from typing import List, Tuple",
        "WordRow = Tuple[str, str, str, str]",
        "",
    ]

    def dump(name: str, rows: List[WordRow]) -> None:
        lines.append(f"{name}: List[WordRow] = [")
        for a, b, c, d in rows:
            lines.append(f"    ({a!r}, {b!r}, {c!r}, {d!r}),")
        lines.append("]")
        lines.append("")

    dump("EXTRA_EN", extra_en)
    dump("EXTRA_DE", extra_de)
    dump("EXTRA_FR", extra_fr)
    dump("EXTRA_ES", extra_es)
    dump("EXTRA_IT", extra_it)
    dump("EXTRA_PT", extra_pt)
    dump("EXTRA_ZH", extra_zh)
    dump("EXTRA_JA", extra_ja)

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("Written", out_path)
    for name, rows in [
        ("EN", extra_en),
        ("DE", extra_de),
        ("FR", extra_fr),
        ("ES", extra_es),
        ("IT", extra_it),
        ("PT", extra_pt),
        ("ZH", extra_zh),
        ("JA", extra_ja),
    ]:
        print(name, len(rows))


if __name__ == "__main__":
    main()
