from dataclasses import dataclass
from enum import StrEnum
# from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List
from extract_text import TextExctractor

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

# Контекст - отдельный файл или строка в csv. Для csv хинты общие для всех строк
@dataclass
class Context:
    found_categories: list[Category]
    found_category_hints: list[Category]

ROOT_DIR = Path('../ПДнDataset/share')
OUTPUT_CSV = Path('results.csv')
INCLUDE_EXTS = {'mp4', 'jpg', 'html', 'parquet', 'doc', 'tif', 'pdf', 'docx', 'xls', 'md', 'json', 'txt', 'csv', 'rtf', 'gif', 'png'}
#{'mp4', 'jpg', 'html', 'parquet', 'doc', 'tif', 'pdf', 'docx', 'xls', 'md', 'json', 'txt', 'csv', 'rtf', 'gif', 'png'}

def analyze_file(path_to_file: Path) -> Context:
    text = TextExctractor.extract_text(path_to_file)
    print(text)
    return Context([], [])

# class Level(StrEnum):
#     UZ1 = "УЗ-1"
#     UZ2 = "УЗ-2"
#     UZ3 = "УЗ-3"
#     UZ4 = "УЗ-4"

# @dataclass
# class RuleCategory:
#     category: Category
#     min_amount: int
#     hint: bool = False

# @dataclass
# class Rule:
#     categories: list[RuleCategory]
#     level: Level

# RULES = [
#     {
#         CommonCategory.NAME, SpecialCategory.HEALTH
#     }
# ]

if __name__ == "__main__":
    results = {}
    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        for name in filenames:
            p = Path(dirpath) / name
            ext = p.suffix.lower().lstrip('.')
            if ext not in INCLUDE_EXTS:
                continue
            try:
                context = analyze_file(p)
            except Exception as e:
                pass
            print(name)
