import json
import random
from pathlib import Path

with (Path(__file__).resolve().parent / "data.json").open(encoding="utf-8") as f:
    DATA = json.load(f)

LEVELS = [
    {"id": 1, "title": "Новичок", "limit": 0},
    {"id": 2, "title": "Ученик", "limit": 200},
    {"id": 3, "title": "Любитель", "limit": 600},
    {"id": 4, "title": "Профи", "limit": 1500},
    {"id": 5, "title": "Мастер", "limit": 3000},
]

ACHIEVES = [
    {"id": 1, "title": "Первый шаг", "description": "Завершить первую тренировку"},
    {"id": 2, "title": "Снайпер", "description": "Пройти упражнение со 100% точностью"},
    {"id": 3, "title": "Печатный гений", "description": "Набрать скорость 300 слов/мин"},
    {"id": 4, "title": "Ветеран кода", "description": "Завершить 50 тренировок с кодом"},
    {"id": 5, "title": "Стальной палец", "description": "1000 правильных нажатий подряд"},
]


def gen_text(mode="words", lang="ru", dif=1):
    """Генерация текста из данных."""
    if lang not in ("ru", "en") or not 1 <= dif <= 10:
        raise ValueError("Язык должен быть ru/en, сложность — от 1 до 10")
    match mode:
        case "words":
            words = DATA["words"][lang]
            count = 15 * dif
            text = " ".join(random.sample(words, count))
        case "text" | "sentences":
            sents = DATA["sentences"][lang]
            text = " ".join(random.sample(sents, dif))
        case "code":
            text = random.choice(DATA["code"])
        case "symbols":
            chars = "!@#$%^&*()_+-=[]{};:0123456789"
            batches = ["".join(random.choices(chars, k=4)) for _ in range(10)]
            text = " ".join(batches)
        case _:
            raise ValueError(f"Неизвестный режим {mode}")
    return text


def calc_xp(wpm, acc, max_combo):
    """Опыт и множитель комбо"""
    base_xp = wpm * (acc / 100.00)
    mp = 1.0

    if max_combo >= 50:
        mp = 5.0
    elif max_combo >= 20:
        mp = 3.0
    elif max_combo >= 10:
        mp = 2.0

    return int(base_xp * mp)


def calc_level(total_xp):
    """id уровня по количеству опыта"""
    current_level = 1
    for lvl in LEVELS:
        if total_xp >= lvl["limit"]:
            current_level = lvl["id"]
    return current_level


def check_achieves(wpm, accuracy, streak, total_lessons, code_lessons=0):
    """Условия и ID совпадают с каталогом достижений в SQLite."""
    unlocked = []
    if total_lessons >= 1:
        unlocked.append(ACHIEVES[0])
    if accuracy == 100:
        unlocked.append(ACHIEVES[1])
    if wpm >= 300:
        unlocked.append(ACHIEVES[2])
    if code_lessons >= 50:
        unlocked.append(ACHIEVES[3])
    if streak >= 1000:
        unlocked.append(ACHIEVES[4])
    return unlocked

def get_top_mistakes(mistakes_dict, top_n=5):
    """Поиск топ частых ошибок пользователя"""
    if not mistakes_dict:
        return []
    
    sorted_mist = sorted(mistakes_dict, key=mistakes_dict.get, reverse=True)

    return sorted_mist[:top_n]

def analyze_hist_errors(hist_list):
    """Все ошибки пользователя и топ-5 сложнейших букв"""
    total_mistakes = {}
    for session in hist_list:
        errs = session.get("errors_json", {})
        if isinstance(errs, str):
            try:
                errors = json.loads(errs)
            except (json.JSONDecodeError, TypeError):
                errors = {}
        else:
            errors = errs
        for char, count in errors.items():
            total_mistakes[char] = total_mistakes.get(char, 0) + count

    return get_top_mistakes(total_mistakes, top_n=5)
