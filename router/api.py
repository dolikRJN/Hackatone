"""API сайта. Все приватные запросы используют Authorization: Bearer <token>."""

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import services
from database import connection
from schemas import LoginRequest, Mode, RegisterRequest, SessionResult

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)


def hash_pwd(password: str) -> str:
    # Соль делает хеши одинаковых паролей разными.
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        _, salt, expected = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    else:
        # Совместимость с аккаунтами, созданными первоначальной версией проекта.
        expected = stored
        actual = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("DELETE FROM Sessions WHERE expires_at <= ?", (int(time.time()),))
    conn.execute(
        "INSERT INTO Sessions VALUES (?, ?, ?)",
        (token_hash(token), user_id, int(time.time()) + 7 * 86400),
    )
    return token


def get_user_id(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials:
        with connection() as conn:
            row = conn.execute(
                "SELECT user_id FROM Sessions WHERE token_hash = ? AND expires_at > ?",
                (token_hash(credentials.credentials), int(time.time())),
            ).fetchone()
        if row:
            return row["user_id"]
    # Не подставляем пользователя №1 при отсутствии или ошибке токена.
    raise HTTPException(401, "Войдите в аккаунт", headers={"WWW-Authenticate": "Bearer"})


UserID = Annotated[int, Depends(get_user_id)]


@router.post("/auth/register", status_code=201)
def register(data: RegisterRequest):
    with connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO Users (email, password, nickname) VALUES (?, ?, ?)",
                (data.email, hash_pwd(data.password), data.nickname or data.email.split("@")[0]),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Email уже зарегистрирован") from exc
        user_id = cur.lastrowid
        token = create_session(conn, user_id)
    return {"status": "ok", "user_id": user_id, "token": token}


@router.post("/auth/login")
def login(data: LoginRequest):
    with connection() as conn:
        row = conn.execute("SELECT id, password FROM Users WHERE email = ?", (data.email,)).fetchone()
        if not row or not verify_password(data.password, row["password"]):
            raise HTTPException(401, "Неверный email или пароль")
        if not row["password"].startswith("pbkdf2_sha256$"):
            conn.execute("UPDATE Users SET password = ? WHERE id = ?", (hash_pwd(data.password), row["id"]))
        token = create_session(conn, row["id"])
    return {"status": "ok", "user_id": row["id"], "token": token}


@router.post("/auth/logout")
def logout(user_id: UserID, credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    with connection() as conn:
        conn.execute("DELETE FROM Sessions WHERE token_hash = ?", (token_hash(credentials.credentials),))
    return {"status": "ok"}


@router.get("/users/me")
def get_me(user_id: UserID):
    with connection() as conn:
        row = conn.execute("SELECT id, email, nickname, xp, level_id FROM Users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Пользователь не найден")
    user = dict(row)
    user["nickname"] = user["nickname"] or user["email"].split("@")[0]
    user["level_start"] = services.LEVELS[user["level_id"] - 1]["limit"]
    user["next_level_xp"] = next((level["limit"] for level in services.LEVELS if level["limit"] > user["xp"]), None)
    return user


@router.get("/exercises/generate")
def get_text(mode: Mode = "words", lang: Literal["ru", "en"] = "ru", dif: int = Query(1, ge=1, le=10)):
    return {"id": 1, "type": mode, "text": services.gen_text(mode, lang, dif)}


@router.post("/stats/submit")
def save_result(data: SessionResult, user_id: UserID):
    mode = "sentences" if data.mode == "text" else data.mode
    wpm = int(round(data.speed_wpm))
    earned_xp = services.calc_xp(wpm, data.accuracy_pct, data.max_combo)
    with connection() as conn:
        # Захватываем запись до чтения XP: параллельные отправки не потеряют прогресс.
        conn.execute("BEGIN IMMEDIATE")
        user = conn.execute("SELECT xp, level_id FROM Users WHERE id = ?", (user_id,)).fetchone()
        conn.execute(
            """INSERT INTO StatsHistory
               (user_id, speed_wpm, accuracy_pct, errors_json, mode, duration_seconds, xp_gained)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, wpm, data.accuracy_pct, json.dumps(data.errors_json, ensure_ascii=False), mode, data.duration_seconds, earned_xp),
        )
        # SQL-триггер уже пересчитал средние показатели и число тренировок.
        total = conn.execute("SELECT total_lessons_completed FROM Statistics WHERE user_id = ?", (user_id,)).fetchone()[0]
        code_total = conn.execute("SELECT COUNT(*) FROM StatsHistory WHERE user_id = ? AND mode = 'code'", (user_id,)).fetchone()[0]
        new_xp = user["xp"] + earned_xp
        new_level = services.calc_level(new_xp)
        conn.execute("UPDATE Users SET xp = ?, level_id = ? WHERE id = ?", (new_xp, new_level, user_id))
        unlocked = []
        for achievement in services.check_achieves(wpm, data.accuracy_pct, data.max_combo, total, code_total):
            cur = conn.execute(
                "INSERT OR IGNORE INTO UserUnlocks (user_id, achievement_id) VALUES (?, ?)",
                (user_id, achievement["id"]),
            )
            if cur.rowcount:
                unlocked.append(achievement)
    return {"xp_gained": earned_xp, "level_up": new_level > user["level_id"], "new_achievements": unlocked, "problem_keys": services.get_top_mistakes(data.errors_json)}


@router.get("/stats/summary")
def get_summary(user_id: UserID):
    with connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(AVG(speed_wpm), 0) AS avg_speed,
                      COALESCE(AVG(accuracy_pct), 0) AS avg_accuracy,
                      COUNT(*) AS total_lessons, COALESCE(MAX(speed_wpm), 0) AS best_wpm,
                      COALESCE(MAX(accuracy_pct), 0) AS best_accuracy,
                      COALESCE(SUM(duration_seconds), 0) AS total_seconds
               FROM StatsHistory WHERE user_id = ?""", (user_id,),
        ).fetchone()
    return dict(row)


@router.get("/stats/history")
def get_history(user_id: UserID, limit: int = Query(30, ge=1, le=500)):
    with connection() as conn:
        rows = conn.execute(
            """SELECT id, speed_wpm AS speed, accuracy_pct AS accuracy, created_at,
                      errors_json, mode, duration_seconds, xp_gained
               FROM StatsHistory WHERE user_id = ? ORDER BY id DESC LIMIT ?""", (user_id, limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["errors"] = sum(json.loads(item.pop("errors_json")).values())
        result.append(item)
    return result


@router.get("/stats/error-analysis")
def get_error_analysis(user_id: UserID):
    with connection() as conn:
        rows = [dict(row) for row in conn.execute("SELECT errors_json FROM StatsHistory WHERE user_id = ?", (user_id,))]
    return {"problem_keys": services.analyze_hist_errors(rows)}


@router.get("/stats/achievements")
def get_achievements():
    with connection() as conn:
        return [dict(row) for row in conn.execute("SELECT id, title, description FROM Achievements ORDER BY id")]


@router.get("/stats/achievements/my")
def get_my_achievements(user_id: UserID):
    with connection() as conn:
        return [dict(row) for row in conn.execute(
            """SELECT a.id, a.title, a.description, u.unlocked_at FROM UserUnlocks u
               JOIN Achievements a ON u.achievement_id = a.id WHERE u.user_id = ?""", (user_id,),
        )]


@router.get("/stats/leaderboard")
def get_leaderboard(sort_by: Literal["speed", "accuracy", "xp"] = "speed", period: Literal["day", "week", "all"] = "all"):
    # В SQL подставляются только выражения из этого словаря, не входная строка.
    order = {"speed": "wpm", "accuracy": "accuracy", "xp": "value"}[sort_by]
    since = {"day": "start of day", "week": "-7 days", "all": "-10000 years"}[period]
    with connection() as conn:
        rows = conn.execute(f"""
            SELECT u.id AS user_id, u.email, COALESCE(u.nickname, u.email) AS username,
                   u.xp, ROUND(AVG(h.speed_wpm), 1) AS wpm,
                   ROUND(AVG(h.accuracy_pct), 2) AS accuracy,
                   {'u.xp' if period == 'all' else 'SUM(h.xp_gained)'} AS value
            FROM Users u JOIN StatsHistory h ON h.user_id = u.id
            WHERE (? = 'all' OR h.created_at >= datetime('now', ?))
            GROUP BY u.id ORDER BY {order} DESC, u.id LIMIT 20
        """, (period, since)).fetchall()
    return [dict(row, rank=index) for index, row in enumerate(rows, 1)]
