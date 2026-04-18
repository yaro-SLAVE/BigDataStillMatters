from dataclasses import dataclass
from enum import StrEnum

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