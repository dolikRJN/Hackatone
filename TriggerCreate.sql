CREATE TRIGGER IF NOT EXISTS after_user_registration
AFTER INSERT ON Users
BEGIN
	INSERT INTO Statistics (user_id, speed_wpm, accuracy_pct, total_lessons_completed)
	VALUES (NEW.id, 0, 0.0, 0);
END;

CREATE TRIGGER IF NOT EXISTS update_user_statistics_on_new_session
AFTER INSERT ON StatsHistory
BEGIN
	UPDATE Statistics
	SET
		total_lessons_completed = total_lessons_completed + 1,
		speed_wpm = (
			SELECT CAST(AVG(speed_wpm) AS INTEGER)
			FROM StatsHistory
			WHERE user_id = NEW.user_id
		),
		accuracy_pct = (
			SELECT ROUND(AVG(accuracy_pct), 2)
			FROM StatsHistory
			WHERE user_id = NEW.user_id
		)
	WHERE user_id = NEW.user_id;
END;