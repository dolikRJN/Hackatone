import json, ollama, time

def request_to_LLM(prompt):
    """Отправка запроса на генерацию данных через локальную LLM"""
    response = ollama.chat(
        model="qwen3_5:latest",
        messages=[
            {"role": "system", "content": 'Ты - генератор тренировочных наборов данных для практики печати. Твоя задача создать набор данных в формате JSON-списка, без markdown. Формат вывода: ["etc1", "etc2", "etc3"]'},
            {"role": "user", "content": prompt}
        ],
        think=False,
        options={"temperature": 0.3, "num_ctx": 2048}
    )
    try:
        raw_text = response['message']['content'].strip()
        return json.loads(raw_text)
    except:
        return []

def gen_words(lang, count=500, batch_size=50):
    """Генерация слов по 50 штук за раз"""
    words_set = set()
    max_attempts = (count // batch_size) * 10
    attempts = 0

    while len(words_set) < count and attempts < max_attempts:
        prompt = f'Сгенерируй {batch_size} реальных разнообразных слов на языке "{lang}" '
        words_set.update(request_to_LLM(prompt))
        attempts += 1

        print(f"Батч {attempts} завершён")

    print(f'Генерация {count} слов на языке "{lang}" завершена!')
    return list(words_set)[:count]


def gen_sentences(lang, count=50, batch_size=10):
    """Генерация предложений по 10 штук за раз"""
    sentences_set = set()
    max_attempts = (count // batch_size) * 3
    attempts = 0

    while len(sentences_set) < count and attempts < max_attempts:
        prompt = f'Сгенерируй {batch_size} реальных осмысленных предложений разной длины на языке "{lang}", но не больше 20 слов.'
        sentences_set.update(request_to_LLM(prompt))
        attempts += 1

        print(f"Батч {attempts} завершён")

    print(f'Генерация {count} предложений на языке "{lang}" завершена!')
    return list(sentences_set)[:count]

def gen_code(count=50, batch_size=10):
    """Генерация примеров кода по 10 штук за раз"""
    code_set = set()
    max_attempts = (count // batch_size) * 3
    attempts = 0

    while len(code_set) < count and attempts < max_attempts:
        prompt = f'Сгенерируй {batch_size} реальных коротких кусков кода (5-10 строк) на Python или JS.'
        code_set.update(request_to_LLM(prompt))
        attempts += 1

        print(f"Батч {attempts} завершён")

    print(f'Генерация {count} кусков кода завершена!')
    return list(code_set)[:count]

def main():
    words_ru = gen_words("ru")
    words_en = gen_words("en")

    sentences_ru = gen_sentences("ru")
    sentences_en = gen_sentences("en")

    code_snippets = gen_code()

    raw_data = {
        "words": {
            "ru": words_ru,
            "en": words_en
        },
        "sentences": {
            "ru": sentences_ru,
            "en": sentences_en
        },
        "code": code_snippets
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=4)
    
    print("Данные записаны в файл data.json.")

if __name__ == "__main__":
    main()