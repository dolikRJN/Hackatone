"""Публичные HTML-страницы и SEO-файлы. Домен задаётся через SITE_URL."""

import json
import os
from html import escape
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response

from database import BASE_DIR
from router.api import get_leaderboard


def validate_site_url(value: str) -> str:
    """Принимаем только адрес сайта: https://domain.ru, без пути и параметров."""
    value = value.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
        raise ValueError("SITE_URL должен быть адресом вида https://domain.ru без пути и параметров")
    return value


SITE_URL = validate_site_url(os.environ.get("SITE_URL", "https://blindtyping.codetimes.org"))
router = APIRouter(include_in_schema=False)
PUBLIC_PATHS = ("/", "/leaderboard")
PRIVATE_PATHS = {"/auth", "/game", "/profile"}
LEGACY_PATHS = {"index": "/", "auth": "/auth", "game": "/game", "profile": "/profile", "leaderboard": "/leaderboard"}


def seo_metadata(path: str) -> str:
    # На разработке нет канонического домена; не используем входящий Host вместо него.
    if not SITE_URL:
        return '<meta name="robots" content="noindex, follow">'
    canonical = SITE_URL + path
    image = SITE_URL + "/static/img/social-preview.png"
    graph = [{
        "@type": "WebSite", "@id": SITE_URL + "/#website",
        "url": SITE_URL + "/", "name": "Печать героя", "inLanguage": "ru",
    }, {
        "@type": "WebPage" if path == "/" else "CollectionPage",
        "@id": canonical + "#webpage", "url": canonical,
        "name": "Тренажёр слепой печати — Печать героя" if path == "/" else "Таблица лидеров — Печать героя",
        "isPartOf": {"@id": SITE_URL + "/#website"}, "inLanguage": "ru",
    }]
    if path == "/":
        graph.append({
            "@type": "WebApplication", "@id": SITE_URL + "/#app",
            "name": "Печать героя", "url": SITE_URL + "/",
            "applicationCategory": "EducationalApplication", "operatingSystem": "Web browser",
            "inLanguage": ["ru", "en"],
            "description": "Тренажёр слепой печати с упражнениями на русском и английском, подсказками по пальцам и статистикой прогресса.",
        })
    # Экранируем и HTML-атрибуты, и закрывающий тег script внутри JSON.
    structured = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False).replace("<", "\\u003c")
    return "\n".join([
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">',
        f'<meta property="og:url" content="{escape(canonical, quote=True)}">',
        f'<meta property="og:image" content="{escape(image, quote=True)}">',
        '<meta property="og:image:type" content="image/png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="Печать героя — тренажёр слепой печати на русском и английском">',
        f'<meta name="twitter:image" content="{escape(image, quote=True)}">',
        '<meta name="twitter:image:alt" content="Печать героя — тренажёр слепой печати">',
        f'<script type="application/ld+json">{structured}</script>',
    ])


def format_number(value) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", "\u00a0").replace(".", ",")


def render_public_page(filename: str, path: str, compact: bool = False) -> HTMLResponse:
    html = (BASE_DIR / "template" / filename).read_text(encoding="utf-8")
    html = html.replace("<!-- SEO_META -->", seo_metadata(path))
    # Поисковик получает рейтинг сразу в ответе сервера, даже без выполнения JS.
    entries = get_leaderboard(sort_by="speed", period="all")[:5 if compact else 20]
    fields = ("rank", "username", "wpm", "accuracy") if compact else ("rank", "username", "wpm", "cpm", "accuracy", "xp")
    rows = []
    for item in entries:
        values = {
            "rank": item["rank"], "username": item["username"],
            "wpm": format_number(item["wpm"]), "cpm": format_number(int(item["wpm"] * 5 + .5)),
            "accuracy": format_number(item["accuracy"]) + "%", "xp": format_number(item["xp"]),
        }
        cells = []
        for field in fields:
            content = escape(str(values[field]))
            if field == "rank":
                badge = f' place--{item["rank"]}' if item["rank"] <= 3 else ""
                content = f'<span class="place{badge}">{content}</span>'
            css = ' class="num"' if field not in ("rank", "username") else ""
            cells.append(f'<td data-field="{field}"{css}>{content}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    table_id = "home-leaders" if compact else "leaders"
    html = html.replace(f'<tbody id="{table_id}"></tbody>', f'<tbody id="{table_id}">' + "".join(rows) + "</tbody>")
    message = "" if rows else "Пока нет завершённых тренировок"
    html = html.replace('id="leaders-status" role="status">Загрузка рейтинга…', f'id="leaders-status" role="status">{message}')
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
def homepage():
    return render_public_page("index.html", "/", compact=True)


@router.get("/{filename}.html")
def legacy_page(filename: str, request: Request):
    # Сохраняем mode/next и другие параметры старых закладок и ссылок.
    target = LEGACY_PATHS.get(filename)
    if target is None:
        raise HTTPException(404, "Страница не найдена")
    if request.url.query:
        target += "?" + request.url.query
    return RedirectResponse(target, status_code=301)


@router.get("/leaderboard", response_class=HTMLResponse)
def leaderboard():
    return render_public_page("leaderboard.html", "/leaderboard")


@router.get("/auth", response_class=FileResponse)
def auth_page():
    return FileResponse(BASE_DIR / "template" / "auth.html")


@router.get("/game", response_class=FileResponse)
def game_page():
    return FileResponse(BASE_DIR / "template" / "game.html")


@router.get("/profile", response_class=FileResponse)
def profile_page():
    return FileResponse(BASE_DIR / "template" / "profile.html")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    if not SITE_URL:
        return "User-agent: *\nDisallow: /\n"
    # Страницы с noindex разрешено обходить, чтобы робот прочитал этот тег.
    return ("User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /docs\n"
            "Disallow: /redoc\nDisallow: /openapi.json\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n")


@router.get("/sitemap.xml")
def sitemap():
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    if SITE_URL:
        for path in PUBLIC_PATHS:
            SubElement(SubElement(root, "url"), "loc").text = SITE_URL + path
    # Не указываем lastmod без реальной даты изменения содержимого.
    return Response(tostring(root, encoding="utf-8", xml_declaration=True), media_type="application/xml")
