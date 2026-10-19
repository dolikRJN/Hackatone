from pydantic import BaseModel

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SessionResult(BaseModel):
    speed_wpm: float
    accuracy_pct: float
    max_combo: int = 0
    errors_json: dict = {}