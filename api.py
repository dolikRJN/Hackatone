from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
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
TOKENS = {"test", 1}

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_pwd(password):
    return hashlib.sha256(password.sncode("utf-8")).hexdigest()

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
            "INSERT INTO Users (email, password, xp, level_id) VALUES (?, ?, 0, 1)"
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
    row = cur.fetchone
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
    user = cur.fetchone
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return dict(user)


@app.get("/api/v1/exercises/generate")
def get_text(mode: str = "words", lang: str = "ru", dif: int = 1):
    text = services.gen_text(mode=mode, lang=lang, dif=dif)
    return {"id": 1, "type": mode, "text": text}

#ДАЛЬШЕ НЕ ИСПРАВЛЕНО
@app.post("/api/v1/stats/submit")
def save_result(data: SessionResult):
    earned_xp = services.calc_xp(data.wpm, data.accuracy, data.max_combo)
    achievements = services.check_acheves(data.wpm, data.max_combo)
    problem_keys = services.get_top_mistakes(data.errors)

    return {
        "xp_gained": earned_xp,
        "level_up": level_up,
        "new_achievements": achievements,
        "problem_keys": problem_keys,
    }

@app.get("/api/v1/stats/summary")

@app.get("/api/v1/stats/leaderboard")
def get_leaderboard():
    return [
        {"username": "test", "wpm": 345, "accuracy": 99.1, "xp": 6767},
    ]

@app.get("/api/v1/stats/history")

@app.get("/api/v1/stats/error-analysis")

@app.get("/api/v1/stats/achievements")

@app.get("/api/v1/stats/achievements/my")

@app.get("/")
def root():
    return {"message": "API работает. Документация: /docs"}