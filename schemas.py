from pydantic import BaseModel

class LoginRequest(BaseModel):
    email: str
    password: str

class SessionResult(BaseModel):
    wpm: int
    accuracy: float
    max_combo: int
    errors: dict