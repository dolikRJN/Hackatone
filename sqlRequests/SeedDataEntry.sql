INSERT OR IGNORE INTO Levels (id, title, xp_limit) VALUES
(1, 'Джуниор клавиатуры', 0),
(2, 'Уверенный практик', 500),
(3, 'Адепт тайпинга', 1500),
(4, 'Кибер-рейсер', 4000),
(5, 'Слепой мудрец', 10000);

INSERT OR IGNORE INTO Achievements (id, title, description, unlock_condition_json) VALUES
(1, 'Первый шаг', 'Завершите вашу самую первую тренировку', '{"metric": "total_lessons", "operator": ">=", "value": 1}'),
(2, 'Снайпер', 'Пройдите упражнение со 100% точностью', '{"metric": "accuracy_pct", "operator": "==", "value": 100}'),
(3, 'Гонщик Спиди', 'Разгонитесь выше 70 WPM (слов в минуту)', '{"metric": "speed_wpm", "operator": ">=", "value": 70}'),
(4, 'Ветеран кода', 'Успешно завершите 50 тренировок в режиме "Code"', '{"metric": "code_lessons", "operator": ">=", "value": 50}');