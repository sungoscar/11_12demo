"""登入、角色與 CSRF 的共用後端驗證。"""
import secrets

from fastapi import HTTPException, Request
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

import db

password_hasher = PasswordHash.recommended()
# 不存在的帳號也執行 Argon2 驗證，避免明顯的時間差異。
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))
ROLE_NAMES = {"author": "作者", "editor": "編輯"}


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def get_current_user(request: Request):
    if hasattr(request.state, "current_user"):
        return request.state.current_user
    user_id = request.session.get("user_id")
    user = db.find_user_by_id(user_id) if type(user_id) is int else None
    if user is None or user["role"] not in ROLE_NAMES:
        if user_id is not None:
            request.session.clear()
        user = None
    request.state.current_user = user
    return user


def require_role(request: Request, role: str):
    if role not in ROLE_NAMES:
        raise ValueError("不支援的角色")
    user = get_current_user(request)
    if user is None:
        raise HTTPException(303, headers={"Location": "/login"})
    if user["role"] != role:
        raise HTTPException(403, detail="您沒有權限存取此頁面。")
    return user


def csrf_token(request: Request) -> str:
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_urlsafe(32)
    return request.session["csrf_token"]


def validate_csrf(request: Request, token: str) -> None:
    expected = request.session.get("csrf_token")
    if not isinstance(expected, str) or not secrets.compare_digest(expected.encode(), token.encode()):
        raise HTTPException(403, detail="表單已失效，請重新整理頁面後再試。")


def render_page(request: Request, name: str, *, status_code=200, **context):
    return request.app.state.templates.TemplateResponse(
        request=request, name=name,
        context={"user": get_current_user(request), "role_names": ROLE_NAMES,
                 "csrf_token": csrf_token(request), **context},
        status_code=status_code,
    )
