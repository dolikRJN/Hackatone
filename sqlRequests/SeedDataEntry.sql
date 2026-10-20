INSERT OR IGNORE INTO Levels (id, title, xp_limit) VALUES
(1, 'Новичок', 0),
(2, 'Ученик', 200),
(3, 'Любитель', 600),
(4, 'Профи', 1500),
(5, 'Мастер', 3000);

INSERT OR IGNORE INTO Achievements (id, title, description, unlock_condition_json) VALUES
(1, 'Первый шаг', 'Завершите вашу самую первую тренировку', '{"metric": "total_lessons", "operator": ">=", "value": 1}'),
(2, 'Снайпер', 'Пройдите упражнение со 100% точностью', '{"metric": "accuracy_pct", "operator": "==", "value": 100}'),
(3, 'Печатный гений', 'Разгонитесь выше 300 WPM (слов в минуту)', '{"metric": "speed_wpm", "operator": ">=", "value": 300}'),
(5, 'Стальной палец', 'Ни разу не промахнитесь за 1000 нажатий подряд', '{"metric": "max_combo", "operator": ">=", "value": 1000}'),
(4, 'Ветеран кода', 'Успешно завершите 50 тренировок в режиме "Code"', '{"metric": "code_lessons", "operator": ">=", "value": 50}');
