from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import services
from schemas import LoginRequest, SessionResult

app = FastAPI(title="Тренажёр слепой печати")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.post("/api/login")
def login(data: LoginRequest):
    return {"status": "ok", "token": "test", "user_id": 1}

@app.get("/api/texts")
def get_text(mode: str = "words", dif: int = 1):
    texts = {
        "words": "случайный набор слов пайтон клавиатура",
        "sentences": "Быстрая печать требует ежедвенвых тренировок и правильной техники.",
        "code": "def train(epochs=10):\n    for epoch in range(epochs):\n   pass",
        "symbols": "!@# $%^ &*() _+-= [] |:;"
    }
    return {"text": texts.get(mode, texts["words"])}

@app.post("/api/result")
def save_result(data: SessionResult):
    earned_xp = services.calc_xp(data.wpm, data.accuracy, data.max_combo)
    achievements = services.check_acheves(data.wpm, data.max_combo)
    problem_keys = services.get_top_mistakes(data.errors)

    return {
        "earned_xp": earned_xp,
        "achievements": achievements,
        "promlem_keys": problem_keys,
    }

@app.get("/api/leaderboard")
def get_leaderboard():
    return [
        {"username": "test", "wpm": 345, "accuracy": 99.1, "xp": 6767},
    ]

@app.get("/")
def root():
    return {"message": "API работает. Документация: /docs"}