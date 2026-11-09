import secrets
from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import db
from auth_utils import (
    DUMMY_HASH,
    ROLE_NAMES,
    get_current_user,
    render_page,
    validate_csrf,
    verify_password,
)

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(f"/{user['role']}/", status_code=303)
    return render_page(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf(request, csrf_token)
    # 自行處理長度，避免預設 422 驗證回應包含原始密碼。
    if not (1 <= len(username) <= 50 and 1 <= len(password) <= 1024):
        return render_page(request, "login.html", status_code=401,
                           error="帳號或密碼錯誤", username=username[:50])
    user = db.find_user_by_username(username)
    valid = verify_password(password, user["password_hash"] if user else DUMMY_HASH)
    if not valid or user is None or user["role"] not in ROLE_NAMES:
        return render_page(request, "login.html", status_code=401,
                           error="帳號或密碼錯誤", username=username)
    request.session.clear()
    request.session.update(user_id=user["id"], csrf_token=secrets.token_urlsafe(32))
    return RedirectResponse(f"/{user['role']}/", status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: Annotated[str, Form()] = ""):
    validate_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
