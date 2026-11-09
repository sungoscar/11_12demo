import base64
import json
import re

import psycopg
import pytest
from fastapi.testclient import TestClient

import db
from auth_utils import hash_password, verify_password
from config import Settings
from main import create_app


def token(response):
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def login(client, credentials, username="author1", **extra):
    csrf = token(client.get("/login"))
    return client.post("/login", data={"username": username, "password": credentials[0],
                                      "csrf_token": csrf, **extra})


@pytest.mark.parametrize("path,text", [("/", "讓投稿與審查"), ("/login", "登入系統")])
def test_public_pages(client, path, text):
    response = client.get(path)
    assert response.status_code == 200
    assert text in response.text
    assert '<html lang="zh-Hant">' in response.text
    assert response.headers["cache-control"] == "no-store"


def test_static_css(client):
    assert client.get("/static/style.css").status_code == 200


@pytest.mark.parametrize("username,role,title", [
    ("author1", "author", "作者首頁"), ("editor1", "editor", "編輯首頁")])
def test_successful_login_and_role_home(client, credentials, username, role, title):
    response = login(client, credentials, username)
    assert response.status_code == 303
    assert response.headers["location"] == f"/{role}/"
    home = client.get(response.headers["location"])
    assert home.status_code == 200
    assert title in home.text and username in home.text and "登出" in home.text
    for path in ("/", "/login"):
        assert client.get(path).headers["location"] == f"/{role}/"


@pytest.mark.parametrize("username", ["author1", "does-not-exist", "' OR 1=1 --"])
def test_bad_credentials_are_generic(client, username):
    csrf = token(client.get("/login"))
    response = client.post("/login", data={"username": username, "password": "wrong",
                                           "csrf_token": csrf})
    assert response.status_code == 401
    assert "帳號或密碼錯誤" in response.text
    assert client.get("/author/").status_code == 303


@pytest.mark.parametrize("path", ["/author/", "/editor/"])
def test_anonymous_is_redirected(client, path):
    response = client.get(path)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("username,forbidden", [("author1", "/editor/"), ("editor1", "/author/")])
def test_cross_role_forbidden(client, credentials, username, forbidden):
    login(client, credentials, username)
    response = client.get(forbidden)
    assert response.status_code == 403
    assert "您沒有權限" in response.text


def test_logout_clears_session(client, credentials):
    login(client, credentials)
    csrf = token(client.get("/author/"))
    response = client.post("/logout", data={"csrf_token": csrf})
    assert response.status_code == 303
    assert "expires=Thu, 01 Jan 1970" in response.headers["set-cookie"]
    assert not client.cookies.get("submission_session")
    assert client.get("/author/").headers["location"] == "/login"


@pytest.mark.parametrize("bad_token", [None, "invalid", "錯誤權杖"])
def test_login_csrf_required(client, credentials, bad_token):
    client.get("/login")
    data = {"username": "author1", "password": credentials[0]}
    if bad_token is not None:
        data["csrf_token"] = bad_token
    assert client.post("/login", data=data).status_code == 403


def test_logout_csrf_and_rotation(client, credentials):
    old = token(client.get("/login"))
    login(client, credentials)
    assert client.post("/logout", data={"csrf_token": old}).status_code == 403
    assert client.post("/logout").status_code == 403
    assert client.get("/author/").status_code == 200
    assert client.get("/logout").status_code == 405


def test_submitted_role_is_ignored(client, credentials):
    response = login(client, credentials, role="editor", user_id=2)
    assert response.headers["location"] == "/author/"
    assert client.get("/editor/").status_code == 403


def test_database_role_rechecked(client, credentials, users):
    login(client, credentials)
    users[1]["role"] = "editor"
    assert client.get("/author/").status_code == 403
    assert client.get("/editor/").status_code == 200


def test_deleted_user_session_rejected(client, credentials, users):
    login(client, credentials)
    del users[1]
    assert client.get("/author/").headers["location"] == "/login"


def test_cookie_minimal_signed_and_http_only(client, credentials):
    response = login(client, credentials)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    raw = client.cookies.get("submission_session")
    payload = json.loads(base64.b64decode(raw.split(".")[0]))
    assert set(payload) == {"user_id", "csrf_token"}
    client.cookies.clear()
    client.cookies.set("submission_session", raw + "tampered")
    assert client.get("/author/").headers["location"] == "/login"


def test_production_cookie_secure(users):
    with TestClient(create_app(Settings(session_secret="x" * 48, https_only=True)),
                    base_url="https://testserver") as secure_client:
        response = secure_client.get("/login")
        assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.parametrize("secret", ["", "short", "請填入至少32字元的隨機金鑰"])
def test_missing_or_weak_secret_fails(monkeypatch, secret):
    monkeypatch.setenv("SESSION_SECRET", secret)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        Settings.from_env()


def test_production_rejects_insecure_cookie(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "false")
    with pytest.raises(RuntimeError, match="HTTPS"):
        Settings.from_env()


def test_argon2_hashing(credentials):
    password, hashed = credentials
    assert hashed.startswith("$argon2id$") and password not in hashed
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password(password, "broken-hash")
    assert hash_password(password) != hashed


def test_database_failure_is_sanitized(client, monkeypatch):
    def broken(_):
        raise psycopg.OperationalError("internal-connection-detail")
    monkeypatch.setattr(db, "find_user_by_username", broken)
    csrf = token(client.get("/login"))
    response = client.post("/login", data={"csrf_token": csrf, "username": "author1", "password": "x"})
    assert response.status_code == 503
    assert "資料庫暫時無法使用" in response.text
    assert "internal-connection-detail" not in response.text


@pytest.mark.parametrize("username,password", [
    ("", "value"), ("author1", ""), ("a" * 51, "value"), ("author1", "p" * 1025)])
def test_invalid_credentials_length_is_generic(client, username, password):
    csrf = token(client.get("/login"))
    response = client.post("/login", data={"csrf_token": csrf, "username": username,
                                           "password": password})
    assert response.status_code == 401
    assert "帳號或密碼錯誤" in response.text
    if len(password) > 1024:
        assert password not in response.text


def test_username_is_html_escaped(client):
    csrf = token(client.get("/login"))
    response = client.post("/login", data={"csrf_token": csrf, "username": '<script>alert(1)</script>',
                                           "password": "wrong"})
    assert response.status_code == 401
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text
