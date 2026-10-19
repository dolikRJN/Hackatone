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

def check_acheves(wpm, streak):
    """Получение ачивок"""
    unlocked = []
    if wpm >= 300:
        unlocked.append("Печатный гений")
    if streak >= 1000:
        unlocked.append("Стальной палец")
    return unlocked

def get_top_mistakes(mistakes_dict):
    """Поиск топ-3 частых ошибок пользователя"""
    if not mistakes_dict:
        return []
    
    sorted_mist = sorted(mistakes_dict, key=mistakes_dict.get, reverse=True)

    return sorted_mist[:3]
