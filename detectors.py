import re
from functools import lru_cache
from typing import Dict, List

from natasha import Segmenter, NewsNERTagger, NewsEmbedding, Doc
from sentence_transformers import SentenceTransformer

from data import (
    CommonCategory, GovernmentCategory, PaymentCategory,
    BiometricCategory, SpecialCategory, Category,
)


@lru_cache(maxsize=1)
def _ner_components():
    emb = NewsEmbedding()
    return Segmenter(), NewsNERTagger(emb)


@lru_cache(maxsize=1)
def _semantic_model():
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")


# Эталонные фразы для каждой категории
_SEMANTIC_CATEGORIES = {
    BiometricCategory.FINGERPRINT: [
        "отпечаток пальца", "дактилоскопия", "fingerprint", "дактилоскопические данные",
        "биометрические данные отпечатков", "сканирование отпечатков пальцев",
        "хранение дактилоскопических данных", "дактилоскопический учёт",
    ],
    BiometricCategory.IRIS: [
        "радужная оболочка глаза", "сканирование сетчатки", "iris scan", "распознавание по радужке",
    ],
    BiometricCategory.VOICE: [
        "голосовой отпечаток", "voice biometrics", "voiceprint", "голосовая биометрия",
    ],
    BiometricCategory.FACE: [
        "распознавание лица", "геометрия лица", "face recognition", "идентификация по лицу",
    ],
    BiometricCategory.DNA: [
        "ДНК анализ", "геном человека", "DNA sample", "анализ ДНК", "генетические данные",
    ],
    SpecialCategory.HEALTH: [
        "диагноз пациента", "состояние здоровья", "медицинская карта", "инвалидность",
        "медицинский диагноз", "история болезни", "данные о здоровье", "заболевание пациента",
    ],
    SpecialCategory.BELIEFS: [
        "религиозные убеждения", "политические взгляды", "судимость", "вероисповедание",
        "исповедует религию", "политические убеждения", "уголовная судимость",
    ],
    SpecialCategory.RACE: [
        "расовая принадлежность", "национальность", "этническое происхождение",
        "этническая принадлежность", "расовая и национальная принадлежность",
    ],
    SpecialCategory.INTIMATE: [
        "сексуальная ориентация", "интимная жизнь", "sexual orientation", "половая принадлежность",
    ],
}

_SEMANTIC_THRESHOLD = 0.9


@lru_cache(maxsize=1)
def _reference_embeddings():
    model = _semantic_model()
    return {
        cat: model.encode(phrases, normalize_embeddings=True)
        for cat, phrases in _SEMANTIC_CATEGORIES.items()
    }


def semantic_detect(text: str, chunk_size: int = 500) -> Dict:
    """Делит текст на чанки и ищет семантически близкие категории ПДн."""
    if not text or len(text) < 10:
        return {}

    model = _semantic_model()
    ref_embs = _reference_embeddings()

    # Делим текст на чанки по chunk_size символов с перекрытием 50
    words = text.split()
    chunks, buf, buf_len = [], [], 0
    for word in words:
        buf.append(word)
        buf_len += len(word) + 1
        if buf_len >= chunk_size:
            chunks.append(" ".join(buf))
            buf = buf[-10:]  # перекрытие ~10 слов
            buf_len = sum(len(w) + 1 for w in buf)
    if buf:
        chunks.append(" ".join(buf))

    if not chunks:
        return {}

    chunk_embs = model.encode(chunks, normalize_embeddings=True, batch_size=32)

    low = text.lower()
    found = {}
    for cat, ref in ref_embs.items():
        sims = chunk_embs @ ref.T
        if sims.max() >= _SEMANTIC_THRESHOLD:
            found[cat] = 1
    return found


def extract_persons(text: str) -> int:
    """Возвращает количество уникальных персон (PER) через NER natasha."""
    if not text or len(text) < 3:
        return 0
    segmenter, ner_tagger = _ner_components()
    doc = Doc(text[:50_000])  # ограничиваем для скорости
    doc.segment(segmenter)
    doc.tag_ner(ner_tagger)
    persons = {span.text for span in doc.spans if span.type == "PER"}
    return len(persons)

_ALL_CATEGORIES = (
    list(CommonCategory) + list(GovernmentCategory) +
    list(PaymentCategory) + list(BiometricCategory) + list(SpecialCategory)
)


def _empty_cats() -> Dict[Category, int]:
    return {cat: 0 for cat in _ALL_CATEGORIES}


# Признаки публикаций/книг — при наличии любого из них текст не содержит ПДн
_PUBLICATION_MARKERS = [
    # Книги и издания
    "издательство", "издатель", "издано", "издана", "издание",
    "isbn", "issn", "doi:", "udc ", "удк ", "ббк ",
    "тираж", "переплёт", "переплет", "суперобложка",
    "все права защищены", "all rights reserved",
    "copyright ©", "©", "printed in",
    # Научные статьи и журналы
    "аннотация:", "abstract:", "ключевые слова:", "keywords:",
    "список литературы", "references:", "библиография",
    "поступила в редакцию", "received:", "accepted:",
    "журнал ", "вестник ", "сборник статей", "proceedings of",
    # Учебники и методички
    "учебник", "учебное пособие", "методическое пособие",
    "для студентов", "допущено министерством",
    "рекомендовано к изданию",
    # Художественная литература
    "глава ", "глава\n", "часть первая", "часть вторая",
    "пролог", "эпилог", "предисловие автора",
    # Нормативные документы (законы, госты — не ПДн людей)
    "гост р ", "гост р\n", "iso ", "iec ", "din ",
    "федеральный закон", "постановление правительства",
    "приказ минист", "технический регламент",
    # Инструкции
    "служба поддержки", "импортер", "свяжитесь с нами", "contact us",
    "правила проведения", "политика обработки персональных данных",
    "расписание", "план обучения", "документация", "правила пользования",
    "инструкция", "руководство пользователя"
]

PROGRAM_RE = re.compile(r"[0-9][0-9].[0-9][0-9].[0-9][0-9]")


# def is_publication(text: str) -> bool:
#     """Возвращает True если текст похож на книгу/статью/норматив, а не на ПДн-документ."""
#     low = text[:5000].lower()  # проверяем только начало — маркеры обычно в шапке
#     return any(marker in low for marker in _PUBLICATION_MARKERS)

def is_publication(text: str) -> bool:
    """Возвращает True если текст похож на книгу/статью/норматив, а не на ПДн-документ."""
    low = text[:5000].lower()  # проверяем только начало — маркеры обычно в шапке
    if any(marker in low for marker in _PUBLICATION_MARKERS):
        return True
    
    # Проверяем наличие года публикации в формате ", YYYY" в начале или конце текста
    text_len = len(text)
    start_part = text[:5000] if text_len > 5000 else text
    end_part = text[-5000:] if text_len > 5000 else text
    
    # Регулярное выражение для поиска ", 19XX" или ", 20XX" (годы 1900-2099)
    year_pattern = re.compile(r',\s+(19[0-9]{2}|20[0-9]{2})')
    
    if (year_pattern.search(start_part) or year_pattern.search(end_part)) or (PROGRAM_RE.search(start_part) or PROGRAM_RE.search(end_part)) :
        return True
    
    return False

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")

PHONE_RE = re.compile(r"(?:(?:\+7|8)\s*\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})")

DOB_RE = re.compile(
    r"(?:"
    r"\b\d{2}[./]\d{2}[./]\d{4}\b"                    # DD.MM.YYYY / DD/MM/YYYY
    r"|\b\d{4}-\d{2}-\d{2}\b"                           # ISO: YYYY-MM-DD
    r"|\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May"
    r"|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?"
    r"|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b"          # DD Month YYYY (EN)
    r")",
    re.IGNORECASE,
)

BIRTHPLACE_RE = re.compile(
    r"(?i)(?:место\s+рождения|уроженец\s+г(?:ород)?а?|уроженка\s+г(?:ород)?а?"
    r"|born\s+in|place\s+of\s+birth)[^\n]{0,80}"
)

ADDRESS_RE = re.compile(
    r"(?i)"
    r"(?:ул(?:ица)?\.?\s+[А-ЯЁа-яёA-Za-z\s\-]{3,40}"  # ул. Ленина
    r"|пр(?:осп(?:ект)?)?\.?\s+[А-ЯЁа-яё\s\-]{3,40}"   # пр. Мира
    r"|пер(?:еулок)?\.?\s+[А-ЯЁа-яё\s\-]{3,40}"         # пер. Садовый
    r"|\d+\s+[A-Z][a-z]+\s+(?:St|Ave|Blvd|Rd|Dr|Ln|Way|Ct)\.?"  # 123 Main St
    r")"
)

INDEX_RE = re.compile(r"\b\d{6}\b")

SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")

INN12_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")

PASSPORT_RU_RE = re.compile(r"(?:(?<!\d)\d{2}\s?\d{2}\s?\d{6}(?!\d))")

MRZ_RE = re.compile(r"[PVC]<[A-Z]{3}[A-Z<]{3,}")

DL_RU_RE = re.compile(r"(?<!\d)\d{10,12}(?!\d)")

SSN_RE = re.compile(
    r"(?i)(?:ssn|social\s+security(?:\s+number)?)\s*[:#]?\s*"
    r"(?<!\d)(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}(?!\d)"
)

CARD_RE = re.compile(r"(?:(?:\d[ -]*?){13,19})")
CVV_RE = re.compile(r"\b(CVV|CVC|CVV2)\b", re.IGNORECASE)
RS_RE = re.compile(r"(?i)(?:р/с|расч[её]тн(?:ый)?\s+сч[её]т)[^\d]*(\d{20})")
BIK_RE = re.compile(r"(?i)бик[^\d]*(\d{9})")

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b")

SWIFT_RE = re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")

ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b")

OMS_RE = re.compile(r"(?i)(?:омс|полис\s+омс|enhi)[^\d]{0,10}(\d{16})")


# Имена колонок CSV/JSON/Parquet, которые однозначно указывают на ПДн
PII_COLUMN_MAP: Dict[str, Category] = {
    # Обычные
    "email": CommonCategory.EMAIL, "e-mail": CommonCategory.EMAIL, "почта": CommonCategory.EMAIL,
    "phone": CommonCategory.PHONE, "телефон": CommonCategory.PHONE, "mobile": CommonCategory.PHONE,
    "фио": CommonCategory.NAME, "имя": CommonCategory.NAME, "фамилия": CommonCategory.NAME,
    "отчество": CommonCategory.NAME, "name": CommonCategory.NAME, "full_name": CommonCategory.NAME,
    "first_name": CommonCategory.NAME, "last_name": CommonCategory.NAME,
    "дата_рождения": CommonCategory.DATE, "birthdate": CommonCategory.DATE, "dob": CommonCategory.DATE,
    "адрес": CommonCategory.ADDRESS, "address": CommonCategory.ADDRESS, "город": CommonCategory.ADDRESS,
    "место_рождения": CommonCategory.ADDRESS, "birthplace": CommonCategory.ADDRESS,
    # Государственные
    "снилс": GovernmentCategory.SNILS, "snils": GovernmentCategory.SNILS,
    "инн": GovernmentCategory.INN, "inn": GovernmentCategory.INN,
    "паспорт": GovernmentCategory.PASSPORT, "passport": GovernmentCategory.PASSPORT,
    "серия": GovernmentCategory.PASSPORT, "номер_паспорта": GovernmentCategory.PASSPORT,
    "водительское": GovernmentCategory.DRIVER, "driver_license": GovernmentCategory.DRIVER,
    "ssn": GovernmentCategory.PASSPORT,
    # Платёжные
    "card": PaymentCategory.CARD, "карта": PaymentCategory.CARD, "card_number": PaymentCategory.CARD,
    "cvv": PaymentCategory.CVV, "cvc": PaymentCategory.CVV,
    "счёт": PaymentCategory.BANK_NUMBER, "account": PaymentCategory.BANK_NUMBER,
    "iban": PaymentCategory.BANK_NUMBER, "бик": PaymentCategory.BANK_NUMBER, "bik": PaymentCategory.BANK_NUMBER,
    # Биометрические
    "биометрия": BiometricCategory.FINGERPRINT, "biometrics": BiometricCategory.FINGERPRINT,
    "fingerprint": BiometricCategory.FINGERPRINT, "face_id": BiometricCategory.FACE,
    # Специальные
    "диагноз": SpecialCategory.HEALTH, "diagnosis": SpecialCategory.HEALTH,
    "religion": SpecialCategory.BELIEFS, "национальность": SpecialCategory.RACE,
}

def count_occurrences(pattern: re.Pattern, text: str) -> int:
    """Подсчитывает количество вхождений паттерна в тексте."""
    return len(list(pattern.finditer(text)))


def has_context(text_lower: str, pos: int, window: int, *keywords: str) -> bool:
    """
    Проверяет наличие контекстных ключевых слов рядом с позицией pos.
    Окно поиска: window символов влево и вправо.
    """
    start = max(0, pos - window)
    end = min(len(text_lower), pos + window)
    fragment = text_lower[start:end]
    return any(kw in fragment for kw in keywords)


def luhn_check(value: str) -> bool:
    """Проверяет номер карты по алгоритму Луна."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def snils_valid(raw: str) -> bool:
    """
    Контрольная сумма СНИЛС.
    Формат: XXX-XXX-XXX YY, где YY — контрольное число.
    """
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11:
        return False
    number = [int(digits[i]) for i in range(9)]
    control = int(digits[9:11])
    s = sum((9 - i) * number[i] for i in range(9))
    if s < 100:
        return s == control
    if s in (100, 101):
        return control == 0
    return (s % 101) % 100 == control


def inn_valid(inn: str) -> bool:
    """
    Контрольная сумма ИНН (10-значного юр. лица или 12-значного физ. лица).
    """
    if not inn.isdigit():
        return False
    d = [int(c) for c in inn]
    if len(d) == 10:
        weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        return (sum(w * v for w, v in zip(weights, d[:9])) % 11) % 10 == d[9]
    if len(d) == 12:
        w1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        w2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        c1 = (sum(w * v for w, v in zip(w1, d[:10])) % 11) % 10
        c2 = (sum(w * v for w, v in zip(w2, d[:11])) % 11) % 10
        return c1 == d[10] and c2 == d[11]
    return False

def find_cards(text: str) -> List[str]:
    """Ищет номера карт и фильтрует по алгоритму Луна."""
    return [m.group(0) for m in CARD_RE.finditer(text) if luhn_check(m.group(0))]

def detect_categories(
    text: str,
    column_hints: List[str] | None = None,
) -> List[Category]:
    """
    Анализирует текст и возвращает количество найденных ПДн по категориям.

    Args:
        text:          Извлечённый текст документа / ячейки / поля.
        column_hints:  Результат check_columns_fast() — быстрые подсказки
                       по именам колонок (опционально).

    Returns:
        Словарь { категория: количество_вхождений }
    """
    t: str = text if isinstance(text, str) else ""

    if is_publication(t):
        return []

    low: str = t.lower()

    cats = _empty_cats()

    # Быстрая проверка наличия ПДн по именам колонок CSV/JSON/Parquet.
    # Не требует построчного сканирования данных.
    # Возвращает счётчики по категориям.
    if column_hints:
        for col in column_hints:
            key = col.lower().strip().replace(" ", "_")
            # Точное совпадение
            if key in PII_COLUMN_MAP:
                cats[PII_COLUMN_MAP[key]] += 1
                continue
            # Частичное совпадение по подстрокам
            for pattern, category in PII_COLUMN_MAP.items():
                if pattern in key:
                    cats[category] += 1
                    break

    # ── Обычные ──────────────────────────────────────────────────────
    cats[CommonCategory.EMAIL] += count_occurrences(EMAIL_RE, t)
    cats[CommonCategory.PHONE] += count_occurrences(PHONE_RE, t)

    # ФИО: через NER natasha
    cats[CommonCategory.NAME] += extract_persons(t)

    # Дата рождения — только с контекстом
    for m in DOB_RE.finditer(t):
        if has_context(
            low, m.start(), 50,
            "дата рождения", "д.р.", "д/р", "родил", "born", "dob", "birth",
        ):
            cats[CommonCategory.DATE] += 1

    # Место рождения
    cats[CommonCategory.ADDRESS] += count_occurrences(BIRTHPLACE_RE, t)

    # Адрес — индекс с контекстом
    for m in INDEX_RE.finditer(t):
        if has_context(
            low, m.start(), 60,
            "ул", "улица", "просп", "пер", "дом", "квартира", "город", "г.",
            "street", "ave", "blvd", "zip", "postal",
        ):
            cats[CommonCategory.ADDRESS] += 1
    cats[CommonCategory.ADDRESS] += count_occurrences(ADDRESS_RE, t)

    # ── Государственные ─────────────────────────────────────────────
    cats[GovernmentCategory.SNILS] += count_occurrences(OMS_RE, t)
    for m in SNILS_RE.finditer(t):
        if snils_valid(m.group(0)):
            cats[GovernmentCategory.SNILS] += 1

    for m in INN12_RE.finditer(t):
        if inn_valid(m.group(0)):
            cats[GovernmentCategory.INN] += 1

    for m in PASSPORT_RU_RE.finditer(t):
        if has_context(
            low, m.start(), 20,
            "паспорт", "серия", "номер", "код подразделения",
        ):
            cats[GovernmentCategory.PASSPORT] += 1

    cats[GovernmentCategory.PASSPORT] += 5 if "identification" in t else 0
    cats[GovernmentCategory.PASSPORT] += 5 if "Identification" in t else 0

    for m in DL_RU_RE.finditer(t):
        if has_context(
            low, m.start(), 60,
            "водитель"
        ):
            cats[GovernmentCategory.DRIVER] += 1

    if MRZ_RE.search(t):
        cats[GovernmentCategory.MRZ] += 1

    # ── Платёжные ────────────────────────────────────────────────────
    for raw in find_cards(t):
        if has_context(
            low,
            t.find(raw.strip()),
            60,
            "visa", "mastercard", "мир", "карта", "card", "cvv", "cvc",
            "номер карты", "оплат",
        ):
            cats[PaymentCategory.CARD] += 1

    cats[PaymentCategory.BANK_NUMBER] += count_occurrences(RS_RE, t)
    cats[PaymentCategory.BANK_NUMBER] += count_occurrences(BIK_RE, t)
    cats[PaymentCategory.BANK_NUMBER] += count_occurrences(IBAN_RE, t)

    if CVV_RE.search(t):
        cats[PaymentCategory.CVV] += 1

    # ── Биометрические + Специальные — семантический поиск ──────────
    for cat, count in semantic_detect(t).items():
        cats[cat] += count

    return [cat for cat, n in cats.items() for _ in range(n)]
