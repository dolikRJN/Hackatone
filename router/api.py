from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uuid, json, sqlite3, hashlib

import services
from schemas import RegisterRequest, LoginRequest, SessionResult

app = FastAPI(title="Тренажёр слепой печати")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

DB_PATH = "SQLiteDB.db"
TOKENS = {"test": 1}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_pwd(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_user_id(auth: str = Header(default=None)):
    if not auth:
        return 1
    token = auth.replace("Bearer ", "").strip()
    return TOKENS.get(token, 1)


@app.post("/api/v1/auth/register")
def register(data: RegisterRequest):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO Users (email, password, xp, level_id) VALUES (?, ?, 0, 1)", (data.email, hash_pwd(data.password))
        )
        user_id = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    conn.close()
    return {"status": "ok", "user_id": user_id}


@app.post("/api/v1/auth/login")
def login(data: LoginRequest):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM Users WHERE email = ? AND password = ?", (data.email, hash_pwd(data.password))
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    token = str(uuid.uuid4())
    TOKENS[token] = row["id"]
    return {"status": "ok", "token": token, "user_id": row["id"]}


@app.get("/api/v1/users/me")
def get_me(auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, email, xp, level_id FROM Users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return dict(user)


@app.get("/api/v1/exercises/generate")
def get_text(mode: str = "words", lang: str = "ru", dif: int = 1):
    text = services.gen_text(mode=mode, lang=lang, dif=dif)
    return {"id": 1, "type": mode, "text": text}


@app.post("/api/v1/stats/submit")
def save_result(data: SessionResult, auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT xp, level_id FROM Users WHERE id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    wpm = max(0, int(round(data.speed_wpm)))
    acc = max(0.0, min(100.0, float(data.accuracy_pct)))
    errors = json.dumps(data.errors_json, ensure_ascii=False)


    cur.execute("INSERT INTO StatsHistory (user_id, speed_wpm, accuracy_pct, errors_json) VALUES (?, ?, ?, ?)", (user_id, wpm, acc, errors))
    
    earned_xp = services.calc_xp(wpm, acc, data.max_combo)
    new_xp = user["xp"] + earned_xp
    new_level = services.calc_level(new_xp)
    level_up = new_level > user["level_id"]

    cur.execute("UPDATE Users SET xp = ?, level_id = ? WHERE id = ?", (new_xp, new_level, user_id))

    cur.execute("SELECT total_lessons_completed FROM Statistics WHERE user_id = ?", (user_id,))
    stats_row = cur.fetchone()
    if stats_row is None:
        total_lessons = 0
    else:
        total_lessons = stats_row["total_lessons_completed"]

    candidate_achieves = services.check_achieves(wpm, acc, total_lessons)
    new_achievements = []

    for ach in candidate_achieves:
        cur.execute(
            "SELECT id FROM UserUnlocks WHERE user_id = ? AND achievement_id = ?",
            (user_id, ach["id"])
        )
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO UserUnlocks (user_id, achievement_id) VALUES (?, ?)",
                (user_id, ach["id"])
            )
            new_achievements.append(ach)
    conn.commit()
    conn.close()

    problem_keys = services.get_top_mistakes(data.errors_json)

    return {
        "xp_gained": earned_xp,
        "level_up": level_up,
        "new_achievements": new_achievements,
        "problem_keys": problem_keys,
    }


@app.get("/api/v1/stats/summary")
def get_summary(auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT speed_wpm AS avg_speed, accuracy_pct AS avg_accuracy, total_lessons_completed AS total_lessons FROM Statistics WHERE user_id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return {"avg_speed": 0, "avg_accuracy": 0.0, "total_lessons": 0}

    return dict(row)


@app.get("/api/v1/stats/history")
def get_history(limit: int = 30, auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT speed_wpm AS speed, accuracy_pct AS accuracy, created_at FROM StatsHistory WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/v1/stats/error-analysis")
def get_error_analysis(auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT errors_json FROM StatsHistory WHERE user_id = ?", (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    problem_keys = services.analyze_hist_errors(rows)
    return {"problem_keys": problem_keys}


@app.get("/api/v1/stats/achievements")
def get_achievements():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, description FROM Achievements")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/v1/stats/achievements/my")
def get_my_achievements(auth: str = Header(default=None)):
    user_id = get_user_id(auth)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.title, a.description, u.unlocked_at
        FROM UserUnlocks u
        JOIN Achievements a ON u.achievement_id = a.id
        WHERE u.user_id = ?
    """, (user_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/v1/stats/leaderboard")
def get_leaderboard(sort_by: str = "speed", period: str = "week"):
    conn = get_conn()
    cur = conn.cursor()

    if sort_by == "xp":
        order_col = "u.xp"
    elif sort_by == "accuracy":
        order_col = "s.accuracy_pct"
    else:
        order_col = "s.speed_wpm"

    cur.execute(f"""
        SELECT u.email, u.xp, s.speed_wpm AS wpm, s.accuracy_pct AS accuracy, {order_col} AS value
        FROM Users u
        JOIN Statistics s ON u.id = s.user_id
        ORDER BY {order_col} DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for idx, r in enumerate(rows):
        item = dict(r)
        item["rank"] = idx + 1
        item["username"] = item["email"]
        result.append(item)

    return result


@app.get("/")
def root():
    return {"message": "API работает. Документация: /docs"}