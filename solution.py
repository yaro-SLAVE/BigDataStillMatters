from dataclasses import dataclass
from enum import StrEnum
import os
import json
import csv
from pathlib import Path
from extract_text import TextExctractor
from detectors import detect_categories

class CommonCategory(StrEnum):
    NAME = "ФИО"
    PHONE = "телефон"
    EMAIL = "email"
    DATE = "дата"
    ADDRESS = "адрес"

class GovernmentCategory(StrEnum):
    PASSPORT = "паспортные данные"
    SNILS = "СНИЛС"
    INN = "ИНН"
    DRIVER = "водительское удостоверение"
    MRZ = "MRZ"

class PaymentCategory(StrEnum):
    CARD = "номера банковских кард"
    BANK_NUMBER = "банковские счета и БИК"
    CVV= "CVV"

class BiometricCategory(StrEnum):
    FINGERPRINT = "отпечатки пальцев"
    IRIS = "радужная оболочка глаза"
    VOICE = "голосовые образцы"
    FACE = "лицо"
    DNA = "ДНК"

class SpecialCategory(StrEnum):
    HEALTH = "данные о состоянии здоровья"
    BELIEFS = "религиозные и политические убеждения"
    RACE = "расовая и национальная принадлежность"
    INTIMATE = "интимная жизнь"

Category = CommonCategory | GovernmentCategory | PaymentCategory | BiometricCategory | SpecialCategory
CategoryType = type[CommonCategory] | type[GovernmentCategory] | type[PaymentCategory] | type[BiometricCategory] | type[SpecialCategory]

ROOT_DIR = Path('ПДнDataset/share')
OUTPUT_CSV = Path('results.csv')
INCLUDE_EXTS = {'mp4', 'jpg', 'html', 'parquet', 'doc', 'tif', 'pdf', 'docx', 'xls', 'md', 'json', 'txt', 'csv', 'rtf', 'gif', 'png'}
#{'mp4', 'jpg', 'html', 'parquet', 'doc', 'tif', 'pdf', 'docx', 'xls', 'md', 'json', 'txt', 'csv', 'rtf', 'gif', 'png'}

def analyze_file(path_to_file: Path) -> list[Category]:
    text = TextExctractor.extract_text(path_to_file)
    print(text)
    return []

class Level(StrEnum):
    UZ1 = "УЗ-1"
    UZ2 = "УЗ-2"
    UZ3 = "УЗ-3"
    UZ4 = "УЗ-4"
    NONE = "нет уровня"

@dataclass
class RuleCategory:
    category: Category | CategoryType
    min_amount: int

@dataclass
class Rule:
    categories: list[RuleCategory]
    level: Level
    recommendation: str

THRESHOLD = 10  # Граница "большого объема"

RULES: list[Rule] = [
    # --- УЗ-1: Специальные категории или Биометрия ---
    # По картинке: наличие таких категорий — это высокий риск (УЗ-1)
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, 1), RuleCategory(SpecialCategory, 1)],
        level=Level.UZ1,
        recommendation="Обнаружены специальные категории ПДн (здоровье, взгляды и пр.). Требуется защита уровня УЗ-1: шифрование, строгий контроль доступа и аудит."
    ),
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, 1), RuleCategory(BiometricCategory, 1)],
        level=Level.UZ1,
        recommendation="Обнаружена биометрия. Требуется УЗ-1. Необходимо обеспечить защиту от несанкционированного доступа к биометрическим шаблонам."
    ),

    # --- УЗ-2: Платежная информация или Госы в БОЛЬШИХ объемах ---
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, THRESHOLD), RuleCategory(PaymentCategory, THRESHOLD)],
        level=Level.UZ2,
        recommendation=f"Платежная информация в объеме более {THRESHOLD} субъектов. Требуется УЗ-2: использование DLP-систем и сегментация сети."
    ),
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, THRESHOLD), RuleCategory(GovernmentCategory, THRESHOLD)],
        level=Level.UZ2,
        recommendation=f"Гос. идентификаторы в большом объеме (>{THRESHOLD}). Требуется УЗ-2: усиленная защита учетных записей администраторов."
    ),
    Rule(
        categories=[RuleCategory(BiometricCategory, THRESHOLD)],
        level=Level.UZ2,
        recommendation=f"Массовый сбор биометрических шаблонов (>{THRESHOLD}). Требуется защита уровня УЗ-2."
    ),
    Rule(
        categories=[
            RuleCategory(CommonCategory.NAME, 1), 
            RuleCategory(GovernmentCategory, 1), 
            RuleCategory(PaymentCategory, 1)
        ],
        level=Level.UZ2,
        recommendation="Полный профиль (ФИО + Паспорт + Банк). Высочайший риск кражи личности. Уровень УЗ-2."
    ),

    # --- УЗ-3: Госы в МАЛЫХ объемах или Обычные в БОЛЬШИХ объемах ---
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, 1), RuleCategory(GovernmentCategory, 1)],
        level=Level.UZ3,
        recommendation="Наличие государственных идентификаторов (паспорт, СНИЛС, ИНН). Требуется УЗ-3: базовые технические меры и ограничение круга лиц."
    ),
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, THRESHOLD), RuleCategory(CommonCategory, THRESHOLD)],
        level=Level.UZ3,
        recommendation=f"Массовая обработка обычных ПДн (>{THRESHOLD}). Требуется УЗ-3: регистрация событий безопасности в системе."
    ),
    Rule(
        categories=[RuleCategory(CommonCategory.PHONE, 1), RuleCategory(GovernmentCategory, 1)],
        level=Level.UZ3,
        recommendation="Связка Телефон + Гос. идентификатор позволяет установить личность. Уровень УЗ-3."
    ),
    Rule(
        categories=[RuleCategory(CommonCategory.EMAIL, 1), RuleCategory(PaymentCategory, 1)],
        level=Level.UZ3,
        recommendation="Связка Email + Платежные данные. Высокий риск мошенничества, требуется УЗ-3."
    ),

    # --- УЗ-4: Обычные ПДн в МАЛЫХ объемах ---
    Rule(
        categories=[RuleCategory(CommonCategory.NAME, 1), RuleCategory(CommonCategory, 1)],
        level=Level.UZ4,
        recommendation="Минимальный набор обычных ПДн. Базовый уровень УЗ-4: антивирусная защита и парольная политика."
    ),
    Rule(
        categories=[
            RuleCategory(CommonCategory.NAME, 1), 
            RuleCategory(CommonCategory.PHONE, 1),
            RuleCategory(CommonCategory.ADDRESS, 1),
            RuleCategory(CommonCategory.DATE, 1)
        ],
        level=Level.UZ4,
        recommendation="Развернутый набор обычных ПДн. Базовый уровень защиты УЗ-4."
    ),

    # --- Дополнительно: Обработка без ФИО (по желанию) ---
    Rule(
        categories=[RuleCategory(PaymentCategory, 1)],
        level=Level.NONE,
        recommendation="Финансовые данные без ФИО не являются ПДн, но требуют защиты согласно PCI DSS."
    )
]

def solve_categories(categories: list[Category]) -> Rule:
    counted_categories: dict[Category | CategoryType, int] = {}
    for category in categories:
        if category in counted_categories:
            counted_categories[category] += 1
        else:
            counted_categories[category] = 1
        if type(category) in counted_categories:
            counted_categories[type(category)] += 1
        else:
            counted_categories[type(category)] = 1

    for rule in RULES:
        rule_applies = True
        for rule_category in rule.categories:
            rule_applies &= rule_category.category in counted_categories and counted_categories[rule_category.category] >= rule_category.min_amount
        if rule_applies:
            return rule

    return Rule(
        categories=[],
        level=Level.NONE,
        recommendation="Персональные данные не найдены."
    )

def save_csv(results: list[dict[str, object]], out_csv: Path):
    # убираем uz none и сортируем
    results = [x for x in results if x["uz"] != str(Level.NONE)]
    results.sort(key=lambda x: str(x["uz"]))

    out_csv = Path(out_csv)
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['path','categories','uz','total_hits','ext','recommendation'])
        for r in results:
            w.writerow([r['path'], json.dumps(r['categories'], ensure_ascii=False), r['uz'], r.get('total_hits',0), r.get('ext','')])
    return out_csv

if __name__ == "__main__":
    total_results: list[dict[str, object]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        for name in filenames:
            p = Path(dirpath) / name
            ext = p.suffix.lower().lstrip('.')
            if ext not in INCLUDE_EXTS:
                continue
            try:
                categories = analyze_file(p)
                rule = solve_categories(categories)
                res = {
                    'path': str(p),
                    'categories': categories,
                    'uz': str(rule.level),
                    'total_hits': len(categories),
                    'ext': ext,
                    'recommendation': rule.recommendation
                }
                total_results.append(res)
            except Exception as e:
                total_results.append({'path': str(p), 'categories': {}, 'uz': 'error', 'error': str(e), 'ext': ext})
            print(f"{name} {len(total_results)} {total_results[-1]["uz"]}")
    save_csv(total_results, OUTPUT_CSV)
