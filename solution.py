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

def analyze_file(path_to_file: str) -> Context:
    text = TextExctractor.extract_text(path_to_file)
    print(text)
    return []

# Удалишь потом
def scan_root(root: Path) -> List[Dict[str, object]]:
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            p = Path(dirpath) / name
            ext = p.suffix.lower().lstrip('.')
            if ext not in INCLUDE_EXTS:
                continue
            try:
                res = analyze_file(p)
            except Exception as e:
                pass
            print(name)

if __name__ == "__main__":
    if ROOT_DIR.exists():
        #TODO
        scan_root(ROOT_DIR)
        # pass
    else:
        print("Укажите корректный ROOT_DIR (существующая директория).")
