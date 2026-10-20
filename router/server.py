"""Сборка приложения: python -m uvicorn router.server:app --reload."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from database import BASE_DIR, init_db
from router.api import router
from router import seo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Создаём недостающие таблицы и применяем совместимые изменения старой БД.
    init_db()
    yield


app = FastAPI(title="Тренажёр слепой печати", lifespan=lifespan)
app.include_router(router)
app.include_router(seo.router)


@app.middleware("http")
async def indexing_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (not seo.SITE_URL or path in seo.PRIVATE_PATHS
            or path.startswith(("/api/", "/docs", "/redoc", "/openapi.json"))
            or response.status_code >= 400):
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response

# HTML отдают маршруты страниц, а файловый сервер обслуживает только ресурсы.
app.mount("/static", StaticFiles(directory=BASE_DIR / "template" / "static"), name="static")
