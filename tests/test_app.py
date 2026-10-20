"""Проверка сайта и API на временной БД: python -m unittest discover -s tests -v."""

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import database
from router.server import app


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "test.db"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        database.DB_PATH = self.original_path
        self.temp.cleanup()

    def register(self, email="tester@example.com"):
        result = self.client.post("/api/v1/auth/register", json={
            "email": email, "password": "secret123", "nickname": "Tester",
        })
        self.assertEqual(result.status_code, 201, result.text)
        return {"Authorization": "Bearer " + result.json()["token"]}

    def submit(self, headers, **overrides):
        payload = {"speed_wpm": 60, "accuracy_pct": 98, "max_combo": 20,
                   "errors_json": {"a": 2}, "duration_seconds": 30, "mode": "words"}
        payload.update(overrides)
        response = self.client.post("/api/v1/stats/submit", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_pages_assets_and_openapi(self):
        for path in ("/", "/auth", "/game", "/profile", "/leaderboard",
                     "/static/css/style.css", "/static/js/auth.js",
                     "/static/js/game.js", "/static/js/profile.js", "/static/js/leaderboard.js",
                     "/static/img/avatar.svg", "/docs"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn("text/html", self.client.get("/").headers["content-type"])
        self.assertIn("/api/v1/auth/register", self.client.get("/openapi.json").json()["paths"])
        self.assertEqual(self.client.get("/database.py").status_code, 404)

    def test_legacy_page_redirects_and_clean_links(self):
        for old, new in (("index", "/"), ("game", "/game"), ("profile", "/profile"),
                         ("leaderboard", "/leaderboard"), ("auth", "/auth")):
            with self.subTest(page=old):
                response = self.client.get(f"/{old}.html?mode=register&next=%2Fprofile", follow_redirects=False)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers["location"], new + "?mode=register&next=%2Fprofile")
                page = self.client.get(new)
                self.assertEqual(page.status_code, 200)
                for filename in ("index", "game", "profile", "leaderboard", "auth"):
                    self.assertNotIn(filename + '.html"', page.text)
                    self.assertNotIn(filename + '.html?', page.text)
        self.assertEqual(self.client.get("/missing.html").status_code, 404)
        self.assertEqual(self.client.get("/template/game.html").status_code, 404)
        self.assertEqual(self.client.get("/game/").url.path, "/game")

    def test_authentication_and_logout(self):
        headers = self.register()
        self.assertEqual(self.client.get("/api/v1/users/me").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/users/me", headers={"Authorization": "Bearer test"}).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/users/me", headers=headers).json()["nickname"], "Tester")
        self.assertEqual(self.client.post("/api/v1/auth/login", json={"email": "tester@example.com", "password": "bad"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/register", json={"email": "tester@example.com", "password": "secret123"}).status_code, 409)
        login = self.client.post("/api/v1/auth/login", json={"email": " TESTER@example.com ", "password": "secret123"})
        self.assertEqual(login.status_code, 200)
        self.client.post("/api/v1/auth/logout", headers=headers)
        self.assertEqual(self.client.get("/api/v1/users/me", headers=headers).status_code, 401)

    def test_training_progress_and_isolation(self):
        headers = self.register()
        first = self.submit(headers)
        self.assertEqual([item["id"] for item in first["new_achievements"]], [1])
        self.assertEqual(first["xp_gained"], 176)
        self.assertEqual(self.submit(headers)["new_achievements"], [])
        summary = self.client.get("/api/v1/stats/summary", headers=headers).json()
        self.assertEqual((summary["total_lessons"], summary["total_seconds"]), (2, 60))
        self.assertEqual(self.client.get("/api/v1/stats/history", headers=headers).json()[0]["errors"], 2)
        self.assertEqual(self.client.get("/api/v1/stats/error-analysis", headers=headers).json()["problem_keys"], ["a"])
        self.assertEqual(self.client.get("/api/v1/users/me", headers=headers).json()["level_id"], 2)
        other = self.register("other@example.com")
        self.assertEqual(self.client.get("/api/v1/stats/history", headers=other).json(), [])
        # Повторный запуск миграций сохраняет результаты и действующую сессию.
        database.init_db()
        self.assertEqual(self.client.get("/api/v1/stats/summary", headers=headers).json()["total_lessons"], 2)

    def test_achievements_match_database(self):
        headers = self.register()
        result = self.submit(headers, speed_wpm=300, accuracy_pct=100, max_combo=1000, errors_json={})
        self.assertEqual({item["id"] for item in result["new_achievements"]}, {1, 2, 3, 5})
        unlocked = self.client.get("/api/v1/stats/achievements/my", headers=headers).json()
        self.assertEqual({item["title"] for item in unlocked}, {"Первый шаг", "Снайпер", "Печатный гений", "Стальной палец"})

    def test_modes_and_validation(self):
        for mode in ("words", "sentences", "text", "code", "symbols"):
            for lang in ("ru", "en"):
                result = self.client.get("/api/v1/exercises/generate", params={"mode": mode, "lang": lang, "dif": 10})
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json()["text"])
        for params in ({"mode": "bad"}, {"lang": "bad"}, {"dif": 0}, {"dif": 999}):
            self.assertEqual(self.client.get("/api/v1/exercises/generate", params=params).status_code, 422)
        headers = self.register()
        self.assertEqual(self.client.post("/api/v1/stats/submit", headers=headers, json={"speed_wpm": -1, "accuracy_pct": 110}).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/stats/history?limit=-1", headers=headers).status_code, 422)

    def test_leaderboard_periods(self):
        headers = self.register()
        self.submit(headers)
        for metric in ("speed", "accuracy", "xp"):
            self.assertEqual(len(self.client.get(f"/api/v1/stats/leaderboard?sort_by={metric}&period=all").json()), 1)
        with database.connection() as conn:
            conn.execute("UPDATE StatsHistory SET created_at = datetime('now', '-10 days')")
        self.assertEqual(self.client.get("/api/v1/stats/leaderboard?period=week").json(), [])
        self.assertEqual(len(self.client.get("/api/v1/stats/leaderboard?period=all").json()), 1)

    def test_migration_of_original_database(self):
        # Старые таблицы не содержат nickname/mode; пользователь и пароль сохраняются.
        old_path = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / "legacy.db"
        try:
            conn = sqlite3.connect(database.DB_PATH)
            for filename in ("TableCreate.sql", "TriggerCreate.sql", "SeedDataEntry.sql"):
                conn.executescript((database.BASE_DIR / "sqlRequests" / filename).read_text(encoding="utf-8"))
            conn.execute("INSERT INTO Users (email, password) VALUES (?, ?)",
                         ("legacy@example.com", hashlib.sha256(b"secret123").hexdigest()))
            conn.commit()
            conn.close()
            database.init_db()
            result = self.client.post("/api/v1/auth/login", json={"email": "legacy@example.com", "password": "secret123"})
            self.assertEqual(result.status_code, 200, result.text)
        finally:
            database.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
