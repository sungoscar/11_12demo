import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware

from auth_utils import get_current_user, render_page
from config import BASE_DIR, Settings
from routers import auth, author, editor


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="投稿審查系統")
    app.state.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.add_middleware(
        SessionMiddleware, secret_key=settings.session_secret,
        session_cookie="submission_session", max_age=8 * 60 * 60,
        same_site="lax", https_only=settings.https_only,
    )
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.include_router(auth.router)
    app.include_router(author.router, prefix="/author")
    app.include_router(editor.router, prefix="/editor")

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        if exc.status_code == 303:
            return RedirectResponse(exc.headers["Location"], status_code=303)
        return app.state.templates.TemplateResponse(
            request=request, name="error.html", status_code=exc.status_code,
            headers=exc.headers,
            context={"message": exc.detail if exc.status_code == 403 else "找不到頁面或無法處理此請求。"},
        )

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, exc: psycopg.Error):
        return app.state.templates.TemplateResponse(
            request=request, name="error.html", status_code=503,
            context={"message": "資料庫暫時無法使用，請稍後再試或聯絡管理員。"},
        )

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        user = get_current_user(request)
        if user:
            return RedirectResponse(f"/{user['role']}/", status_code=303)
        return render_page(request, "index.html")

    return app


app = create_app()
