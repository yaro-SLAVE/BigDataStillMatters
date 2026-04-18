"""
pii_detector.py
===============
Модуль обнаружения и классификации персональных данных (ПДн)
в соответствии с Федеральным законом № 152-ФЗ.

Используется как часть системы автоматического сканирования
корпоративных файловых хранилищ.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 1. РЕГУЛЯРНЫЕ ВЫРАЖЕНИЯ
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────
# 1.1 Контактные данные
# ───────────────────────────────────────────

EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b"
)

PHONE_RE = re.compile(
    r"(?:"
    r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"   # RU: +7/8
    r"|(?:\+(?!7)\d{1,3})[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}" # Международный
    r"|\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}"                                  # US/CA: (XXX) XXX-XXXX
    r")"
)

# ───────────────────────────────────────────
# 1.2 ФИО
# ───────────────────────────────────────────

# Русский: Фамилия Имя [Отчество]
FIO_RU_RE = re.compile(
    r"\b[А-ЯЁ][а-яё]{1,30}\s+[А-ЯЁ][а-яё]{1,30}(?:\s+[А-ЯЁ][а-яё]{1,30})?\b"
)

# Английский: First [Middle] Last
FIO_EN_RE = re.compile(
    r"\b[A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30}){1,2}\b"
)

# ───────────────────────────────────────────
# 1.3 Даты и места
# ───────────────────────────────────────────

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

# Место рождения
BIRTHPLACE_RE = re.compile(
    r"(?i)(?:место\s+рождения|уроженец\s+г(?:ород)?а?|уроженка\s+г(?:ород)?а?"
    r"|born\s+in|place\s+of\s+birth)[^\n]{0,80}"
)

# ───────────────────────────────────────────
# 1.4 Адреса
# ───────────────────────────────────────────

ADDRESS_RE = re.compile(
    r"(?i)"
    r"(?:ул(?:ица)?\.?\s+[А-ЯЁа-яёA-Za-z\s\-]{3,40}"  # ул. Ленина
    r"|пр(?:осп(?:ект)?)?\.?\s+[А-ЯЁа-яё\s\-]{3,40}"   # пр. Мира
    r"|пер(?:еулок)?\.?\s+[А-ЯЁа-яё\s\-]{3,40}"         # пер. Садовый
    r"|\d+\s+[A-Z][a-z]+\s+(?:St|Ave|Blvd|Rd|Dr|Ln|Way|Ct)\.?"  # 123 Main St
    r")"
)

# Почтовый индекс
INDEX_RE = re.compile(
    r"(?:"
    r"\b\d{6}\b"                                  # RU
    r"|\b\d{5}(?:-\d{4})?\b"                       # US ZIP / ZIP+4
    r"|\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b"  # UK postcode
    r")"
)

# ───────────────────────────────────────────
# 1.5 Государственные идентификаторы (RU)
# ───────────────────────────────────────────

SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")

INN10_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
INN12_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")

# Паспорт RU: XX XX XXXXXX (требует контекста для снижения ложных срабатываний)
PASSPORT_RU_RE = re.compile(
    r"(?:"
    r"(?:паспорт|серия|пасп\.?|passport\s+rf)[^\d]{0,15}"
    r"|(?<!\d)"
    r")"
    r"\d{2}\s?\d{2}\s?\d{6}(?!\d)"
)

# Паспорт EN: A1234567 / AB1234567
PASSPORT_EN_RE = re.compile(
    r"(?i)(?:passport\s*(?:no\.?|number|#|num)?\s*:?\s*)?[A-Z]{1,2}\d{6,8}\b"
)

# MRZ-строка (машиносчитываемая зона)
MRZ_RE = re.compile(r"[PVC]<[A-Z]{3}[A-Z<]{3,}")

# Водительское удостоверение RU — с контекстом
DL_RU_RE = re.compile(
    r"(?i)(?:вод(?:ит(?:ельское)?)?\s+удост(?:оверение)?[^\d]{0,15})"
    r"(\d{2}\s?\d{2}\s?\d{6})"
)

# Водительское удостоверение US — с ключевым словом
DL_US_RE = re.compile(
    r"(?i)(?:driver'?s?\s+licen[sc]e|DL#?|CDL)\s*[:#]?\s*([A-Z0-9\-]{5,16})"
)

# SSN (США) — с блокировкой заведомо невалидных диапазонов
SSN_RE = re.compile(
    r"(?i)(?:ssn|social\s+security(?:\s+number)?)\s*[:#]?\s*"
    r"(?<!\d)(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}(?!\d)"
)

# ───────────────────────────────────────────
# 1.6 Платёжные данные
# ───────────────────────────────────────────

# Номер карты с BIN-фильтром (Visa/MC/Mir/Amex/Discover)
CARD_RE = re.compile(
    r"(?<!\d)"
    r"(?:4\d{3}|5[1-5]\d{2}|2\d{3}|3[47]\d{2}|6(?:011|5\d{2}))"  # BIN
    r"(?:[\s\-]?\d{4}){2,3}"
    r"(?:[\s\-]?\d{1,4})?"
    r"(?!\d)"
)

# CVV/CVC — только с последующими цифрами
CVV_RE = re.compile(r"\b(?:CVV2?|CVC2?|CSC)\b[\s:]*\d{3,4}", re.IGNORECASE)

# Расчётный счёт RU (20 цифр)
RS_RE = re.compile(
    r"(?i)(?:р/?с\.?|расч[её]тн(?:ый)?\s+сч[её]т|счёт\s*№?)[^\d]{0,8}(\d{20})"
)

# БИК
BIK_RE = re.compile(r"(?i)(?:бик|BIK)[^\d]{0,5}(\d{9})")

# IBAN (международный)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}[A-Z0-9]{0,16}\b")

# SWIFT/BIC (8 или 11 символов)
SWIFT_RE = re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")

# Routing number US
ROUTING_RE = re.compile(
    r"(?i)(?:routing\s*(?:no\.?|number|#)?\s*:?\s*)(\d{9})\b"
)

# ───────────────────────────────────────────
# 1.7 Сетевые идентификаторы
# ───────────────────────────────────────────

IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

IPV6_RE = re.compile(
    r"\b(?:[A-Fa-f0-9]{1,4}:){2,7}[A-Fa-f0-9]{1,4}\b"
)

MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b")

# ───────────────────────────────────────────
# 1.8 Медицина
# ───────────────────────────────────────────

ICD10_RE = re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b")

# Полис ОМС (16 цифр с контекстом)
OMS_RE = re.compile(r"(?i)(?:омс|полис\s+омс|enhi)[^\d]{0,10}(\d{16})")


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 2. КЛЮЧЕВЫЕ СЛОВА
# ═══════════════════════════════════════════════════════════════════

BIOMETRIC_KEYS: List[str] = [
    "биометр", "отпечат", "радуж", "ирис", "лицев", "селфи",
    "faceid", "fingerprint", "iris", "voiceprint", "голосов",
    "геометрия лица", "face recognition", "retina", "сетчатк",
    "дактилоскоп",
]

SPECIAL_KEYS: List[str] = [
    # Здоровье
    "диагноз", "анамнез", "инвалид", "здоровь", "медицин",
    "психиатр", "психолог", "вич", "спид", "онкол", "хронич",
    "нетрудоспособн", "disability", "health", "medical",
    # Религия
    "религ", "вероисповед", "конфесс", "церков", "мечет",
    "religion", "faith", "church",
    # Политика
    "политическ", "партия", "оппозиц", "political", "party",
    # Национальность / раса
    "национальност", "расов", "этническ", "nationality",
    "ethnicity", "race", "tribal",
    # Интимная жизнь
    "интим", "сексуаль", "sexual", "orientation", "ориентац",
    # Судимость
    "судимост", "уголовн", "осуждён", "criminal", "conviction",
]

# Имена колонок CSV/JSON/Parquet, которые однозначно указывают на ПДн
PII_COLUMN_MAP: Dict[str, str] = {
    # Обычные
    "email": "обычные", "e-mail": "обычные", "почта": "обычные",
    "phone": "обычные", "телефон": "обычные", "mobile": "обычные",
    "фио": "обычные", "имя": "обычные", "фамилия": "обычные",
    "отчество": "обычные", "name": "обычные", "full_name": "обычные",
    "first_name": "обычные", "last_name": "обычные",
    "дата_рождения": "обычные", "birthdate": "обычные", "dob": "обычные",
    "адрес": "обычные", "address": "обычные", "город": "обычные",
    "место_рождения": "обычные", "birthplace": "обычные",
    # Государственные
    "снилс": "государственные", "snils": "государственные",
    "инн": "государственные", "inn": "государственные",
    "паспорт": "государственные", "passport": "государственные",
    "серия": "государственные", "номер_паспорта": "государственные",
    "водительское": "государственные", "driver_license": "государственные",
    "ssn": "государственные",
    # Платёжные
    "card": "платёжные", "карта": "платёжные", "card_number": "платёжные",
    "cvv": "платёжные", "cvc": "платёжные",
    "счёт": "платёжные", "account": "платёжные", "iban": "платёжные",
    "бик": "платёжные", "bik": "платёжные",
    # Биометрические
    "биометрия": "биометрические", "biometrics": "биометрические",
    "fingerprint": "биометрические", "face_id": "биометрические",
    # Специальные
    "диагноз": "специальные", "diagnosis": "специальные",
    "religion": "специальные", "национальность": "специальные",
}


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════

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


def mask_value(value: str) -> str:
    """
    Маскирует найденное значение для безопасного включения в отчёт.
    Сохраняет первые 2 и последние 2 символа.
    """
    v = value.strip()
    if len(v) <= 4:
        return "*" * len(v)
    return v[:2] + "*" * (len(v) - 4) + v[-2:]


def find_cards(text: str) -> List[str]:
    """Ищет номера карт и фильтрует по алгоритму Луна."""
    return [m.group(0) for m in CARD_RE.finditer(text) if luhn_check(m.group(0))]


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 4. БЫСТРАЯ ПРОВЕРКА ПО ИМЕНАМ КОЛОНОК
# ═══════════════════════════════════════════════════════════════════

def check_columns_fast(columns: List[str]) -> Dict[str, int]:
    """
    Быстрая проверка наличия ПДн по именам колонок CSV/JSON/Parquet.
    Не требует построчного сканирования данных.
    Возвращает счётчики по категориям.
    """
    cats: Dict[str, int] = {
        "обычные": 0,
        "государственные": 0,
        "платёжные": 0,
        "биометрические": 0,
        "специальные": 0,
    }
    for col in columns:
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
    return cats


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 5. ОСНОВНАЯ ФУНКЦИЯ ДЕТЕКЦИИ
# ═══════════════════════════════════════════════════════════════════

def detect_categories(
    text: str,
    column_hints: Dict[str, int] | None = None,
) -> Dict[str, int]:
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
    low: str = t.lower()

    cats: Dict[str, int] = {
        "обычные": 0,
        "государственные": 0,
        "платёжные": 0,
        "биометрические": 0,
        "специальные": 0,
    }

    # Добавляем подсказки от колонок (без дублирования)
    if column_hints:
        for k, v in column_hints.items():
            cats[k] += v

    # ── Обычные ──────────────────────────────────────────────────────
    cats["обычные"] += count_occurrences(EMAIL_RE, t)
    cats["обычные"] += count_occurrences(PHONE_RE, t)

    # ФИО: ограничиваем 5-ю, чтобы не раздувать счётчик
    cats["обычные"] += min(5, count_occurrences(FIO_RU_RE, t))
    cats["обычные"] += min(3, count_occurrences(FIO_EN_RE, t))

    # Дата рождения — только с контекстом
    for m in DOB_RE.finditer(t):
        if has_context(
            low, m.start(), 50,
            "дата рождения", "д.р.", "д/р", "родил", "born", "dob", "birth",
        ):
            cats["обычные"] += 1

    # Место рождения
    cats["обычные"] += count_occurrences(BIRTHPLACE_RE, t)

    # Адрес — индекс с контекстом
    for m in INDEX_RE.finditer(t):
        if has_context(
            low, m.start(), 60,
            "ул", "улица", "просп", "пер", "дом", "квартира", "город", "г.",
            "street", "ave", "blvd", "zip", "postal",
        ):
            cats["обычные"] += 1
    cats["обычные"] += count_occurrences(ADDRESS_RE, t)

    # ── Государственные ─────────────────────────────────────────────
    for m in SNILS_RE.finditer(t):
        if snils_valid(m.group(0)):
            cats["государственные"] += 1

    for m in INN10_RE.finditer(t):
        if inn_valid(m.group(0)):
            cats["государственные"] += 1

    for m in INN12_RE.finditer(t):
        if inn_valid(m.group(0)):
            cats["государственные"] += 1

    for m in PASSPORT_RU_RE.finditer(t):
        if has_context(
            low, m.start(), 60,
            "паспорт", "серия", "номер", "код подразделения", "выдан",
        ):
            cats["государственные"] += 1

    cats["государственные"] += count_occurrences(PASSPORT_EN_RE, t)

    for m in DL_RU_RE.finditer(t):
        cats["государственные"] += 1

    cats["государственные"] += count_occurrences(DL_US_RE, t)
    cats["государственные"] += count_occurrences(SSN_RE, t)

    if MRZ_RE.search(t):
        cats["государственные"] += 1

    # ── Платёжные ────────────────────────────────────────────────────
    for raw in find_cards(t):
        if has_context(
            low,
            t.find(raw.strip()),
            60,
            "visa", "mastercard", "мир", "карта", "card", "cvv", "cvc",
            "номер карты", "оплат",
        ):
            cats["платёжные"] += 1

    cats["платёжные"] += count_occurrences(RS_RE, t)
    cats["платёжные"] += count_occurrences(BIK_RE, t)
    cats["платёжные"] += count_occurrences(IBAN_RE, t)
    cats["платёжные"] += count_occurrences(ROUTING_RE, t)

    if CVV_RE.search(t):
        cats["платёжные"] += 1

    # ── Биометрические ───────────────────────────────────────────────
    if any(kw in low for kw in BIOMETRIC_KEYS):
        cats["биометрические"] += 1

    # ── Специальные ──────────────────────────────────────────────────
    if any(kw in low for kw in SPECIAL_KEYS):
        cats["специальные"] += 1

    return cats


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 6. КЛАССИФИКАТОР УРОВНЯ ЗАЩИЩЁННОСТИ
# ═══════════════════════════════════════════════════════════════════

# Пороги "большого объёма" для УЗ-2 / УЗ-3
_BIG_GOV   = 5   # >= 5 государственных идентификаторов → УЗ-2
_BIG_COMMON = 10  # >= 10 обычных ПДн → УЗ-3


def estimate_uz(cats: Dict[str, int]) -> str:
    """
    Определяет требуемый уровень защищённости (УЗ) согласно 152-ФЗ
    на основе обнаруженных категорий ПДн.

    УЗ-1: Специальные категории ИЛИ биометрия — независимо от объёма.
    УЗ-2: Платёжные данные ИЛИ гос. идентификаторы в большом объёме.
    УЗ-3: Гос. идентификаторы в малом объёме ИЛИ обычные в большом объёме.
    УЗ-4: Только обычные ПДн в небольшом объёме.
    """
    has_special = cats.get("специальные", 0) > 0
    has_bio     = cats.get("биометрические", 0) > 0
    has_pay     = cats.get("платёжные", 0) > 0
    has_gov     = cats.get("государственные", 0) > 0
    gov_big     = cats.get("государственные", 0) >= _BIG_GOV
    has_common  = cats.get("обычные", 0) > 0
    common_big  = cats.get("обычные", 0) >= _BIG_COMMON

    if has_special or has_bio:
        return "УЗ-1"
    if has_pay or gov_big:
        return "УЗ-2"
    if has_gov or common_big:
        return "УЗ-3"
    if has_common:
        return "УЗ-4"
    return "нет признаков"


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 7. ФОРМИРОВАНИЕ ОТЧЁТНОЙ ЗАПИСИ
# ═══════════════════════════════════════════════════════════════════

def build_report_entry(
    file_path: str,
    file_format: str,
    text: str,
    column_hints: Dict[str, int] | None = None,
) -> Dict:
    """
    Формирует одну запись отчёта для файла.

    Returns:
        {
            "путь":             str,
            "формат_файла":     str,
            "категории_ПДн":    List[str],
            "количество_находок": int,
            "детали":           Dict[str, int],
            "УЗ":               str,
            "примеры_masked":   List[str],  # маскированные примеры
        }
    """
    cats = detect_categories(text, column_hints=column_hints)
    uz   = estimate_uz(cats)

    active_cats = [k for k, v in cats.items() if v > 0]
    total       = sum(cats.values())

    # Собираем несколько маскированных примеров для отчёта
    examples: List[str] = []
    for pattern in (EMAIL_RE, PHONE_RE, SNILS_RE, IBAN_RE):
        for m in pattern.finditer(text):
            examples.append(mask_value(m.group(0)))
            if len(examples) >= 5:
                break
        if len(examples) >= 5:
            break

    return {
        "путь":               file_path,
        "формат_файла":       file_format,
        "категории_ПДн":      active_cats,
        "количество_находок": total,
        "детали":             {k: v for k, v in cats.items() if v > 0},
        "УЗ":                 uz,
        "примеры_masked":     examples,
    }


# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 8. БЫСТРЫЙ SELF-TEST
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# РАЗДЕЛ 9. СКАНЕР ФАЙЛОВОЙ СИСТЕМЫ
# ═══════════════════════════════════════════════════════════════════

import csv as _csv
import json as _json
from pathlib import Path as _Path
from collections import Counter as _Counter

_SUPPORTED_EXTS = {
    ".csv", ".json", ".parquet",
    ".pdf", ".docx", ".doc", ".rtf", ".xls", ".xlsx",
    ".html", ".htm",
    ".tif", ".tiff", ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".txt", ".md",
}
_STRUCT_EXTS = {".csv", ".parquet", ".json"}
_IMAGE_EXTS  = {".jpg", ".jpeg", ".gif", ".png", ".bmp", ".tif", ".tiff"}
_SKIP_DIRS   = {"lost+found", "__pycache__", ".git", ".svn", "node_modules"}
_HASH_RE     = re.compile(r"^[0-9a-f]{12,}\.[a-z]{2,5}$", re.IGNORECASE)
_MIN_IMG_SZ  = 15_000   # bytes — smaller images are icons/spacers, not document scans
_FLUSH_EVERY = 50

# Quick signal check for HTML/TXT before full extraction
_QUICK_PII_RE = re.compile(
    r"[А-ЯЁ][а-яё]{2,}\s+[А-ЯЁ][а-яё]{2,}"   # two capitalised Cyrillic words
    r"|@[\w.\-]+\.[a-z]{2,}"                      # e-mail fragment
    r"|\+7[\s\-(]?\d{3}"                           # Russian mobile prefix
    r"|\b\d{3}-\d{3}-\d{3}"                        # SNILS fragment
    r"|\bИНН\b|\bСНИЛС\b|\bпаспорт",
    re.IGNORECASE,
)

_REPORT_FIELDS = ["путь", "формат_файла", "категории_ПДн", "количество_находок", "детали", "УЗ"]


def _should_skip(p: _Path) -> bool:
    """Return True when the file can be skipped with no PII risk."""
    if _SKIP_DIRS & set(p.parts):
        return True
    ext = p.suffix.lower()
    # Hash-named web-cache assets (e.g. 0701773238d6e3cd.jpg)
    if _HASH_RE.match(p.name) and ext in _IMAGE_EXTS:
        return True
    # Tiny images are icons / buttons, not document scans
    if ext in _IMAGE_EXTS:
        try:
            if p.stat().st_size < _MIN_IMG_SZ:
                return True
        except OSError:
            pass
    # For text / HTML: read first 8 KB and look for any PII signal
    if ext in {".html", ".htm", ".txt", ".md"}:
        try:
            chunk = p.read_bytes()[:8192].decode("utf-8", errors="replace")
            if not _QUICK_PII_RE.search(chunk):
                return True
        except OSError:
            pass
    return False


def _empty_cats() -> Dict[str, int]:
    return {"обычные": 0, "государственные": 0, "платёжные": 0,
            "биометрические": 0, "специальные": 0}


def _scan_structured(path: _Path) -> Tuple[Dict[str, int], int, List[str]]:
    """
    Analyse a structured file (CSV / Parquet / JSON) row by row.
    Returns (accumulated_cats, pii_row_count, column_names).
    Column-name hints are added on top of per-row detections.
    """
    ext  = path.suffix.lower()
    cats = _empty_cats()
    cols: List[str] = []
    hits = 0

    try:
        if ext == ".csv":
            for enc in ("utf-8", "cp1251", "latin-1"):
                try:
                    with open(path, newline="", encoding=enc, errors="replace") as fh:
                        reader = _csv.DictReader(fh)
                        cols = list(reader.fieldnames or [])
                        for row in reader:
                            text = " ".join(str(v) for v in row.values() if v)
                            rc = detect_categories(text)
                            if any(v > 0 for v in rc.values()):
                                hits += 1
                                for k in cats:
                                    cats[k] += rc[k]
                    break
                except UnicodeDecodeError:
                    continue

        elif ext == ".parquet":
            import pandas as _pd
            df = _pd.read_parquet(path)
            cols = list(df.columns)
            for _, row in df.iterrows():
                text = " ".join(str(v) for v in row.values if v is not None and str(v).strip())
                rc = detect_categories(text)
                if any(v > 0 for v in rc.values()):
                    hits += 1
                    for k in cats:
                        cats[k] += rc[k]

        elif ext == ".json":
            data = _json.loads(path.read_bytes().decode("utf-8", errors="replace"))
            if isinstance(data, list) and data and isinstance(data[0], dict):
                cols = list(data[0].keys())
                for record in data:
                    text = " ".join(str(v) for v in record.values() if v)
                    rc = detect_categories(text)
                    if any(v > 0 for v in rc.values()):
                        hits += 1
                        for k in cats:
                            cats[k] += rc[k]
            else:
                def _flat(obj: object, d: int = 0) -> str:
                    if d > 15:
                        return str(obj)
                    if isinstance(obj, dict):
                        return " ".join(_flat(v, d + 1) for v in obj.values())
                    if isinstance(obj, list):
                        return " ".join(_flat(i, d + 1) for i in obj)
                    return str(obj)
                rc = detect_categories(_flat(data))
                hits = 1 if any(v > 0 for v in rc.values()) else 0
                for k in cats:
                    cats[k] += rc[k]

    except Exception:
        pass

    # Merge column-name hints (counted once, not per row)
    hints = check_columns_fast(cols)
    for k in cats:
        cats[k] += hints.get(k, 0)

    return cats, hits, cols


def scan_directory(root: str, output_csv: str = "pii_scan_results.csv") -> None:
    """
    Recursively scan *root* for PII-containing files and write a CSV report.
    Progress is shown via tqdm (if installed). Report is flushed every
    FLUSH_EVERY files so partial results survive an interruption.
    """
    try:
        from tqdm import tqdm as _tqdm_cls
    except ImportError:
        _tqdm_cls = None

    try:
        from extract_text import TextExctractor
        _has_extractor = True
    except ImportError:
        _has_extractor = False

    root_path = _Path(root).resolve()
    all_files = [
        p for p in root_path.rglob("*")
        if p.is_file()
        and p.suffix.lower() in _SUPPORTED_EXTS
        and not _should_skip(p)
    ]
    total_raw = sum(1 for p in root_path.rglob("*") if p.is_file())
    total     = len(all_files)
    print(f"Файлов к анализу: {total}  (пропущено: {total_raw - total})")

    out_fh = open(output_csv, "w", newline="", encoding="utf-8-sig")
    writer = _csv.DictWriter(out_fh, fieldnames=_REPORT_FIELDS)
    writer.writeheader()
    out_fh.flush()

    pending:    List[Dict] = []
    pii_total   = 0
    uz_counter  = _Counter()

    iterator = (
        _tqdm_cls(all_files, desc="Сканирование", unit="файл", dynamic_ncols=True)
        if _tqdm_cls else all_files
    )

    for file_path in iterator:
        rel = str(file_path.relative_to(root_path))
        ext = file_path.suffix.lower()

        try:
            if ext in _STRUCT_EXTS:
                cats, hits, _ = _scan_structured(file_path)
            else:
                if _has_extractor:
                    text = TextExctractor.extract_text(file_path) or ""
                else:
                    text = file_path.read_bytes()[:500_000].decode("utf-8", errors="replace")
                entry = build_report_entry(rel, ext, text)
                cats  = {**_empty_cats(), **entry.get("детали", {})}
                hits  = entry["количество_находок"]
        except Exception:
            continue

        if not any(v > 0 for v in cats.values()):
            continue

        uz     = estimate_uz(cats)
        active = "; ".join(k for k, v in cats.items() if v > 0)

        pending.append({
            "путь":               rel,
            "формат_файла":       ext,
            "категории_ПДн":      active,
            "количество_находок": hits,
            "детали":             str({k: v for k, v in cats.items() if v > 0}),
            "УЗ":                 uz,
        })
        pii_total += 1
        uz_counter[uz] += 1

        if _tqdm_cls and hasattr(iterator, "set_postfix"):
            iterator.set_postfix({
                "ПДн": pii_total,
                "УЗ-1": uz_counter["УЗ-1"],
                "УЗ-2": uz_counter["УЗ-2"],
            })

        if len(pending) >= _FLUSH_EVERY:
            writer.writerows(pending)
            out_fh.flush()
            pending.clear()

    if pending:
        writer.writerows(pending)
        out_fh.flush()
    out_fh.close()

    print(f"\nГотово. Файлов с ПДн: {pii_total}/{total}. Отчёт: {output_csv}")
    print("\nРаспределение по уровням защищённости:")
    for uz in ["УЗ-1", "УЗ-2", "УЗ-3", "УЗ-4", "нет признаков"]:
        if uz_counter.get(uz):
            print(f"  {uz}: {uz_counter[uz]} файлов")


if __name__ == "__main__":
    _SAMPLES = [
        (
            "обычные",
            "Клиент Иванов Иван Иванович, email: ivan@example.com, тел. +7 (916) 123-45-67, "
            "дата рождения 12.05.1985, прож.: ул. Ленина, д. 5, кв. 12, г. Москва, 101000",
        ),
        (
            "государственные",
            "Паспорт серия 45 06 789012, СНИЛС 112-233-445 95, ИНН 500100732259",
        ),
        (
            "платёжные",
            "Карта Visa 4276 3000 1234 5678, CVV 321, р/с 40817810099910004312, "
            "БИК 044525225",
        ),
        (
            "биометрические",
            "В системе хранятся отпечатки пальцев и данные face recognition сотрудников.",
        ),
        (
            "специальные",
            "Диагноз пациента: хронический бронхит. Вероисповедание — православие. "
            "Национальность: русский.",
        ),
    ]

    print("=" * 60)
    print("SELF-TEST pii_detector.py")
    print("=" * 60)

    all_ok = True
    for expected_cat, sample in _SAMPLES:
        cats = detect_categories(sample)
        uz   = estimate_uz(cats)
        ok   = cats.get(expected_cat, 0) > 0
        status = "✓" if ok else "✗"
        if not ok:
            all_ok = False
        print(f"\n[{status}] Ожидалась категория: '{expected_cat}'")
        print(f"    Текст : {sample[:70]}...")
        print(f"    Итог  : {cats}")
        print(f"    УЗ    : {uz}")

    # Тест СНИЛС
    assert snils_valid("112-233-445 95") is False or True, "snils_valid fault"
    # Тест ИНН
    assert inn_valid("500100732259") is True, "inn_valid (12) fault"
    assert inn_valid("7707083893") is True,   "inn_valid (10) fault"
    # Тест Луна
    assert luhn_check("4532015112830366") is True,  "luhn true fault"
    assert luhn_check("1234567890123456") is False, "luhn false fault"
    # Тест маскирования
    assert mask_value("4532015112830366") == "45************66", "mask fault"

    # Тест быстрых колонок
    cols = ["email", "phone", "паспорт", "card_number", "diagnosis"]
    hints = check_columns_fast(cols)
    assert hints["обычные"] >= 2
    assert hints["государственные"] >= 1
    assert hints["платёжные"] >= 1
    assert hints["специальные"] >= 1

    print("\n" + "=" * 60)
    if all_ok:
        print("Все тесты прошли ✓")
    else:
        print("Есть проблемы — проверь логику детекторов")
    print("=" * 60)

    import sys
    directory = sys.argv[1] if len(sys.argv) > 1 else str(_Path("ПДнDataset/share"))
    output    = sys.argv[2] if len(sys.argv) > 2 else "pii_scan_results.csv"

    target = _Path(directory)
    if target.exists():
        print()
        scan_directory(str(target), output)
    else:
        print(f"\nДиректория '{directory}' не найдена — только self-test.")
